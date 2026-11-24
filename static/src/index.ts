import './livemap.css';
import 'leaflet/dist/leaflet.css';

import * as L from 'leaflet';
import 'leaflet-rotatedmarker';
import { GasMeasurementPlotter } from './gas-measurement-plotter';
import { WindMeasurementPlotter } from './wind-measurement-plotter';
import { FocusControl } from './focus-control';
import { WindControl } from './wind-control';
import { Slider } from './gas-slider';
import { NumericDisplay } from './numeric-display';
import { LiveLocationMarker } from './live-location-marker';
import { addWindroseToMap } from './windrose';
import { getUrlParameter, is_screenshot_mode, extractCampaignIdFromCurrentUrl, extractStartEndFromUrlIfPresent, Campaign } from './url-helper';
import { getBaseConcentration } from './campaign-statistics';

declare var campaign: Campaign;
declare var availableSpecies: string[] | undefined;
declare var mapSettings: { default_layer?: string } | undefined;


type RangeMode =
    | { kind: "fixed"; min: number; max: number }
    | { kind: "baseline"; baselineGas: 'CH4' | 'CO2' | 'CH4-LI' | 'CO2-LI';
        fallback: number; spanParam: string; spanScale: number };

interface SpeciesConfig {
    unit: string;
    range: RangeMode;
}


const SPECIES: { [key: string]: SpeciesConfig } = {
    
    "NO":    { unit: "ppb",   range: { kind: "fixed", min: 0, max: 200 } },  // mean ~16 ppb, peaks up to ~640 ppb (saturates)
    "NO2":   { unit: "ppb",   range: { kind: "fixed", min: 0, max: 60  } },  // mean ~11-17 ppb, peaks ~52-67 ppb
    "NOx":   { unit: "ppb",   range: { kind: "fixed", min: 0, max: 250 } },  // sum NO+NO2; roadside regularly >100 ppb (no measured data)
    "O3":    { unit: "ppb",   range: { kind: "fixed", min: 0, max: 120 } },  // mean ~10-20 ppb, peaks ~110-118 ppb; WHO-8h ~50 ppb mid-scale
    "CO":    { unit: "ppm",   range: { kind: "fixed", min: 0, max: 3   } },  // mean ~0.3 ppm, peaks ~0.9-1.7 ppm
    "PM10":  { unit: "ug/m3", range: { kind: "fixed", min: 0, max: 80  } },  // mean ~20, realistic peaks ~115-145 (outliers ignored); WHO-24h 45
    "PM4":   { unit: "ug/m3", range: { kind: "fixed", min: 0, max: 50  } },  // between PM2.5 and PM10 (no measured data)
    "PM2.5": { unit: "ug/m3", range: { kind: "fixed", min: 0, max: 40  } },  // mean ~12, realistic peaks ~58-66; WHO-24h 15
    "PM1":   { unit: "ug/m3", range: { kind: "fixed", min: 0, max: 30  } },  // finest fraction, below PM2.5 (no measured data)

    
    "CH4":    { unit: "ppm", range: { kind: "baseline", baselineGas: "CH4",    fallback: 2.0,   spanParam: "span", spanScale: 0.001 } },
    "CH4-LI": { unit: "ppm", range: { kind: "baseline", baselineGas: "CH4-LI", fallback: 2.0,   spanParam: "span", spanScale: 0.001 } },
    "CO2":    { unit: "ppm", range: { kind: "baseline", baselineGas: "CO2",    fallback: 400.0, spanParam: "span", spanScale: 1.0   } },
    "CO2-LI": { unit: "ppm", range: { kind: "baseline", baselineGas: "CO2-LI", fallback: 400.0, spanParam: "span", spanScale: 1.0   } },
    "H2O":    { unit: "ppm", range: { kind: "fixed", min: 0, max: 100 } },
};


const INITIAL_GAS = "NO";


function unitFor(species: string): string {
    return SPECIES[species] ? SPECIES[species].unit : "";
}

async function main() {

    function get_map_options(){
        if (is_screenshot_mode()) {
            return { zoomControl: false };
        }
        return {};
    }

    var map_options = get_map_options();
    var map_view_lat = Number(getUrlParameter("lat", "48.112167"));
    var map_view_long = Number(getUrlParameter("long", "11.583705"));
    var map = L.map('map', map_options).setView([map_view_lat, map_view_long], 16);
    map.attributionControl.setPrefix('<a href="https://leafletjs.com/">Leaflet</a> | &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors');

    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19});
    const osm_local = L.tileLayer('/static/tiles/osm/{z}/{x}/{y}.png', {maxZoom: 19});
    const osm_local_grayscale = L.tileLayer('/static/tiles/osm_grayscale/{z}/{x}/{y}.png', {maxZoom: 19});

    const tile_layers: { [key: string]: L.TileLayer } = {
        "OSM": osm,
        "Local": osm_local,
        "LocalG": osm_local_grayscale
    };
    const defaultLayerKey = (typeof mapSettings !== 'undefined' && mapSettings?.default_layer && tile_layers[mapSettings.default_layer])
        ? mapSettings.default_layer
        : "OSM";
    tile_layers[defaultLayerKey].addTo(map);


    var NavigationIcon = L.icon({
        iconUrl: '/static/navigation-icon.svg',
        iconSize:     [16, 16],
        iconAnchor:   [8, 8],
        popupAnchor:  [8, 16]
    });

    var LiveNavigationIcon = L.icon({
        iconUrl: '/static/live-location-icon.svg',
        iconSize:     [16, 16],
        iconAnchor:   [8, 8],
        popupAnchor:  [8, 16]
    });

    campaign = extractStartEndFromUrlIfPresent(campaign);

    var marker = L.marker([48.112167000, 11.583705000], {icon: NavigationIcon, rotationAngle: 0});
    var live_marker = L.marker([48.112167000, 11.583705000], {icon: LiveNavigationIcon, rotationAngle: 0});

    const selector = document.getElementById('gas-selector') as HTMLSelectElement | null;
    const initial_gas = (selector && selector.value) ? selector.value : INITIAL_GAS;
    const gas_slider = new Slider('gas-slider', map);
    
    const gas_display = new NumericDisplay('gas-concentration-display', initial_gas, unitFor(initial_gas));

    const campaign_id = extractCampaignIdFromCurrentUrl();

    const speciesKeys = (typeof availableSpecies !== 'undefined' && Array.isArray(availableSpecies) && availableSpecies.length > 0)
        ? availableSpecies.filter(s => s in SPECIES)
        : Object.keys(SPECIES);
    const activeSpeciesKeys = speciesKeys.length > 0 ? speciesKeys : Object.keys(SPECIES);

    const gas_layers: { [key: string]: { plotter: GasMeasurementPlotter } } = {};

    for (const name of activeSpeciesKeys) {
        const cfg = SPECIES[name];
        let min_value: number;
        let max_value: number;

        if (cfg.range.kind === "fixed") {
            min_value = cfg.range.min;
            max_value = cfg.range.max;
        } else {
            
            min_value = await getBaseConcentration(campaign_id, cfg.range.baselineGas, cfg.range.fallback);
            max_value = min_value + Number(getUrlParameter(cfg.range.spanParam, "100")) * cfg.range.spanScale;
        }

        const plotter = new GasMeasurementPlotter(
            map, marker, name, min_value, max_value, cfg.unit,
            gas_slider, gas_display, campaign.start, campaign.end
        );
        plotter.startPlotting(1000);
        gas_layers[name] = { plotter: plotter };
    }

    const wind_plotter = new WindMeasurementPlotter(map, campaign.start, campaign.end);
    wind_plotter.startPlotting(1000);

    const isLive = campaign.end === null;
    const start_key = (initial_gas in gas_layers) ? initial_gas : Object.keys(gas_layers)[0];
    let active_plotter: GasMeasurementPlotter | null = gas_layers[start_key]?.plotter ?? null;

    const focus_control = new FocusControl(
        { position: 'topleft' },
        (focus: boolean) => active_plotter?.setFocus(focus),
        isLive
    );
    const wind_control = new WindControl({ position: 'topleft' }, (show: boolean) => wind_plotter.show(show))

    if (active_plotter) {
        active_plotter.show(true);
        if (isLive) {
            active_plotter.setFocus(true);
        } else {
            active_plotter.onFinished = () => {
                const bounds = active_plotter?.getBounds();
                if (bounds && bounds.isValid()) {
                    map.fitBounds(bounds, { padding: [24, 24] });
                }
            };
        }
        gas_slider.updateGasType(start_key, active_plotter.measurements);
        if (start_key !== initial_gas) {
            gas_display.changeGasType(start_key, unitFor(start_key));
        }
    }



    document.getElementById('gas-selector')?.addEventListener('change', (event) => {
        const target = event.target as HTMLSelectElement;
        const selectedLayerKey = target.value;

        const wasFocused = active_plotter ? active_plotter.focus : false;
        if (wasFocused && active_plotter) {
            active_plotter.setFocus(false);
        }

        Object.values(gas_layers).forEach(gas => gas.plotter.show(false));

        if (selectedLayerKey in gas_layers) {
            active_plotter = gas_layers[selectedLayerKey].plotter;
            active_plotter.show(true);
            if (wasFocused) {
                active_plotter.setFocus(true);
            }
            gas_slider.updateGasType(selectedLayerKey, active_plotter.measurements)
            
            gas_display.changeGasType(selectedLayerKey, unitFor(selectedLayerKey));
        }
    });


    const live_location_plotter = new LiveLocationMarker(map, live_marker, campaign.start, campaign.end);
    live_location_plotter.startPlotting(1000);


    if (is_screenshot_mode()) {
        addWindroseToMap(map, campaign);
        const show_wind = getUrlParameter("wind", "false");
        if (show_wind == "true") {
            wind_plotter.show(true);
        } else {
            wind_plotter.show(false);
        }
    } else {
        wind_control.addTo(map);
        focus_control.addTo(map);
        L.control.layers(tile_layers).addTo(map);

        marker.addTo(map);
        live_marker.addTo(map);
    }

}

main();
