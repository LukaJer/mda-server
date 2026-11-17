import math
from datetime import datetime

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from models.wind_measurement_model import WindMeasurement


class WindMeasurementWithLocation(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    datetime: Mapped[datetime] = mapped_column(DateTime)
    heading: Mapped[float] = mapped_column(Float)
    speed: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    @staticmethod
    def create_from_json(json: dict) -> "WindMeasurementWithLocation":
        pass

    @staticmethod
    def create_from_measurement_and_location(
            measurement: WindMeasurement,
            heading: float,
            speed: float,
            latitude: float,
            longitude: float) -> "WindMeasurementWithLocation":

        v_rw, heading_rw = WindMeasurementWithLocation.calculate_real_wind_and_heading(
            speed, heading, measurement.speed, measurement.heading)

        return WindMeasurementWithLocation(
            datetime=measurement.datetime,
            speed=v_rw,
            heading=heading_rw,
            latitude=latitude,
            longitude=longitude
        )

    @staticmethod
    def calculate_real_wind_and_heading(bike_speed, bike_heading, apparent_wind_speed, apparent_wind_heading):
        v_bx = bike_speed * math.sin(math.radians(bike_heading))
        v_by = bike_speed * math.cos(math.radians(bike_heading))

        v_awx = apparent_wind_speed * math.sin(math.radians(bike_heading + apparent_wind_heading + 180))
        v_awy = apparent_wind_speed * math.cos(math.radians(bike_heading + apparent_wind_heading + 180))

        v_rwx = v_awx + v_bx
        v_rwy = v_awy + v_by

        v_rw = math.sqrt(v_rwx ** 2 + v_rwy ** 2)
        heading_rw = (-math.degrees(math.atan2(v_rwy, v_rwx)) + 450) % 360

        return v_rw, heading_rw

    def serialize(self) -> dict:
        return {
            "datetime": self.datetime.isoformat(),
            "speed": self.speed,
            "heading": self.heading,
            "latitude": self.latitude,
            "longitude": self.longitude
        }

    def __eq__(self, other) -> bool:
        return (self.datetime == other.datetime
                and self.speed == other.speed
                and self.heading == other.heading
                and self.latitude == other.latitude
                and self.longitude == other.longitude)

    def __str__(self) -> str:
        return (f"WindMeasurementWithLocation("
                f"datetime={self.datetime}, "
                f"speed={self.speed}, "
                f"heading={self.heading}, "
                f"latitude={self.latitude}, "
                f"longitude={self.longitude})")
