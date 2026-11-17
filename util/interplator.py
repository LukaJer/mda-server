from typing import List, Union, Type

import numpy as np
import scipy

from models.gas_measurement_model import GasMeasurement
from models.gas_measurement_with_location import GasMeasurementWithLocation
from models.location_measurement_model import LocationMeasurement
from models.wind_measurement_model import WindMeasurement
from models.wind_measurement_with_location import WindMeasurementWithLocation


class Interpolator:
    MAX_INTERPOLATION_DISTANCE = 5.0

    @staticmethod
    def interpolate_measurements(
            measurements: List[Union[GasMeasurement, WindMeasurement]],
            locations: List[LocationMeasurement],
            interpolated_measurement_type: Union[Type[GasMeasurementWithLocation], Type[WindMeasurementWithLocation]]
    ) -> List[Union[GasMeasurementWithLocation, WindMeasurementWithLocation]]:

        interpolated_measurements = []
        timestamps = [location.datetime.timestamp() for location in locations]
        latitudes = [location.latitude for location in locations]
        longitudes = [location.longitude for location in locations]
        headings = [location.heading for location in locations]
        speeds = [location.speed for location in locations]

        interpolate_latitude = scipy.interpolate.interp1d(timestamps, latitudes, fill_value='extrapolate')
        interpolate_longitude = scipy.interpolate.interp1d(timestamps, longitudes, fill_value='extrapolate')
        interpolate_heading = scipy.interpolate.interp1d(timestamps, headings, fill_value='extrapolate')
        interpolate_speed = scipy.interpolate.interp1d(timestamps, speeds, fill_value='extrapolate')

        for measurement in measurements:
            if Interpolator._measurement_is_within_interpolation_region(locations, measurement):
                gas_measurement_with_location = interpolated_measurement_type.create_from_measurement_and_location(
                    measurement=measurement,
                    heading=float(interpolate_heading(measurement.datetime.timestamp())) % 360,
                    speed=float(interpolate_speed(measurement.datetime.timestamp())),
                    latitude=float(interpolate_latitude(measurement.datetime.timestamp())),
                    longitude=float(interpolate_longitude(measurement.datetime.timestamp()))
                )
                interpolated_measurements.append(gas_measurement_with_location)

        return interpolated_measurements

    @staticmethod
    def _measurement_is_within_interpolation_region(
            locations: List[LocationMeasurement],
            measurement: Union[GasMeasurement, WindMeasurement]
    ) -> bool:
        time_distances = np.abs([(location.datetime - measurement.datetime).total_seconds() for location in locations])
        return time_distances.min() <= Interpolator.MAX_INTERPOLATION_DISTANCE
