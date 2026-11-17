import time
from datetime import datetime

from models.log_model import Log
from tests.mock.measurement_mock import MeasurementMock


class LogMock(MeasurementMock):
    def __init__(self):
        MeasurementMock.__init__(self)
        self.start_time = time.time()
        self._last_sent: dict[str, str] = {}

    def _send_if_changed(self, sensor: str, description: str, now: datetime) -> None:
        if self._last_sent.get(sensor) == description:
            return
        self._last_sent[sensor] = description
        self._post_measurement(
            Log(datetime=now, sensor=sensor, description=description),
            '/measurement/log',
        )

    def _measurement_routine(self) -> None:
        sensors = ("AC32e", "O342e", "CO12e", "Grimm11D", "GPS", "Wind")

        while not self._stop.is_set():
            elapsed = time.time() - self.start_time
            now = datetime.now()

            if elapsed < 3.0:
                for s in sensors:
                    self._send_if_changed(s, "Unconnected", now)
            elif elapsed < 6.0:
                self._send_if_changed("GPS", "Waiting for GPS fix", now)
                for s in ("AC32e", "O342e", "CO12e", "Grimm11D", "Wind"):
                    self._send_if_changed(s, "Waiting for GPS time", now)
            elif elapsed < 12.0:
                self._send_if_changed("GPS", "OK", now)
                self._send_if_changed("Wind", "OK", now)
                for s in ("AC32e", "O342e", "CO12e"):
                    self._send_if_changed(s, "Warming up", now)
                self._send_if_changed("Grimm11D", "Warming up / Zeroing", now)
            else:
                # Normal operation with periodic simulated transient errors
                cycle = (elapsed - 12.0) % 45.0
                for s in sensors:
                    if s == "O342e" and 20.0 <= cycle < 26.0:
                        self._send_if_changed(s, "ERROR: Modbus read timeout", now)
                    elif s == "Wind" and 32.0 <= cycle < 37.0:
                        self._send_if_changed(s, "ERROR: UMB status 40 (calibrating)", now)
                    else:
                        self._send_if_changed(s, "OK", now)

            time.sleep(1.0)
