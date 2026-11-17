import * as L from 'leaflet';
import { getUrlParameter } from './url-helper';

export async function addWindroseToMap(map: L.Map, campaign: any){
    var start = formatDateToString(campaign.start);
    var end = formatDateToString(campaign.end);
    var station = getUrlParameter('station', 'MIM01');

    const wind_mean_data = await fetchWindMeanData(start, end, station);

    var WindroseLegend = L.Control.extend({
        options: {
            position: 'topright'
        },

        onAdd: function (map: L.Map) {
            var div = L.DomUtil.create('div', 'info legend');
            div.innerHTML += `<h4>Wind mean ${wind_mean_data.speed.toFixed(1)} m/s</h4>`;

            var img = L.DomUtil.create('img', 'windrose-legend', div);
            img.src = `/windrose?start=${start}&end=${end}&station=${station}`;
            img.alt = 'Windrose Legend';
            return div;
        }
    });
    
    map.addControl(new WindroseLegend());
}

function formatDateToString(date: Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are zero-indexed
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return `${year}-${month}-${day}T${hours}-${minutes}-${seconds}`;
}

interface WindMeanData {
    direction: number;
    speed: number;
  }

async function fetchWindMeanData(start: String, end: String, station: any): Promise<WindMeanData> {
    const response = await fetch(`/wind-mean?start=${start}&end=${end}&station=${station}`);
    
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
  
    const data: WindMeanData = await response.json();
    return data;
}