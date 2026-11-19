import * as L from 'leaflet'
import 'leaflet-rotatedmarker'
import { MeasurementPlotter } from './measurement-plotter';

export class WindMeasurementPlotter extends MeasurementPlotter {
    map: L.Map
    wind_vanes: L.LayerGroup
    wind_icons: Map<number, L.Icon>

    
    private readonly MIN_SPEED_KMH = 5;

    constructor(map: L.Map, start_datetime: Date, end_datetime: Date | null = null) {
        super(start_datetime, end_datetime, 'wind');
        this.map = map;
        this.wind_vanes = L.layerGroup();
        this.wind_icons = new Map();

        for (let i = 1; i <= 20; i++) {
            const windSpeed = i * 5; // icon steps: 5, 10, 15, 
            const icon = L.icon({
                iconUrl: `/static/icons/wind-vanes/${windSpeed}kt-wind-vane.svg`,
                iconSize: [50, 50],
                iconAnchor:   [25, 0],
            });
            this.wind_icons.set(windSpeed, icon); // Map wind speed to icon
        }
    }

    drawMeasurement(measurement: any) {
        this.addMeasurementToLayer(measurement);
    }

    addMeasurementToLayer(measurement: any) {
        // The sensor reports speed in m/s; convert to km/h
        const wind_speed_in_kmh = measurement.speed * 3.6;

        
        if (wind_speed_in_kmh < this.MIN_SPEED_KMH) {
            return;
        }

        
        let rounded_step = Math.max(5, Math.floor(wind_speed_in_kmh / 5) * 5);
        
        rounded_step = Math.min(rounded_step, 100);

        const marker = L.marker([measurement.latitude, measurement.longitude], {
            icon: this.wind_icons.get(rounded_step),
            rotationAngle: measurement.heading
        });
        this.wind_vanes.addLayer(marker);
    }

    plotData(data: any[]): void {
        let new_measurements = false;
        data.forEach((measurement: any) => {
            if (this.previous_measurement === null){
                this.previous_measurement = measurement;
                if (!this.measurements.has(measurement.end_datetime)) {
                    new_measurements = true;
                }
            } else {
                if (!this.measurements.has(measurement.end_datetime)){
                    this.start_datetime = new Date(measurement.end_datetime);
                    this.drawMeasurement(measurement);
                    this.previous_measurement = measurement;
                    new_measurements = true;
                }
            }
            this.measurements.set(measurement.end_datetime, measurement);
        });

        if (!new_measurements) {
            throw new Error("No new data available.");
        }
    }

    getRequestUrl(): string {
        const start = MeasurementPlotter.formatToISODateTime(this.start_datetime);

        if (this.end_datetime !== null) {
            const end = MeasurementPlotter.formatToISODateTime(this.end_datetime);
            return `/measurement/wind?with-location=1&start=${start}&end=${end}&t=10`;
        } else {
            return `/measurement/wind?with-location=1&start=${start}&t=10`;
        }
    }

    show(show: boolean) {
        if (show) {
            this.map.addLayer(this.wind_vanes);
        } else {
            this.map.removeLayer(this.wind_vanes);
        }
    }
}
