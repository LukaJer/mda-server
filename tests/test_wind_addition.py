import math


def get_real_wind(bike_speed, bike_heading, apparent_wind_speed, apparent_wind_heading):
    v_bx = bike_speed * math.sin(math.radians(bike_heading))
    v_by = bike_speed * math.cos(math.radians(bike_heading))

    v_awx = apparent_wind_speed * math.sin(math.radians(bike_heading + apparent_wind_heading))
    v_awy = apparent_wind_speed * math.cos(math.radians(bike_heading + apparent_wind_heading))

    v_rwx = v_awx + v_bx
    v_rwy = v_awy + v_by

    v_rw = math.sqrt(v_rwx ** 2 + v_rwy ** 2)
    heading_rw = (-math.degrees(math.atan2(v_rwy, v_rwx)) + 450) % 360

    return v_rw, heading_rw


def test_real_wind_calculations() -> None:
    assert get_real_wind(5.0, 0, 0.0, 0) == (5.0, 0.0)
    assert get_real_wind(10.0, 0, 0.0, 0) == (10.0, 0.0)

    assert get_real_wind(10.0, 0, 20.0, 0) == (30.0, 0.0)
    assert get_real_wind(8.0, 0, 2.0, 0) == (10.0, 0.0)

    assert get_real_wind(20.0, 0, 10, 0) == (30, 0.0)
    assert get_real_wind(10.0, 90, 20.0, 180) == (10, 270.0)

    for offset in range(0, 360):
        real_wind_speed, real_wind_heading = get_real_wind(10.0, offset, 6.0, 180)
        assert math.isclose(4.0, real_wind_speed)
        assert math.isclose(offset, real_wind_heading)

    for offset in range(0, 360):
        real_wind_speed, real_wind_heading = get_real_wind(10.0, offset, 4.0, 180)
        assert math.isclose(6, real_wind_speed)
        assert math.isclose(offset, real_wind_heading)

    real_wind_speed, real_wind_heading = get_real_wind(8, 135, 8, 90)
    print(real_wind_heading)
    assert math.isclose(real_wind_speed, 11.313708499)
    assert math.isclose(real_wind_heading, 180)
