import math
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
    MAX_JUMP_SPEED_MPS = 100.0
    MIN_JUMP_ALLOWANCE_M = 50.0
    RECOVERY_CONSECUTIVE_FIXES = 3

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
        return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))

    @classmethod
    def filter_plausible_locations(cls, locations: List[LocationMeasurement]) -> List[LocationMeasurement]:
        """Filter out Null Island, out-of-bounds, non-finite, and implausible jump GPS fixes."""
        filtered: List[LocationMeasurement] = []
        last_valid = None  # (ts, lat, lon)
        candidate = None   # (ts, lat, lon, buffer_list)

        for loc in sorted(locations, key=lambda l: l.datetime):
            try:
                lat = float(loc.latitude)
                lon = float(loc.longitude)
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(lat) and math.isfinite(lon)):
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            if abs(lat) < 1e-6 and abs(lon) < 1e-6:
                continue

            ts = loc.datetime.timestamp()
            if last_valid is None:
                last_valid = (ts, lat, lon)
                filtered.append(loc)
                continue

            prev_ts, prev_lat, prev_lon = last_valid
            dt_s = max(0.0, ts - prev_ts)
            dist_m = cls._haversine_m(prev_lat, prev_lon, lat, lon)
            if dist_m <= max(cls.MIN_JUMP_ALLOWANCE_M, cls.MAX_JUMP_SPEED_MPS * dt_s):
                last_valid = (ts, lat, lon)
                candidate = None
                filtered.append(loc)
                continue

            if candidate is not None:
                c_ts, c_lat, c_lon, buf = candidate
                c_dt_s = max(0.0, ts - c_ts)
                c_dist_m = cls._haversine_m(c_lat, c_lon, lat, lon)
                if c_dist_m <= max(cls.MIN_JUMP_ALLOWANCE_M, cls.MAX_JUMP_SPEED_MPS * c_dt_s):
                    buf.append(loc)
                    if len(buf) >= cls.RECOVERY_CONSECUTIVE_FIXES:
                        filtered.extend(buf)
                        last_valid = (ts, lat, lon)
                        candidate = None
                    else:
                        candidate = (ts, lat, lon, buf)
                    continue

            candidate = (ts, lat, lon, [loc])

        return filtered

    @staticmethod
    def interpolate_measurements(
            measurements: List[Union[GasMeasurement, WindMeasurement]],
            locations: List[LocationMeasurement],
            interpolated_measurement_type: Union[Type[GasMeasurementWithLocation], Type[WindMeasurementWithLocation]]
    ) -> List[Union[GasMeasurementWithLocation, WindMeasurementWithLocation]]:
        if not measurements or not locations:
            return []

        plausible_locs = Interpolator.filter_plausible_locations(locations)
        if not plausible_locs:
            return []

        # Deduplicate and sort by timestamp so interp1d never divides by zero
        seen_ts = set()
        unique_locs: List[LocationMeasurement] = []
        for loc in plausible_locs:
            ts = loc.datetime.timestamp()
            if ts not in seen_ts:
                seen_ts.add(ts)
                unique_locs.append(loc)

        timestamps = np.array([loc.datetime.timestamp() for loc in unique_locs], dtype=float)

        if len(unique_locs) == 1:
            loc0 = unique_locs[0]
            lat = float(loc0.latitude)
            lon = float(loc0.longitude)
            if not (np.isfinite(lat) and np.isfinite(lon)):
                return []
            hdg = float(loc0.heading) % 360
            spd = float(loc0.speed)
            safe_hdg = hdg if np.isfinite(hdg) else 0.0
            safe_spd = spd if np.isfinite(spd) else 0.0
            ts0 = timestamps[0]
            out = []
            for m in measurements:
                if abs(m.datetime.timestamp() - ts0) <= Interpolator.MAX_INTERPOLATION_DISTANCE:
                    out.append(interpolated_measurement_type.create_from_measurement_and_location(
                        measurement=m,
                        heading=safe_hdg,
                        speed=safe_spd,
                        latitude=lat,
                        longitude=lon,
                    ))
            return out

        latitudes = [loc.latitude for loc in unique_locs]
        longitudes = [loc.longitude for loc in unique_locs]
        headings_rad = np.unwrap(np.deg2rad([loc.heading for loc in unique_locs]))
        speeds = [loc.speed for loc in unique_locs]

        interpolate_latitude = scipy.interpolate.interp1d(timestamps, latitudes, fill_value='extrapolate')
        interpolate_longitude = scipy.interpolate.interp1d(timestamps, longitudes, fill_value='extrapolate')
        interpolate_heading_rad = scipy.interpolate.interp1d(timestamps, headings_rad, fill_value='extrapolate')
        interpolate_speed = scipy.interpolate.interp1d(timestamps, speeds, fill_value='extrapolate')

        interpolated_measurements = []
        for measurement in measurements:
            m_ts = measurement.datetime.timestamp()
            if Interpolator._timestamp_is_within_region(timestamps, m_ts):
                lat = float(interpolate_latitude(m_ts))
                lon = float(interpolate_longitude(m_ts))
                hdg = float(np.rad2deg(interpolate_heading_rad(m_ts))) % 360
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
