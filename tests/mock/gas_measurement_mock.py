import math
import time
from datetime import datetime

from app import load_devices_config
from models.gas_measurement_model import GasMeasurement
from tests.mock.measurement_mock import MeasurementMock


class GasMeasurementMock(MeasurementMock):
    def __init__(self):
        MeasurementMock.__init__(self)
        self.start_time = time.time()
        self._cfg = load_devices_config()

    def _is_enabled(self, key: str) -> bool:
        return bool(self._cfg.get(key, {}).get("enabled", False))

    def _interval(self, key: str, default: float) -> float:
        return float(self._cfg.get(key, {}).get("interval", default))

    def _measurement_routine(self) -> None:
        last_sent: dict[str, float] = {}

        while not self._stop.is_set():
            now_mono = time.time()
            elapsed = now_mono - self.start_time
            if elapsed < 12.0:
                time.sleep(1.0)
                continue

            now = datetime.now()
            samples = []

            no_val = 80.0 * math.sin(math.radians(3 * elapsed)) + 90.0
            no2_val = 25.0 * math.sin(math.radians(4 * elapsed)) + 30.0

            if self._is_enabled("AC32e") and now_mono - last_sent.get("AC32e", 0.0) >= self._interval("AC32e", 1.0):
                last_sent["AC32e"] = now_mono
                samples.extend([("NO", no_val, "ppb"), ("NO2", no2_val, "ppb"), ("NOx", no_val + no2_val, "ppb")])

            if self._is_enabled("O342e") and now_mono - last_sent.get("O342e", 0.0) >= self._interval("O342e", 1.0):
                last_sent["O342e"] = now_mono
                samples.append(("O3", 40.0 * math.sin(math.radians(2 * elapsed)) + 55.0, "ppb"))

            if self._is_enabled("CO12e") and now_mono - last_sent.get("CO12e", 0.0) >= self._interval("CO12e", 1.0):
                last_sent["CO12e"] = now_mono
                samples.append(("CO", 1.0 * math.sin(math.radians(3 * elapsed)) + 1.2, "ppm"))

            if self._is_enabled("Picarro") and now_mono - last_sent.get("Picarro", 0.0) >= self._interval("Picarro", 2.0):
                last_sent["Picarro"] = now_mono
                samples.extend([
                    ("CH4", 0.5 * math.sin(math.radians(3 * elapsed)) + 2.2, "ppm"),
                    ("CO2", 50.0 * math.sin(math.radians(2 * elapsed)) + 430.0, "ppm"),
                    ("H2O", 0.3 * math.sin(math.radians(2 * elapsed)) + 1.2, "%"),
                ])

            if self._is_enabled("Grimm11D") and now_mono - last_sent.get("Grimm11D", 0.0) >= self._interval("Grimm11D", 6.0):
                last_sent["Grimm11D"] = now_mono
                samples.extend([
                    ("PM10", 30.0 * math.sin(math.radians(2 * elapsed)) + 40.0, "ug/m3"),
                    ("PM4", 18.0 * math.sin(math.radians(2 * elapsed)) + 24.0, "ug/m3"),
                    ("PM2.5", 15.0 * math.sin(math.radians(2 * elapsed)) + 19.0, "ug/m3"),
                    ("PM1", 10.0 * math.sin(math.radians(2 * elapsed)) + 13.0, "ug/m3"),
                ])

            for gas_type, concentration, unit in samples:
                measurement = GasMeasurement(
                    datetime=now,
                    type=gas_type,
                    concentration=concentration,
                    unit=unit,
                )
                self._post_measurement(measurement, '/measurement/gas')

            time.sleep(0.5)
