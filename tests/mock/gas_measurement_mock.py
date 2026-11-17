import math
import random
import time
from datetime import datetime

from models.gas_measurement_model import GasMeasurement
from tests.mock.measurement_mock import MeasurementMock


class GasMeasurementMock(MeasurementMock):
    def __init__(self):
        MeasurementMock.__init__(self)
        self.start_time = time.time()

    def _measurement_routine(self) -> None:
        while not self._stop.is_set():
            elapsed_time = time.time() - self.start_time

            measurement = GasMeasurement(
                datetime=datetime.now(),
                type="CH4",
                concentration=math.sin(math.radians(3 * elapsed_time)) + 3,
                unit="ppm")
            self._post_measurement(measurement, '/measurement/gas', )

            measurement = GasMeasurement(
                datetime=datetime.now(),
                type="CO2",
                concentration=300.0 * math.sin(math.radians(4 * elapsed_time)) + 700.0,
                unit="ppm")
            self._post_measurement(measurement, '/measurement/gas', )

            measurement = GasMeasurement(
                datetime=datetime.now(),
                type="H2O",
                concentration=50.0 * math.sin(math.radians(4 * elapsed_time)) + 50.0,
                unit="ppm")
            self._post_measurement(measurement, '/measurement/gas', )

            time.sleep(random.randint(4500, 5500) / 1000)
