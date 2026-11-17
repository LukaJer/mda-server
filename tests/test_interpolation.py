import datetime

from models.gas_measurement_model import GasMeasurement
from models.gas_measurement_with_location import GasMeasurementWithLocation
from models.location_measurement_model import LocationMeasurement
from util.interplator import Interpolator

locations = [
    LocationMeasurement(
        datetime=datetime.datetime(2024,5,1,10,0,10),
        latitude=0.0,
        longitude=0.0,
        accuracy=0.0,
        heading=0.0,
        speed=10.0
    ),
    LocationMeasurement(
        datetime=datetime.datetime(2024,5,1,10,0,20),
        latitude=10.0,
        longitude=10.0,
        accuracy=0.0,
        heading=100.0,
        speed=10.0
    ),
    LocationMeasurement(
        datetime=datetime.datetime(2024,5,1,10,0,30),
        latitude=0.0,
        longitude=20.0,
        accuracy=0.0,
        heading=50.0,
        speed=10.0
    ),
]

measurements = [
    GasMeasurement(
        datetime=datetime.datetime(2024,5,1,10,0,0),
        type="CH4",
        concentration=7.4,
        unit="ppm"
    ),
    GasMeasurement(
        datetime=datetime.datetime(2024,5,1,10,0,5),
        type="CH4",
        concentration=7.4,
        unit="ppm"
    ),
    GasMeasurement(
        datetime=datetime.datetime(2024,5,1,10,0,15),
        type="CH4",
        concentration=7.4,
        unit="ppm"
    ),
    GasMeasurement(
        datetime=datetime.datetime(2024,5,1,10,0,25),
        type="CH4",
        concentration=7.4,
        unit="ppm"
    ),
    GasMeasurement(
        datetime=datetime.datetime(2024, 5, 1, 10, 0, 35),
        type="CH4",
        concentration=7.4,
        unit="ppm"
    ),
    GasMeasurement(
        datetime=datetime.datetime(2024, 5, 1, 10, 0, 40),
        type="CH4",
        concentration=7.4,
        unit="ppm"
    )
]

expected_interpolated_measurements = [
    GasMeasurementWithLocation(
        datetime=datetime.datetime(2024,5,1,10,0,5),
        type="CH4",
        concentration=7.4,
        unit="ppm",
        heading=310.0,
        latitude=-5.0,
        longitude=-5.0,
    ),
    GasMeasurementWithLocation(
        datetime=datetime.datetime(2024,5,1,10,0,15),
        type="CH4",
        concentration=7.4,
        unit="ppm",
        heading=50.0,
        latitude=5.0,
        longitude=5.0,
    ),
    GasMeasurementWithLocation(
        datetime=datetime.datetime(2024,5,1,10,0,25),
        type="CH4",
        concentration=7.4,
        unit="ppm",
        heading=75.00,
        latitude=5.0,
        longitude=15.0,
    ),
    GasMeasurementWithLocation(
        datetime=datetime.datetime(2024, 5, 1, 10, 0, 35),
        type="CH4",
        concentration=7.4,
        unit="ppm",
        heading=25.0,
        latitude=-5.0,
        longitude=25.0,
    )
]


def test_interpolation_works() -> None:
    interpolated_measurements = Interpolator.interpolate_measurements(measurements, locations)
    for interpolated_measurement, expected_interpolated_measurement in zip(interpolated_measurements,
                                                                           expected_interpolated_measurements):

        assert interpolated_measurement == expected_interpolated_measurement



