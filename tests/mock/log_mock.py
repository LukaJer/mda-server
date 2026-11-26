import time
from datetime import datetime

from app import load_devices_config
from models.log_model import Log
from tests.mock.measurement_mock import MeasurementMock


class LogMock(MeasurementMock):
    def __init__(self):
        MeasurementMock.__init__(self)
        self.start_time = time.time()
        self._last_sent: dict[str, str] = {}
        cfg = load_devices_config()
        self._sensors = tuple(k for k, v in cfg.items() if v.get("enabled", False))

    def _send_if_changed(self, sensor: str, description: str, now: datetime) -> None:
        if sensor not in self._sensors:
            return
        if self._last_sent.get(sensor) == description:
            return
        self._last_sent[sensor] = description
        self._post_measurement(
            Log(datetime=now, sensor=sensor, description=description),
            '/measurement/log',
        )

    def _measurement_routine(self) -> None:
        while not self._stop.is_set():
            elapsed = time.time() - self.start_time
            now = datetime.now()

            if elapsed < 3.0:
                for s in self._sensors:
                    self._send_if_changed(s, "Unconnected", now)
            elif elapsed < 6.0:
                self._send_if_changed("GPS", "Waiting for GPS fix", now)
                for s in self._sensors:
                    if s != "GPS":
                        self._send_if_changed(s, "Waiting for GPS time", now)
            elif elapsed < 12.0:
                self._send_if_changed("GPS", "OK", now)
                self._send_if_changed("Wind", "OK", now)
                for s in ("AC32e", "O342e", "CO12e", "Picarro"):
                    self._send_if_changed(s, "Warming up", now)
                self._send_if_changed("Grimm11D", "Warming up / Zeroing", now)
            else:
                cycle = (elapsed - 12.0) % 45.0
                for s in self._sensors:
                    if s == "O342e" and 20.0 <= cycle < 26.0:
                        self._send_if_changed(s, "ERROR: Modbus read timeout", now)
                    elif s == "Wind" and 32.0 <= cycle < 37.0:
                        self._send_if_changed(s, "ERROR: UMB status 40 (calibrating)", now)
                    else:
                        self._send_if_changed(s, "OK", now)

            time.sleep(1.0)
