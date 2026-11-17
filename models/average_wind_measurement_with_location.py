from datetime import datetime, timedelta
from typing import List

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db
from models.wind_measurement_with_location import WindMeasurementWithLocation


class AverageWindMeasurementWithLocation(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    start_datetime: Mapped[datetime] = mapped_column(DateTime)
    end_datetime: Mapped[datetime] = mapped_column(DateTime)
    duration: Mapped[float] = mapped_column(Float)
    heading: Mapped[float] = mapped_column(Float)
    speed: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    @staticmethod
    def create_from_json(json: dict) -> "AverageWindMeasurementWithLocation":
        pass

    @staticmethod
    def create_from_list(
            measurements: List[WindMeasurementWithLocation],
            t: timedelta
    ) -> "AverageWindMeasurementWithLocation":
        n_measurements = len(measurements)
        middle_latitude = measurements[int(n_measurements/2)].latitude
        middle_longitude = measurements[int(n_measurements / 2)].longitude

        avg_heading = sum(m.heading for m in measurements)/n_measurements
        avg_speed = sum(m.speed for m in measurements)/n_measurements

        return AverageWindMeasurementWithLocation(
            start_datetime=measurements[0].datetime,
            end_datetime=measurements[-1].datetime,
            duration=t.total_seconds(),
            heading=avg_heading,
            speed=avg_speed,
            latitude=middle_latitude,
            longitude=middle_longitude
        )

    @staticmethod
    def calculate_average_measurements(measurements: List[WindMeasurementWithLocation], t: timedelta
                                       ) -> List["AverageWindMeasurementWithLocation"]:
        if len(measurements) <= 1:
            return []

        averaged_measurements = []
        sub_group = [measurements[0]]
        for measurement in measurements[1:]:
            if measurement.datetime - sub_group[0].datetime > t:
                averaged_measurements.append(AverageWindMeasurementWithLocation.create_from_list(sub_group, t))
                sub_group = [measurement]
            else:
                sub_group.append(measurement)
        return averaged_measurements

    def serialize(self) -> dict:
        return {
            "start_datetime": self.start_datetime.isoformat(),
            "end_datetime": self.end_datetime.isoformat(),
            "duration": self.duration,
            "speed": self.speed,
            "heading": self.heading,
            "latitude": self.latitude,
            "longitude": self.longitude
        }

    def __str__(self) -> str:
        return (f"AverageWindMeasurementWithLocation("
                f"start_datetime={self.start_datetime}, "
                f"end_datetime={self.end_datetime}, "
                f"duration={self.duration}, "
                f"speed={self.speed}, "
                f"heading={self.heading}, "
                f"latitude={self.latitude}, "
                f"longitude={self.longitude})")
