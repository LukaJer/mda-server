import os
import time
from datetime import datetime
from itertools import cycle
from threading import Thread
from typing import List, Optional
from xml.etree import ElementTree

from models.location_measurement_model import LocationMeasurement
from tests.mock.measurement_mock import MeasurementMock


class LocationMeasurementMock(MeasurementMock):
    INTERVAL_SECONDS = 1.0

    def __init__(self, track_name: Optional[str] = None):
        MeasurementMock.__init__(self)
        track_path = os.path.join(os.path.dirname(__file__), "mock_location_measurements.xml")
        self._track_points = self._load_mock_track(track_path, track_name=track_name)
        self._measurement_thread = Thread(target=self._measurement_routine)

    def _load_mock_track(self, path: str, track_name: Optional[str] = None) -> List[tuple]:
        root = ElementTree.parse(path).getroot()
        if track_name:
            needle = track_name.strip().lower()
            trks = [
                trk for trk in root.findall('trk')
                if needle in (trk.findtext('name') or '').strip().lower()
            ]
            if not trks:
                available = [(trk.findtext('name') or '<unnamed>') for trk in root.findall('trk')]
                raise ValueError(f"Track {track_name!r} not found. Available tracks: {available}")
            trkpts = [pt for trk in trks for pt in trk.findall('trkseg/trkpt')]
        else:
            trkpts = root.findall('trk/trkseg/trkpt')

        points = []
        for trkpt in trkpts:
            points.append((
                float(trkpt.get("lat")),
                float(trkpt.get("lon")),
                float(trkpt.find("extensions").find("course").text),
                float(trkpt.find("extensions").find("speed").text),
            ))
        return points

    def _measurement_routine(self) -> None:
        for lat, lon, heading, speed in cycle(self._track_points):
            if self._stop.is_set():
                break
            measurement = LocationMeasurement(
                datetime=datetime.now(),
                latitude=lat,
                longitude=lon,
                accuracy=0.0,
                heading=heading,
                speed=speed,
            )
            self._post_measurement(measurement, '/measurement/location')
            time.sleep(self.INTERVAL_SECONDS)
