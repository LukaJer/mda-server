import random
import time
from datetime import datetime

from models.log_model import Log
from tests.mock.measurement_mock import MeasurementMock


class LogMock(MeasurementMock):
    def __init__(self):
        MeasurementMock.__init__(self)

    def _measurement_routine(self) -> None:
        while not self._stop.is_set():
            now = datetime.now()
            log = Log(
                datetime=datetime.now(),
                sensor="MockLog",
                description="Some test log")
            self._post_measurement(log, '/measurement/log', )
            time.sleep(random.randint(800, 1500) / 1000)
