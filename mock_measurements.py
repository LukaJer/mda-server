import argparse
import time
from typing import Optional

import requests

from app import load_devices_config
from tests.mock import LocationMeasurementMock, WindMeasurementMock, GasMeasurementMock
from tests.mock.log_mock import LogMock
from tests.mock.measurement_mock import MeasurementMock


def start_mock_campaign(server_url: str, name: str, author: str, description: Optional[str]) -> None:
    """Enable measurement ingestion and start a named campaign on the server."""
    base = server_url.rstrip("/")
    try:
        requests.get(f"{base}/enable-measurements/1", timeout=5.0)
        payload = {"name": name, "author": author}
        if description:
            payload["description"] = description
        r = requests.post(f"{base}/campaign/start", data=payload, allow_redirects=False, timeout=5.0)
        if r.status_code in (200, 302):
            print(f"Started mock campaign {name!r} (author={author!r})")
        else:
            print(f"Warning: POST /campaign/start returned HTTP {r.status_code}")
    except requests.RequestException as e:
        print(f"Warning: Could not start mock campaign on {base}: {e}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run mock sensor publishers against mda-server.")
    parser.add_argument(
        "-c", "--campaign",
        nargs="?",
        const="Mock Campaign",
        default=None,
        metavar="NAME",
        help="Start a live campaign on the server when starting the mock script (defaults to 'Mock Campaign' if no name is given).",
    )
    parser.add_argument("--author", default="Mock", help="Campaign author when --campaign is used (default: Mock).")
    parser.add_argument("--description", default=None, help="Optional campaign description when --campaign is used.")
    parser.add_argument(
        "-t", "--track",
        default=None,
        metavar="TRACK_NAME",
        help="Optional <trk><name> substring from mock_location_measurements.xml (e.g. 'Munich Extended Loop').",
    )
    parser.add_argument(
        "--server",
        default=MeasurementMock.SERVER_URL,
        help=f"mda-server base URL (default: {MeasurementMock.SERVER_URL}).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    MeasurementMock.SERVER_URL = args.server.rstrip("/")

    if args.campaign:
        start_mock_campaign(MeasurementMock.SERVER_URL, args.campaign, args.author, args.description)

    cfg = load_devices_config()
    mocks = []

    if cfg.get("GPS", {}).get("enabled", True):
        mocks.append(LocationMeasurementMock(track_name=args.track))
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
