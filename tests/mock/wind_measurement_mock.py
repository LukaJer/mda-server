import math
import random
import time
from datetime import datetime

from models.wind_measurement_model import WindMeasurement
from tests.mock.measurement_mock import MeasurementMock


class WindMeasurementMock(MeasurementMock):
    def __init__(self):
        MeasurementMock.__init__(self)

    def _measurement_routine(self) -> None:
        while not self._stop.is_set():
            now = datetime.now()
            measurement = WindMeasurement(
                datetime=now,
                heading=0,
                speed=20.0 * math.sin(math.radians(now.second)) + 20.0)
            self._post_measurement(measurement, '/measurement/wind', )
            time.sleep(random.randint(500, 1500)/1000)
