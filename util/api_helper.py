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
        return datetime.strptime(datetime_iso, '%Y-%m-%dT%H:%M:%S')

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
        try:
            return datetime.fromisoformat(request)
        except ValueError:
            return None
