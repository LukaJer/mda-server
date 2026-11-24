import * as L from 'leaflet';
import 'leaflet-rotatedmarker';
import { MeasurementPlotter } from './measurement-plotter';
import { Feature, FeatureCollection, GeoJsonObject } from 'geojson';
import { Slider } from './gas-slider';
import { NumericDisplay } from './numeric-display';

export class GasMeasurementPlotter extends MeasurementPlotter {
    map: L.Map
    gas_measurement_layer: L.GeoJSON
    marker: L.Marker
    gas_name: string;
    focus: boolean = false;
    slider: Slider
    numeric_dispaly: NumericDisplay
    colors: string[] = ['#19994E', '#68BB68', '#A7D866', '#D9EF8A', '#FFFEBA', '#FFDF88', '#FDAE61', '#FDAE61', '#D82F2A'];
    private minimum_concentration: number;
    private maximum_concentration: number;
    private unit: string;           
    private legend: L.Control;


    constructor(
            map: L.Map, 
            marker: L.Marker,
            type: string,
            minimum_concentration: number,
            maximum_concentration: number,
            unit: string,           
            slider: Slider,
            numeric_display: NumericDisplay,
            start_datetime: Date, 
            end_datetime: Date | null = null
        ) {
        super(start_datetime, end_datetime, 'gas');
        this.map = map;
        this.marker = marker;
        this.gas_measurement_layer = L.geoJSON();
        this.gas_name = type;

        this.minimum_concentration = minimum_concentration;
        this.maximum_concentration = maximum_concentration;
        this.unit = unit;           

        this.slider = slider;
        this.numeric_dispaly = numeric_display;

        this.legend = this.createLegend();
    }

    drawMeasurement(measurement: any) {
        this.updateMarkerPosition(measurement);
        this.addMeasurementToLayer(measurement);
        if (this.slider.gas_name == this.gas_name) {
            this.slider.updateSliderMax();
        }
        if (this.numeric_dispaly.gas_name == this.gas_name) {
            this.numeric_dispaly.updateValue(measurement.concentration);
        }
    }

    updateMarkerPosition(measurement: any) {
        this.marker.setRotationAngle(measurement.heading);
        this.marker.setLatLng([measurement.latitude, measurement.longitude]);
    }

    addMeasurementToLayer(measurement: any) {
        const feature: Feature = {
            "type": "Feature",
            "properties": {
                "type": measurement.type,
                "datetime": measurement.datetime,
                "concentration": measurement.concentration,
                "unit": measurement.unit,
            },
            "geometry": {
                "type": "LineString", "coordinates": [[measurement.longitude, measurement.latitude], [this.previous_measurement.longitude, this.previous_measurement.latitude]]
            }
        };

        const color = this.getColor(measurement.concentration);

        L.geoJson(feature, {
            style: function () {
                return {
                    "color": color,
                    "opacity": 1,
                    "weight": 7
                }
            },
            onEachFeature: function (feature, layer) {
                if (feature.properties) {
                    layer.bindPopup(`${feature.properties.datetime}<br>${feature.properties.type}: <b>${feature.properties.concentration}</b>${feature.properties.unit}`);
                }
            }

        }).addTo(this.gas_measurement_layer);

        if (this.focus) {
            this.map.panTo(new L.LatLng(measurement.latitude, measurement.longitude));
        }

    }

    setFocus(focus: boolean): void {
        this.focus = focus;
        if (this.focus) {
            this.map.dragging.disable();
            if (this.previous_measurement && Number.isFinite(this.previous_measurement.latitude) && Number.isFinite(this.previous_measurement.longitude)) {
                this.map.panTo(new L.LatLng(this.previous_measurement.latitude, this.previous_measurement.longitude));
            }
        } else {
            this.map.dragging.enable();
        }
      }

    private getColor(value: number): string {   
        if (value <= this.minimum_concentration) {
            return this.colors[0];
        } else if (value >= this.maximum_concentration) {
            return this.colors[this.colors.length - 1];
        }
    
        const range = this.maximum_concentration - this.minimum_concentration;
        const step = range / (this.colors.length - 1);
        const index = Math.floor((value - this.minimum_concentration) / step);
        const nextIndex = Math.min(index + 1, this.colors.length - 1);
    
        const color1 = this.colors[index];
        const color2 = this.colors[nextIndex];
    
        const ratio = (value - (this.minimum_concentration + index * step)) / step;
    
        return GasMeasurementPlotter.interpolateColor(color1, color2, ratio);
    }
    
    static interpolateColor(color1: string, color2: string, ratio: number): string {
        const hexToRgb = (hex: string) => {
            const bigint = parseInt(hex.slice(1), 16);
            return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
        };
    
        const rgbToHex = (r: number, g: number, b: number) => {
            const componentToHex = (c: number) => c.toString(16).padStart(2, '0');
            return `#${componentToHex(r)}${componentToHex(g)}${componentToHex(b)}`;
        };
    
        const [r1, g1, b1] = hexToRgb(color1);
        const [r2, g2, b2] = hexToRgb(color2);
    
        const r = Math.round(r1 + ratio * (r2 - r1));
        const g = Math.round(g1 + ratio * (g2 - g1));
        const b = Math.round(b1 + ratio * (b2 - b1));
    
        return rgbToHex(r, g, b);
    }

    getRequestUrl(): string {
        const start = MeasurementPlotter.formatToISODateTime(this.start_datetime);

        if (this.end_datetime !== null) {
            const end = MeasurementPlotter.formatToISODateTime(this.end_datetime);
            return `/measurement/gas?with-location=1&start=${start}&end=${end}&type=${this.gas_name}`;  
        } else {
            return `/measurement/gas?with-location=1&start=${start}&type=${this.gas_name}`;
        }
    }

    show(show: boolean) {
        if (show) {
            this.map.addLayer(this.gas_measurement_layer);
            this.map.addControl(this.legend);
        } else {
            this.map.removeLayer(this.gas_measurement_layer);
            this.map.removeControl(this.legend);
        }
    }

    getBounds(): L.LatLngBounds {
        return this.gas_measurement_layer.getBounds();
    }

    private createLegend(): L.Control {
        var legend = new L.Control({position: 'bottomright'});
        var grades = this.generateEquallySpacedValues(this.minimum_concentration, this.maximum_concentration, 8);

        
        const span = this.maximum_concentration - this.minimum_concentration;
        const decimals = span >= 10 ? 0 : (span >= 2 ? 1 : 2);

        var div = L.DomUtil.create('div', 'info legend')
        
        div.innerHTML += '<h4>' + this.gas_name + ' ' + this.unit + '</h4>';
        for (var i = 0; i < grades.length; i++) {
            div.innerHTML +=
                '<i style="background:' + this.getColor(grades[i]) + '"></i> ' +
                grades[i].toFixed(decimals) + (grades[i + 1] ? '&ndash;' + grades[i + 1].toFixed(decimals) + '<br>' : '+');
        }


        legend.onAdd = function (map: L.Map) { return div; };

        return legend;
        
    }

    private generateEquallySpacedValues(min: number, max: number, n: number): number[] {
        if (n === 1) return [min];
    
        const step = (max - min) / (n - 1);
        const values: number[] = [];
    
        for (let i = 0; i < n; i++) {
            values.push(min + i * step);
        }
    
        return values;
    }
}
