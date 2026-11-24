from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from util.api_helper import ApiHelper, Request


class LocationMeasurement(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    datetime: Mapped[datetime] = mapped_column(DateTime)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float)
    heading: Mapped[float] = mapped_column(Float)
    speed: Mapped[float] = mapped_column(Float)

    @staticmethod
    def create_from_json(json: dict) -> "LocationMeasurement":
        return LocationMeasurement(
            datetime=ApiHelper.parse_iso_datetime(json["datetime"]),
            latitude=float(json["latitude"]),
            longitude=float(json["longitude"]),
            accuracy=float(json["accuracy"]),
            heading=float(json["heading"]),
            speed=float(json["speed"])
        )

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "latitude": f"{self.latitude:.9f}",
            "longitude": f"{self.longitude:.9f}",
            "accuracy": f"{self.accuracy:.3f}",
            "heading": f"{self.heading:.1f}",
            "speed": f"{self.speed:.2f}",
        }

    def __str__(self) -> str:
        return (f"Location("
                f"datetime={self.datetime}, "
                f"lat={self.latitude}, "
                f"long={self.longitude}, "
                f"acc={self.accuracy}, "
                f"heading={self.heading}, "
                f"speed={self.speed})")

    @staticmethod
    def get_data(
        request: Optional[Request],
        additional_limit: int = 0,
        buffer: timedelta = None,
        apply_limit: bool = True,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
    ):
        effective_start = start_datetime if start_datetime is not None else (request.start_datetime if request else None)
        if effective_start is None:
            raise Exception("Invalid request! 'start-date' and 'start-time' must be given")

        effective_end = end_datetime if end_datetime is not None else (request.end_datetime if request else None)
        if buffer:
            effective_start = effective_start - buffer
            if effective_end is not None:
                effective_end = effective_end + buffer

        def query(measurement):
            q = (db.select(measurement)
                 .order_by(measurement.datetime.asc())
                 .where(measurement.datetime >= effective_start))

            if apply_limit and request is not None and request.limit is not None:
                q = q.limit(request.limit + additional_limit)

            if effective_end is not None:
                q = q.where(measurement.datetime <= effective_end)

            return q

        return db.session.execute(query(LocationMeasurement)).scalars().all()
