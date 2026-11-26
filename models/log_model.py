from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from util.api_helper import ApiHelper, Request


class Log(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    datetime: Mapped[datetime] = mapped_column(DateTime)
    sensor: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)

    @staticmethod
    def create_from_json(json: dict) -> "Log":
        return Log(
            datetime=ApiHelper.parse_iso_datetime(json["datetime"]),
            sensor=json["sensor"],
            description=json["description"]
        )

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "sensor": self.sensor,
            "description": self.description,
        }

    def __str__(self) -> str:
        return f"Log(datetime={self.datetime}, sensor={self.sensor}, long={self.description})"

    @staticmethod
    def get_data(request: Request):
        if request.start_datetime is None:
            raise Exception("Invalid request! 'start-date' and 'start-time' must be given")

        def query(measurement):
            q = (db.select(measurement)
                 .order_by(measurement.datetime.asc())
                 .where(measurement.datetime >= request.start_datetime)
                 .limit(request.limit))

            if request.end_datetime is not None:
                q = q.where(measurement.datetime <= request.end_datetime)

            return q

        return db.session.execute(query(Log)).scalars().all()
