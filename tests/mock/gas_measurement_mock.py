import math
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
            elapsed = time.time() - self.start_time
            if elapsed < 12.0:
                time.sleep(1.0)
                continue

            now = datetime.now()

            no_val = 80.0 * math.sin(math.radians(3 * elapsed)) + 90.0
            no2_val = 25.0 * math.sin(math.radians(4 * elapsed)) + 30.0

            samples = [
                ("NO", no_val, "ppb"),
                ("NO2", no2_val, "ppb"),
                ("NOx", no_val + no2_val, "ppb"),
                ("O3", 40.0 * math.sin(math.radians(2 * elapsed)) + 55.0, "ppb"),
                ("CO", 1.0 * math.sin(math.radians(3 * elapsed)) + 1.2, "ppm"),
                ("PM10", 30.0 * math.sin(math.radians(2 * elapsed)) + 40.0, "ug/m3"),
                ("PM4", 18.0 * math.sin(math.radians(2 * elapsed)) + 24.0, "ug/m3"),
                ("PM2.5", 15.0 * math.sin(math.radians(2 * elapsed)) + 19.0, "ug/m3"),
                ("PM1", 10.0 * math.sin(math.radians(2 * elapsed)) + 13.0, "ug/m3"),
            ]

            for gas_type, concentration, unit in samples:
                measurement = GasMeasurement(
                    datetime=now,
                    type=gas_type,
                    concentration=concentration,
                    unit=unit,
                )
                self._post_measurement(measurement, '/measurement/gas')

            time.sleep(1.0)
