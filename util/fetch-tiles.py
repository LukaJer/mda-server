import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from random import randint
from typing import List

import requests


class Tile:
    DOWNLOAD_HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    DOWNLOAD_DELAY_MIN_MS = 50
    DOWNLOAD_DELAY_MAX_MS = 90

    def __init__(self, x: int, y: int, z: int):
        self.x = x
        self.y = y
        self.z = z

    @classmethod
    def create_from_lat_long(cls, latitude: float, longitude: float, zoom: int) -> "Tile":
        x = math.floor((longitude + 180) / 360 * 2 ** zoom)
        y = math.floor((1 - math.log(
            math.tan(latitude * math.pi / 180) + 1 / math.cos(latitude * math.pi / 180)) / math.pi) / 2 * 2 ** zoom)
        return Tile(x, y, zoom)

    def download(self, url: str, path: str, delay: bool = False) -> None:
        url = self._replace_with_coordinates(url)
        path = self._replace_with_coordinates(path)
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)

        if not os.path.isfile(path):
            if delay:
                time.sleep(randint(Tile.DOWNLOAD_DELAY_MIN_MS, Tile.DOWNLOAD_DELAY_MAX_MS) / 1000)
            response = requests.get(url, headers=self.DOWNLOAD_HEADERS)
            if response.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(response.content)
            else:
                print(f"Failed to download tile: {url}")

    def _replace_with_coordinates(self, path):
        path = path.replace("{x}", str(self.x))
        path = path.replace("{y}", str(self.y))
        path = path.replace("{z}", str(self.z))
        return path

    def __sub__(self, other) -> List["Tile"]:
        if self.z != other.z:
            raise Exception("Only tile with same zoom level can be subtracted!")

        tiles = []
        for x in range(self.x, other.x + 1):
            for y in range(self.y, other.y + 1):
                tiles.append(Tile(x, y, self.z))
        return tiles

    def __repr__(self) -> str:
        return f"Tile(x={self.x}, y={self.y}, {self.z})"


@dataclass
class Place:
    name: str
    start_tile: Tile
    end_tile: Tile

    def download(self, url: str, path: str, delay: bool = False) -> None:
        tiles = self.start_tile - self.end_tile
        for tile, n in zip(tiles, range(len(tiles))):
            print(f"Place: {self.name} -- "
                  f"Zoom: {self.start_tile.z} -- "
                  f"Progress: {n:8}/{len(tiles)} -- "
                  f"Missing: {len(tiles) - n:8} -- "
                  f"{100 * n / len(tiles):.2f}%")
            tile.download(url, path, delay)


def main():
    for zoom in range(10, 20):
        places = [
            Place(
                "Munich Inner Area",
                Tile.create_from_lat_long(48.17023303391656, 11.52571082634845, zoom=zoom),
                Tile.create_from_lat_long(48.10123806531225, 11.640676450527536, zoom=zoom)
            ),
            Place(
                "Munich",
                Tile.create_from_lat_long(48.24835006475558, 11.39607679271317, zoom=zoom),
                Tile.create_from_lat_long(48.04034195935822, 11.764118753615119, zoom=zoom)
            )
        ]

        for place in places:
            place.download("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                           "../static/tiles/osm/{z}/{x}/{y}.png",
                           True)


if __name__ == "__main__":
    main()
