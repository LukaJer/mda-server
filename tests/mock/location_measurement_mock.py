import time
from datetime import datetime, timedelta
from itertools import cycle
from threading import Thread
from typing import List
from xml.etree import ElementTree

from models.location_measurement_model import LocationMeasurement
from tests.mock.measurement_mock import MeasurementMock


class LocationMeasurementMock(MeasurementMock):
    def __init__(self):
        MeasurementMock.__init__(self)
        self._mock_location_measurements = self._load_mock_location_measurements("./tests/mock/mock_location_measurements.xml")
        self._measurement_thread = Thread(target=self._measurement_routine)

    def _load_mock_location_measurements(self, path: str) -> List[LocationMeasurement]:
        root = ElementTree.parse(path).getroot()
        location_measurements = []
        now = datetime.now()

        for trkpt in root.findall('trk/trkseg/trkpt'):
            location_measurements.append(
                LocationMeasurement(
                    datetime=now,
                    latitude=float(trkpt.get("lat")),
                    longitude=float(trkpt.get("lon")),
                    accuracy=0.0,
                    heading=float(trkpt.find("extensions").find("course").text),
                    speed=float(trkpt.find("extensions").find("speed").text)
                )
            )
            now += timedelta(seconds=1)
        return location_measurements

    def _measurement_routine(self) -> None:
        cycle_location_measurements = cycle(self._mock_location_measurements)
        while not self._stop.is_set():
            current_location_measurement = next(cycle_location_measurements)
            while datetime.now() < current_location_measurement.datetime:
                time.sleep(0.1)
            self._post_measurement(current_location_measurement, '/measurement/location')
