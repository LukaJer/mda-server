from abc import abstractmethod, ABC
from threading import Thread, Event

import requests

from tests.mock.measurement_mock_logger import MeasurementMockLogger


class MeasurementMock(ABC):
    SERVER_URL = 'http://127.0.0.1:5000'

    def __init__(self):
        self._setup_logger()
        self._stop = Event()
        self._measurement_thread = Thread(target=self._measurement_routine)

    def _setup_logger(self) -> None:
        self.logger = MeasurementMockLogger

    def start(self) -> None:
        self._measurement_thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._measurement_thread.join()

    @abstractmethod
    def _measurement_routine(self) -> None:
        pass

    def _post_measurement(self, measurement: any, path: str) -> None:
        r = requests.post(
            url=self.SERVER_URL + path,
            json=measurement.serialize()
        )
        self.logger.info(f"POST {measurement} returned status code {r.status_code}")
