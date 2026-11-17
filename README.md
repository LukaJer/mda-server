# Installation

### Installation of node modules with container
```bash
podman run -v .:/root -it docker.io/library/node:21-alpine sh
```


### Install Webpack CLI globally and run webpack
```bash
npm install webpack webpack-cli -g
webpack --config webpack.config.js
```

### Usefull Links
- [Beispiel Leaflet mit HQ/Retina-Kacheln](https://maps.omniscale.com/de/examples/leaflet_hq)
- [HQ/Retina-Kachel](https://maps.omniscale.net/v2/mapsosc-b667cf5a/style.default/16/34877/22747.png?hq=true)
- [Retina Basemap](https://developers.arcgis.com/esri-leaflet/samples/retina-basemap/)
- [Switch2OSM Docker Container for OSM Tiles](https://switch2osm.org/serving-tiles/using-a-docker-container/)
- [OSM Tile Server - GitHub](https://github.com/Overv/openstreetmap-tile-server)
- [OSM Tile Server - DockerHub](https://hub.docker.com/r/overv/openstreetmap-tile-server)
- [UMB Protocol - GitHub](https://github.com/Tasm-Devil/lufft-python)