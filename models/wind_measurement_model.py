from datetime import datetime

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from util.api_helper import Request


class WindMeasurement(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    datetime: Mapped[datetime] = mapped_column(DateTime)
    heading: Mapped[float] = mapped_column(Float)
    speed: Mapped[float] = mapped_column(Float)

    @staticmethod
    def create_from_json(json: dict) -> "WindMeasurement":
        return WindMeasurement(
                datetime=datetime.fromisoformat(json["datetime"]),
                heading=float(json["heading"]),
                speed=float(json["speed"])
            )

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "heading": f"{self.heading:.2f}",
            "speed": f"{self.speed:.2f}"
        }

    def __str__(self) -> str:
        return f"WindMeasurement(datetime={self.datetime}, heading={self.heading}, speed={self.speed})"

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

        return db.session.execute(query(WindMeasurement)).scalars().all()
