import './livemap.css';
import 'leaflet/dist/leaflet.css';
import 'maplibre-gl/dist/maplibre-gl.css';

import * as L from 'leaflet';
import 'leaflet-rotatedmarker';
import maplibreGL from '@maplibre/maplibre-gl-leaflet';
import { buildVectorStyle, MBTilesInfo } from './mbtiles-style';
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
declare var mapSettings: {
    default_layer?: string;
    color_palette?: string;
    active_mbtiles_info?: MBTilesInfo | null;
    has_local_png?: boolean;
    has_local_gray_png?: boolean;
} | undefined;


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

    const tile_layers: { [key: string]: L.Layer } = {
        "OSM": osm,
    };
    if (typeof mapSettings !== 'undefined' && mapSettings?.has_local_png) {
        tile_layers["Local"] = L.tileLayer('/static/tiles/osm/{z}/{x}/{y}.png', {maxZoom: 19});
    }
    if (typeof mapSettings !== 'undefined' && mapSettings?.has_local_gray_png) {
        tile_layers["LocalG"] = L.tileLayer('/static/tiles/osm_grayscale/{z}/{x}/{y}.png', {maxZoom: 19});
    }
    const mbtilesInfo = typeof mapSettings !== 'undefined' ? mapSettings?.active_mbtiles_info : null;
    if (mbtilesInfo && mbtilesInfo.filename) {
        const fmt = (mbtilesInfo.format || 'pbf').toLowerCase();
        const origin = window.location.origin;
        if (fmt === 'pbf' || fmt === 'mvt') {
            try {
                const tileUrl = `${origin}/tiles/mbtiles/${encodeURIComponent(mbtilesInfo.filename)}/{z}/{x}/{y}.pbf`;
                const minz = mbtilesInfo.minzoom ?? 0;
                const maxz = mbtilesInfo.maxzoom ?? 14;
                const colorGl = maplibreGL({
                    style: buildVectorStyle(tileUrl, minz, maxz, false),
                    interactive: false,
                });
                const grayGl = maplibreGL({
                    style: buildVectorStyle(tileUrl, minz, maxz, true),
                    interactive: false,
                });
                colorGl.on('add', () => {
                    colorGl.getMaplibreMap()?.on('error', (e: any) => console.error('MBTiles error:', e?.error || e));
                });
                grayGl.on('add', () => {
                    grayGl.getMaplibreMap()?.on('error', (e: any) => console.error('MBTilesG error:', e?.error || e));
                });
                tile_layers["MBTiles"] = colorGl;
                tile_layers["MBTilesG"] = grayGl;
            } catch (err) {
                console.error('Failed to initialize MBTiles vector layers:', err);
            }
        } else {
            const tileUrl = `/tiles/mbtiles/${encodeURIComponent(mbtilesInfo.filename)}/{z}/{x}/{y}.${fmt}`;
            const rasterLayer = L.tileLayer(tileUrl, {
                minZoom: mbtilesInfo.minzoom ?? 0,
                maxZoom: 19,
                maxNativeZoom: mbtilesInfo.maxzoom ?? 18,
            });
            tile_layers["MBTiles"] = rasterLayer;
            tile_layers["MBTilesG"] = rasterLayer;
        }
    }
    const defaultLayerKey = (typeof mapSettings !== 'undefined' && mapSettings?.default_layer && tile_layers[mapSettings.default_layer])
        ? mapSettings.default_layer
        : (tile_layers["MBTiles"] ? "MBTiles" : "OSM");
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

    const isLive = campaign.end === null;
    const palette = (typeof mapSettings !== 'undefined' && mapSettings?.color_palette) ? mapSettings.color_palette : 'default';
    const casingPane = map.createPane('trackCasingPane');
    casingPane.style.zIndex = '399';
    casingPane.style.pointerEvents = 'none';
    const casingRenderer = L.canvas({ padding: 0.5, pane: 'trackCasingPane' });
    const canvasRenderer = L.canvas({ padding: 0.5 });

    const loadingEl = document.getElementById('track-loading');
    const loadingTextEl = document.getElementById('track-loading-text');
    function setTrackLoading(visible: boolean, text: string = 'Loading track...') {
        if (!loadingEl) return;
        loadingEl.style.display = visible ? 'inline-flex' : 'none';
        if (loadingTextEl && text) {
            loadingTextEl.textContent = text;
        }
    }

    const gas_layers: { [key: string]: { plotter: GasMeasurementPlotter; finished: boolean } } = {};
    let active_plotter: GasMeasurementPlotter | null = null;
    let hasFittedInitialBounds = false;
    let isFocused = isLive;

    async function getOrCreatePlotter(name: string): Promise<GasMeasurementPlotter | null> {
        if (name in gas_layers) {
            return gas_layers[name].plotter;
        }
        const cfg = SPECIES[name];
        if (!cfg) {
            return null;
        }

        let min_value: number;
        let max_value: number;
        if (cfg.range.kind === "fixed") {
            min_value = cfg.range.min;
            max_value = cfg.range.max;
        } else {
            min_value = await getBaseConcentration(campaign_id, cfg.range.baselineGas, cfg.range.fallback);
            max_value = min_value + Number(getUrlParameter(cfg.range.spanParam, "100")) * cfg.range.spanScale;
        }

        if (name in gas_layers) {
            return gas_layers[name].plotter;
        }

        const plotter = new GasMeasurementPlotter(
            map, marker, name, min_value, max_value, cfg.unit,
            gas_slider, gas_display, campaign.start, campaign.end, palette, canvasRenderer, casingRenderer
        );
        const entry = { plotter, finished: false };
        plotter.onBatch = (totalCount: number) => {
            if (active_plotter === plotter && !entry.finished) {
                setTrackLoading(true, `Loading ${name} (${totalCount.toLocaleString()} pts)...`);
            }
        };
        plotter.onPollSettled = () => {
            if (active_plotter === plotter && isLive) {
                setTrackLoading(false);
            }
        };
        plotter.onFinished = () => {
            entry.finished = true;
            if (active_plotter === plotter) {
                setTrackLoading(false);
            }
            if (!isLive && !hasFittedInitialBounds && active_plotter === plotter) {
                hasFittedInitialBounds = true;
                const bounds = plotter.getBounds();
                if (bounds && bounds.isValid()) {
                    map.fitBounds(bounds, { padding: [24, 24] });
                }
            }
        };
        gas_layers[name] = entry;
        return plotter;
    }

    const wind_plotter = new WindMeasurementPlotter(map, campaign.start, campaign.end);
    wind_plotter.startPlotting(1000);

    const start_key = activeSpeciesKeys.includes(initial_gas) ? initial_gas : activeSpeciesKeys[0];

    const focus_control = new FocusControl(
        { position: 'topleft' },
        (focus: boolean) => {
            isFocused = focus;
            active_plotter?.setFocus(focus);
        },
        isLive
    );
    const wind_control = new WindControl({ position: 'topleft' }, (show: boolean) => wind_plotter.show(show))

    setTrackLoading(true, `Loading ${start_key}...`);
    active_plotter = await getOrCreatePlotter(start_key);
    if (active_plotter) {
        active_plotter.show(true);
        if (isFocused) {
            active_plotter.setFocus(true);
        }
        active_plotter.startPlotting(1000);
        gas_slider.updateGasType(start_key, active_plotter.measurements);
        if (start_key !== initial_gas) {
            gas_display.changeGasType(start_key, unitFor(start_key));
            if (selector && Array.from(selector.options).some(opt => opt.value === start_key)) {
                selector.value = start_key;
                selector.dispatchEvent(new Event('change', { bubbles: false }));
            }
        }
    } else {
        setTrackLoading(false);
    }

    let switchSeq = 0;
    document.getElementById('gas-selector')?.addEventListener('change', async (event) => {
        const target = event.target as HTMLSelectElement;
        const selectedLayerKey = target.value;
        const seq = ++switchSeq;

        if (active_plotter) {
            active_plotter.stopPlotting();
            if (active_plotter.focus) {
                active_plotter.setFocus(false);
            }
            active_plotter.show(false);
            active_plotter = null;
        }

        setTrackLoading(true, `Loading ${selectedLayerKey}...`);
        const nextPlotter = await getOrCreatePlotter(selectedLayerKey);
        if (seq !== switchSeq || !nextPlotter) {
            if (seq === switchSeq) setTrackLoading(false);
            return;
        }

        active_plotter = nextPlotter;
        active_plotter.show(true);
        if (isFocused) {
            active_plotter.setFocus(true);
        }
        gas_slider.updateGasType(selectedLayerKey, active_plotter.measurements);
        gas_display.changeGasType(selectedLayerKey, unitFor(selectedLayerKey));
        if (active_plotter.previous_measurement && Number.isFinite(active_plotter.previous_measurement.concentration)) {
            gas_display.updateValue(active_plotter.previous_measurement.concentration);
        }

        const entry = gas_layers[selectedLayerKey];
        if (isLive || !entry.finished) {
            const count = active_plotter.measurements.size;
            if (count > 0 && !isLive) {
                setTrackLoading(true, `Loading ${selectedLayerKey} (${count.toLocaleString()} pts)...`);
            }
            active_plotter.startPlotting(1000);
        } else {
            setTrackLoading(false);
        }
    });


    const live_location_plotter = new LiveLocationMarker(map, live_marker, campaign.start, campaign.end);
    live_location_plotter.startPlotting(1000);


    if (is_screenshot_mode()) {
        addWindroseToMap(map, campaign).catch((error) => {
            console.error('Failed to add windrose to map:', error);
        });
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
