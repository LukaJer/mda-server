import time

from tests.mock import LocationMeasurementMock, WindMeasurementMock, GasMeasurementMock
from tests.mock.log_mock import LogMock


def main():
    location_measurement_mock = LocationMeasurementMock()
    wind_measurement_mock = WindMeasurementMock()
    gas_measurement_mock = GasMeasurementMock()
    log_mock = LogMock()

    try:
        location_measurement_mock.start()
        wind_measurement_mock.start()
        gas_measurement_mock.start()
        log_mock.start()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        location_measurement_mock.stop()
        wind_measurement_mock.stop()
        gas_measurement_mock.stop()
        log_mock.stop()


if __name__ == "__main__":
    main()
