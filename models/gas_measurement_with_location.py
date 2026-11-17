from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from models.gas_measurement_model import GasMeasurement
from models.location_measurement_model import LocationMeasurement


class GasMeasurementWithLocation(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    datetime: Mapped[datetime] = mapped_column(DateTime)
    type: Mapped[str] = mapped_column(String)
    concentration: Mapped[float] = mapped_column(Float)
    unit: Mapped[float] = mapped_column(String)
    heading: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    @staticmethod
    def create_from_json(json: dict) -> "GasMeasurementWithLocation":
        pass

    @staticmethod
    def create_from_measurement_and_location(
            measurement: GasMeasurement,
            heading: float,
            speed: float,
            latitude: float,
            longitude: float) -> "GasMeasurementWithLocation":
        return GasMeasurementWithLocation(
            datetime=measurement.datetime,
            type=measurement.type,
            concentration=measurement.concentration,
            unit=measurement.unit,
            heading=heading,
            latitude=latitude,
            longitude=longitude
        )

    def serialize(self) -> dict:
        return {
            "datetime": self.datetime.isoformat(),
            "type": self.type,
            "concentration": self.concentration,
            "unit": self.unit,
            "heading": self.heading,
            "latitude": self.latitude,
            "longitude": self.longitude
        }

    def __eq__(self, other) -> bool:
        return (self.datetime == other.datetime
                and self.type == other.type
                and self.concentration == other.concentration
                and self.unit == other.unit
                and self.heading == other.heading
                and self.latitude == other.latitude
                and self.longitude == other.longitude)

    def __str__(self) -> str:
        return (f"GasMeasurementWithLocation("
                f"datetime={self.datetime}, "
                f"type={self.type}, "
                f"concentration={self.concentration}, "
                f"unit={self.unit}, "
                f"heading={self.heading}, "
                f"latitude={self.latitude}, "
                f"longitude={self.longitude})")
