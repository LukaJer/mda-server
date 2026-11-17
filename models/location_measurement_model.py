from datetime import datetime, timedelta

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from util.api_helper import Request


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
            datetime=datetime.fromisoformat(json["datetime"]),
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
    def get_data(request: Request, additional_limit: int = 0, buffer: timedelta = None):
        if request.start_datetime is None:
            raise Exception("Invalid request! 'start-date' and 'start-time' must be given")

        start_datetime = request.start_datetime - buffer if buffer else request.start_datetime
        end_datetime = request.end_datetime + buffer if buffer and request.end_datetime else request.end_datetime

        def query(measurement):
            q = (db.select(measurement)
                 .order_by(measurement.datetime.asc())
                 .where(measurement.datetime >= start_datetime)
                 .limit(request.limit + additional_limit))

            if end_datetime is not None:
                q = q.where(measurement.datetime <= end_datetime)

            return q

        return db.session.execute(query(LocationMeasurement)).scalars().all()
