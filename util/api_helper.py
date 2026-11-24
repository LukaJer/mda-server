from datetime import datetime, timedelta
from typing import Optional

from werkzeug.datastructures.structures import MultiDict

from models.base_model import db


class Request:
    DEFAULT_LIMIT = 2000
    DEFAULT_GAS_TYPE = "NO"

    def __init__(self, args: MultiDict[str, str]):
        self.start_datetime = Request.get_datetime(args.get("start"))
        self.end_datetime = Request.get_datetime(args.get("end"))

        self.with_location = Request.get_bool(args.get("with-location"), "1")

        self.limit = Request.get_int(args.get("limit"), default=Request.DEFAULT_LIMIT)
        self.t = timedelta(seconds=Request.get_int(args.get("t"), 0))
        self.type = ApiHelper.get_post_if_set(args.get("type"), Request.DEFAULT_GAS_TYPE)

    @staticmethod
    def get_datetime(datetime_iso: str) -> datetime | None:
        if datetime_iso is None:
            return None
        return ApiHelper.parse_iso_datetime(datetime_iso)

    @staticmethod
    def get_bool(val: str, compare: str) -> bool:
        val = ApiHelper.get_post_if_set(val)
        if val is None:
            return False
        return val == compare

    @staticmethod
    def get_int(val, default: int = None) -> int | None:
        if val is not None:
            return int(val)
        else:
            return default


class ApiHelper:

    @staticmethod
    def get_post_if_set(request: str, default: any = None):
        return request if request else default

    @staticmethod
    def get_datetime_if_set(request: str) -> Optional[datetime]:
        if not request or not request.strip():
            return None
        val = request.strip()
        for fmt in ("%Y.%m.%d %H:%M", "%Y.%m.%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None

    @staticmethod
    def parse_iso_datetime(value: str) -> datetime:
        """Parse an ISO-8601 datetime string and normalize aware timestamps to naive local time."""
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
