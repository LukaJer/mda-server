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
        if not measurements or not locations:
            return []

        # Deduplicate and sort by timestamp so interp1d never divides by zero
        seen_ts = set()
        unique_locs: List[LocationMeasurement] = []
        for loc in sorted(locations, key=lambda l: l.datetime):
            ts = loc.datetime.timestamp()
            if ts not in seen_ts:
                seen_ts.add(ts)
                unique_locs.append(loc)

        timestamps = np.array([loc.datetime.timestamp() for loc in unique_locs], dtype=float)

        if len(unique_locs) == 1:
            loc0 = unique_locs[0]
            ts0 = timestamps[0]
            out = []
            for m in measurements:
                if abs(m.datetime.timestamp() - ts0) <= Interpolator.MAX_INTERPOLATION_DISTANCE:
                    out.append(interpolated_measurement_type.create_from_measurement_and_location(
                        measurement=m,
                        heading=float(loc0.heading) % 360,
                        speed=float(loc0.speed),
                        latitude=float(loc0.latitude),
                        longitude=float(loc0.longitude),
                    ))
            return out

        latitudes = [loc.latitude for loc in unique_locs]
        longitudes = [loc.longitude for loc in unique_locs]
        headings = [loc.heading for loc in unique_locs]
        speeds = [loc.speed for loc in unique_locs]

        interpolate_latitude = scipy.interpolate.interp1d(timestamps, latitudes, fill_value='extrapolate')
        interpolate_longitude = scipy.interpolate.interp1d(timestamps, longitudes, fill_value='extrapolate')
        interpolate_heading = scipy.interpolate.interp1d(timestamps, headings, fill_value='extrapolate')
        interpolate_speed = scipy.interpolate.interp1d(timestamps, speeds, fill_value='extrapolate')

        interpolated_measurements = []
        for measurement in measurements:
            m_ts = measurement.datetime.timestamp()
            if Interpolator._timestamp_is_within_region(timestamps, m_ts):
                lat = float(interpolate_latitude(m_ts))
                lon = float(interpolate_longitude(m_ts))
                hdg = float(interpolate_heading(m_ts)) % 360
                spd = float(interpolate_speed(m_ts))
                if not (np.isfinite(lat) and np.isfinite(lon)):
                    continue
                interpolated_measurements.append(
                    interpolated_measurement_type.create_from_measurement_and_location(
                        measurement=measurement,
                        heading=hdg if np.isfinite(hdg) else 0.0,
                        speed=spd if np.isfinite(spd) else 0.0,
                        latitude=lat,
                        longitude=lon,
                    )
                )

        return interpolated_measurements

    @staticmethod
    def _timestamp_is_within_region(sorted_timestamps: np.ndarray, m_ts: float) -> bool:
        idx = int(np.searchsorted(sorted_timestamps, m_ts))
        best_dist = float('inf')
        if idx < len(sorted_timestamps):
            best_dist = min(best_dist, abs(sorted_timestamps[idx] - m_ts))
        if idx > 0:
            best_dist = min(best_dist, abs(sorted_timestamps[idx - 1] - m_ts))
        return best_dist <= Interpolator.MAX_INTERPOLATION_DISTANCE

    @staticmethod
    def _measurement_is_within_interpolation_region(
            locations: List[LocationMeasurement],
            measurement: Union[GasMeasurement, WindMeasurement]
    ) -> bool:
        if not locations:
            return False
        time_distances = np.abs([(location.datetime - measurement.datetime).total_seconds() for location in locations])
        return time_distances.min() <= Interpolator.MAX_INTERPOLATION_DISTANCE
