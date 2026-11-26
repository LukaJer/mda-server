from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from util.api_helper import ApiHelper, Request


class GasMeasurement(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    datetime: Mapped[datetime] = mapped_column(DateTime)
    type: Mapped[str] = mapped_column(String)
    concentration: Mapped[float] = mapped_column(Float)
    unit: Mapped[float] = mapped_column(String)

    @staticmethod
    def create_from_json(json: dict) -> "GasMeasurement":
        return GasMeasurement(
                datetime=ApiHelper.parse_iso_datetime(json["datetime"]),
                type=json["type"],
                concentration=float(json["concentration"]),
                unit=json["unit"]
            )

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "type": self.type,
            "concentration": self.concentration,
            "unit": self.unit
        }

    def __str__(self) -> str:
        return f"GasMeasurement(datetime={self.datetime}, type={self.type}, concentration={self.concentration}, unit={self.unit})"

    @staticmethod
    def get_data(request: Request):
        if request.start_datetime is None:
            raise Exception("Invalid request! 'start'")

        def query(measurement):
            q = (db.select(measurement)
                 .order_by(measurement.datetime.asc())
                 .where(measurement.datetime >= request.start_datetime)
                 .where(measurement.type == request.type)
                 .limit(request.limit))

            if request.end_datetime is not None:
                q = q.where(measurement.datetime <= request.end_datetime)

            return q

        return db.session.execute(query(GasMeasurement)).scalars().all()
