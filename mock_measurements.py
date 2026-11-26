import time

from app import load_devices_config
from tests.mock import LocationMeasurementMock, WindMeasurementMock, GasMeasurementMock
from tests.mock.log_mock import LogMock


def main():
    cfg = load_devices_config()
    mocks = []

    if cfg.get("GPS", {}).get("enabled", True):
        mocks.append(LocationMeasurementMock())
    if cfg.get("Wind", {}).get("enabled", True):
        mocks.append(WindMeasurementMock())
    if any(cfg.get(k, {}).get("enabled", False) for k in ("AC32e", "O342e", "CO12e", "Grimm11D", "Picarro")):
        mocks.append(GasMeasurementMock())
    mocks.append(LogMock())

    try:
        for m in mocks:
            m.start()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        for m in mocks:
            m.stop()


if __name__ == "__main__":
    main()
