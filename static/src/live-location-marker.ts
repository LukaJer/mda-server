import * as L from 'leaflet';
import { MeasurementPlotter } from './measurement-plotter';

export class LiveLocationMarker extends MeasurementPlotter {
        map: L.Map
        marker: L.Marker
    
        constructor(
                map: L.Map, 
                marker: L.Marker, 
                start_datetime: Date, 
                end_datetime: Date | null = null
            ) {
            super(start_datetime, end_datetime, 'location');
            this.map = map;
            this.marker = marker;
        }
    
        drawMeasurement(measurement: any) {
            this.updateMarkerPosition(measurement);
        }
    
        updateMarkerPosition(measurement: any) {
            this.marker.setRotationAngle(measurement.heading);
            this.marker.setLatLng([measurement.latitude, measurement.longitude]);
        }
    
        getRequestUrl(): string {
            const start = MeasurementPlotter.formatToISODateTime(this.start_datetime);

            if (this.end_datetime !== null) {
                const end = MeasurementPlotter.formatToISODateTime(this.end_datetime);
                return `/measurement/location?start=${start}&end=${end}`;  
            } else {
                return `/measurement/location?start=${start}`;
            }
        }
    }
