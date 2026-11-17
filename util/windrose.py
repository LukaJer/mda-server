from datetime import datetime, timedelta
from io import BytesIO

import numpy as np
import matplotlib.pyplot as plt
import requests
from matplotlib import colormaps
from windrose import WindroseAxes


def get_meteo_data(parameters: list, station_id: str, start: str, end: str):
    par_string = '+'.join(parameters)
    url = (f'https://www.meteo.physik.uni-muenchen.de/request-beta/data/'
           f'var={par_string}&'
           f'station={station_id}&'
           f'start={start}&'
           f'end={end}')
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()
    else:
        raise Exception(f"Wind API returned invalid status code: {r.status_code}")


def get_wind_speed_and_direction(start: datetime, end: datetime, station_id: str, error_threshold: float = 500.0):
    parameters = ['wind_speed_30m', 'wind_from_direction_30m']
    data = get_meteo_data(parameters=parameters,
                          station_id=station_id,
                          start=start.strftime('%Y-%m-%dT%H-%M-%S'),
                          end=end.strftime('%Y-%m-%dT%H-%M-%S'))

    wind_speed = data[station_id]['wind_speed_30m']
    wind_direction = data[station_id]['wind_from_direction_30m']

    wind_speed = list(filter(lambda x: x <= error_threshold, wind_speed))
    wind_direction = list(filter(lambda x: x <= error_threshold, wind_direction))
    return wind_speed, wind_direction


def create_windrose(start: datetime, end: datetime, station: str) -> BytesIO:
    start = start.replace(second=0)
    end += timedelta(minutes=1)
    end = end.replace(second=0)

    start -= timedelta(hours=1)
    end -= timedelta(hours=1)

    wind_speed, wind_direction = get_wind_speed_and_direction(start, end, station)

    plt.rcParams.update({'font.size': 50})
    fig = plt.figure()
    ax = WindroseAxes.from_ax()
    ax.bar(wind_direction, wind_speed, normed=True, bins=np.arange(0.01, 8, 1), lw=3, cmap=colormaps["viridis"], opening=0.8)
    ax.grid(True, linewidth=3)
    ax.set_yticklabels([])

    img = BytesIO()
    plt.tight_layout()
    plt.savefig(img, bbox_inches='tight', format='png', dpi=30, transparent=True)
    img.seek(0)
    plt.close()
    return img


def get_average_wind_speed_and_direction(start: datetime, end: datetime, station: str) -> dict:
    start = start.replace(second=0)
    end += timedelta(minutes=1)
    end = end.replace(second=0)

    start -= timedelta(hours=1)
    end -= timedelta(hours=1)

    wind_speed, wind_direction = get_wind_speed_and_direction(start, end, station)

    return {
        "speed": np.mean(wind_speed),
        "direction": np.mean(wind_direction)
    }
