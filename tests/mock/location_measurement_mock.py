import time
from datetime import datetime
from itertools import cycle
from threading import Thread
from typing import List
from xml.etree import ElementTree

from models.location_measurement_model import LocationMeasurement
from tests.mock.measurement_mock import MeasurementMock


class LocationMeasurementMock(MeasurementMock):
    INTERVAL_SECONDS = 1.0

    def __init__(self):
        MeasurementMock.__init__(self)
        self._track_points = self._load_mock_track("./tests/mock/mock_location_measurements.xml")
        self._measurement_thread = Thread(target=self._measurement_routine)

    def _load_mock_track(self, path: str) -> List[tuple]:
        root = ElementTree.parse(path).getroot()
        points = []
        for trkpt in root.findall('trk/trkseg/trkpt'):
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
