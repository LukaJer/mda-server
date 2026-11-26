import type { StyleSpecification } from 'maplibre-gl';

export interface MBTilesInfo {
    filename: string;
    name?: string;
    description?: string;
    format?: string;
    minzoom?: number;
    maxzoom?: number;
    bounds?: string;
    tile_count?: number;
    size_mb?: number;
}

/**
 * Build an offline MapLibre style for OpenMapTiles-schema vector MBTiles.
 */
export function buildVectorStyle(
    tileUrlTemplate: string,
    minzoom: number,
    maxzoom: number,
    grayscale: boolean,
): StyleSpecification {
    const c = grayscale
        ? {
              bg: '#f2f2f2',
              landcover: '#e9e9e9',
              park: '#e1e1e1',
              water: '#d2d2d2',
              building: '#dcdcdc',
              buildingLine: '#c8c8c8',
              aeroway: '#dfdfdf',
              minorRoad: '#ffffff',
              minorCasing: '#d0d0d0',
              majorRoad: '#fafafa',
              majorCasing: '#b5b5b5',
              motorway: '#f0f0f0',
              motorwayCasing: '#9a9a9a',
              rail: '#bdbdbd',
              boundary: '#a3a3a3',
          }
        : {
              bg: '#f4f2ee',
              landcover: '#e7eadc',
              park: '#d6e9c6',
              water: '#aadaff',
              building: '#ded8ce',
              buildingLine: '#cbc3b7',
              aeroway: '#e2e2e2',
              minorRoad: '#ffffff',
              minorCasing: '#d9d4cb',
              majorRoad: '#fde69a',
              majorCasing: '#d7b45c',
              motorway: '#f7b277',
              motorwayCasing: '#d47c3c',
              rail: '#b0a99f',
              boundary: '#9e95a3',
          };

    return {
        version: 8,
        name: grayscale ? 'EnvBike Offline Grayscale' : 'EnvBike Offline Color',
        sources: {
            openmaptiles: {
                type: 'vector',
                tiles: [tileUrlTemplate],
                minzoom,
                maxzoom,
            },
        },
        layers: [
            {
                id: 'background',
                type: 'background',
                paint: { 'background-color': c.bg },
            },
            {
                id: 'landcover',
                type: 'fill',
                source: 'openmaptiles',
                'source-layer': 'landcover',
                paint: { 'fill-color': c.landcover, 'fill-opacity': 0.7 },
            },
            {
                id: 'landuse',
                type: 'fill',
                source: 'openmaptiles',
                'source-layer': 'landuse',
                paint: { 'fill-color': c.landcover, 'fill-opacity': 0.5 },
            },
            {
                id: 'park',
                type: 'fill',
                source: 'openmaptiles',
                'source-layer': 'park',
                paint: { 'fill-color': c.park, 'fill-opacity': 0.8 },
            },
            {
                id: 'water',
                type: 'fill',
                source: 'openmaptiles',
                'source-layer': 'water',
                paint: { 'fill-color': c.water },
            },
            {
                id: 'waterway',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'waterway',
                paint: {
                    'line-color': c.water,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 16, 3],
                },
            },
            {
                id: 'aeroway',
                type: 'fill',
                source: 'openmaptiles',
                'source-layer': 'aeroway',
                paint: { 'fill-color': c.aeroway },
            },
            {
                id: 'building',
                type: 'fill',
                source: 'openmaptiles',
                'source-layer': 'building',
                minzoom: 13,
                paint: {
                    'fill-color': c.building,
                    'fill-outline-color': c.buildingLine,
                },
            },
            {
                id: 'road-minor-casing',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'transportation',
                filter: ['in', 'class', 'minor', 'service', 'track', 'path'],
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': c.minorCasing,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 12, 1, 16, 5, 19, 10],
                },
            },
            {
                id: 'road-minor',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'transportation',
                filter: ['in', 'class', 'minor', 'service', 'track', 'path'],
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': c.minorRoad,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 16, 3.5, 19, 8],
                },
            },
            {
                id: 'road-major-casing',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'transportation',
                filter: ['in', 'class', 'primary', 'secondary', 'tertiary', 'trunk'],
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': c.majorCasing,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1.5, 16, 7.5, 19, 14],
                },
            },
            {
                id: 'road-major',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'transportation',
                filter: ['in', 'class', 'primary', 'secondary', 'tertiary', 'trunk'],
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': c.majorRoad,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 16, 5.5, 19, 11],
                },
            },
            {
                id: 'road-motorway-casing',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'transportation',
                filter: ['==', 'class', 'motorway'],
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': c.motorwayCasing,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1.5, 16, 9, 19, 16],
                },
            },
            {
                id: 'road-motorway',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'transportation',
                filter: ['==', 'class', 'motorway'],
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': c.motorway,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 16, 6.5, 19, 13],
                },
            },
            {
                id: 'rail',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'transportation',
                filter: ['==', 'class', 'rail'],
                paint: {
                    'line-color': c.rail,
                    'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.8, 16, 2],
                    'line-dasharray': [2, 2],
                },
            },
            {
                id: 'boundary',
                type: 'line',
                source: 'openmaptiles',
                'source-layer': 'boundary',
                paint: {
                    'line-color': c.boundary,
                    'line-width': 1,
                    'line-dasharray': [3, 2],
                },
            },
        ],
    };
}
