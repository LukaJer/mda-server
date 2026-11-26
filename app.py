import bisect
import csv
import datetime
import io
import json
import math
import os
import re
import sqlite3
import subprocess
import threading
import time
from configparser import ConfigParser
from functools import wraps
from typing import List

from flask import Flask, Response, request, jsonify, render_template, redirect, send_file, stream_with_context
import numpy as np
from sqlalchemy import event

from models.average_wind_measurement_with_location import AverageWindMeasurementWithLocation
from models.base_model import db
from models.campaign_model import Campaign
from models.gas_measurement_model import GasMeasurement
from models.gas_measurement_with_location import GasMeasurementWithLocation
from models.location_measurement_model import LocationMeasurement
from models.log_model import Log
from models.wind_measurement_model import WindMeasurement
from models.wind_measurement_with_location import WindMeasurementWithLocation
from util.api_helper import ApiHelper, Request
from util.campaign_statistics import get_campaign_statistics_for_gas, plot_baselines
from util.interplator import Interpolator
from util.timeit import timeit
from util.windrose import create_windrose, get_average_wind_speed_and_direction

measurement_type_look_up = {
    "gas": GasMeasurement,
    "wind": WindMeasurement,
    "location": LocationMeasurement,
    "log": Log,
}


class HttpException(Exception):
    def __init__(self, message: str, error_code: int):
        super().__init__(message)
        self.error_code = error_code


def serialize(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            measurements = func(*args, **kwargs)
            if len(measurements) == 0:
                return {"error": "No measurements available"}, 412
            return jsonify([measurement.serialize() for measurement in measurements])
        except KeyError:
            return {"error": "Invalid measurement type"}, 415
        except HttpException as error:
            return {"error": str(error)}, error.error_code
        except Exception as error:
            return {"error": str(error)}, 500
    return wrapper


DEVICES_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "devices.json")
)
SETTINGS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "settings.json")
)


def default_settings() -> dict:
    return {
        "map": {
            "default_layer": "OSM",
            "cached_layers": ["LocalG"],
            "cache_bbox": {
                "lat_min": 48.06,
                "lat_max": 48.22,
                "lon_min": 11.45,
                "lon_max": 11.72,
            },
            "cache_zooms": [14, 15, 16, 17],
            "tile_source_url": "http://127.0.0.1:8080/tile/{z}/{x}/{y}.png",
            "active_mbtiles": "planet_11.337_48.047_b531ac7e.mbtiles",
            "mbtiles_descriptions": {},
            "color_palette": "default",
        }
    }


MAPS_DIR = os.path.join(os.path.dirname(__file__), "static", "maps")
_MBTILES_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.mbtiles$")
_mbtiles_local = threading.local()


def _get_mbtiles_conn(path: str) -> sqlite3.Connection:
    """Return a cached thread-local read-only sqlite3 connection for path, reopening if mtime_ns changed."""
    cache = getattr(_mbtiles_local, "conns", None)
    if cache is None:
        cache = {}
        _mbtiles_local.conns = cache

    mtime_ns = os.stat(path).st_mtime_ns
    entry = cache.get(path)
    if entry is not None:
        cached_mtime, conn = entry
        if cached_mtime == mtime_ns:
            return conn
        try:
            conn.close()
        except sqlite3.Error:
            pass
        cache.pop(path, None)

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cache[path] = (mtime_ns, conn)
    return conn


def _evict_mbtiles_conn(path: str) -> None:
    """Close and remove any cached thread-local sqlite3 connection for path."""
    cache = getattr(_mbtiles_local, "conns", None)
    if not cache:
        return
    entry = cache.pop(path, None)
    if entry is not None:
        try:
            entry[1].close()
        except sqlite3.Error:
            pass


def _read_mbtiles_info(filename: str, descriptions: dict | None = None) -> dict | None:
    if not _MBTILES_NAME_RE.match(filename):
        return None
    path = os.path.join(MAPS_DIR, filename)
    if not os.path.isfile(path):
        return None
    meta = {}
    tile_count = 0
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            meta = dict(conn.execute("SELECT name, value FROM metadata").fetchall())
            tile_count = int(conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    try:
        size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)
    except OSError:
        size_mb = 0.0

    custom_desc = (descriptions or {}).get(filename)
    meta_desc = (meta.get("description") or "").strip()
    desc = custom_desc if isinstance(custom_desc, str) and custom_desc.strip() else meta_desc
    try:
        minzoom = int(meta.get("minzoom", 0))
    except (TypeError, ValueError):
        minzoom = 0
    try:
        maxzoom = int(meta.get("maxzoom", 14))
    except (TypeError, ValueError):
        maxzoom = 14

    return {
        "filename": filename,
        "name": (meta.get("name") or filename).strip(),
        "description": desc,
        "format": (meta.get("format") or "pbf").strip().lower(),
        "minzoom": minzoom,
        "maxzoom": maxzoom,
        "bounds": meta.get("bounds") or "",
        "tile_count": tile_count,
        "size_mb": size_mb,
    }


def _list_mbtiles(settings_map: dict | None = None) -> list[dict]:
    if not os.path.isdir(MAPS_DIR):
        return []
    descriptions = (settings_map or {}).get("mbtiles_descriptions")
    items = []
    for fname in sorted(os.listdir(MAPS_DIR)):
        info = _read_mbtiles_info(fname, descriptions if isinstance(descriptions, dict) else None)
        if info is not None:
            items.append(info)
    return items


def _is_valid_tile_source_url(url: object) -> bool:
    return (
        isinstance(url, str)
        and url.strip().startswith(("http://", "https://"))
        and "{z}" in url
        and "{x}" in url
        and "{y}" in url
    )


def load_settings() -> dict:
    base = default_settings()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("map"), dict):
            base["map"].update(data["map"])
            if isinstance(data["map"].get("cache_bbox"), dict):
                base["map"]["cache_bbox"].update(data["map"]["cache_bbox"])
    except (OSError, json.JSONDecodeError):
        pass
    return base


def save_settings(settings: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def load_devices_config() -> dict:
    try:
        with open(DEVICES_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {
            "AC32e": {"enabled": True, "name": "Nitrous Oxides", "subtitle": "Envea AC32e", "species": ["NO", "NO2", "NOx"], "interval": 1.0, "stale_after": 15, "offline_after": 120},
            "O342e": {"enabled": True, "name": "Ozone", "subtitle": "Envea O342e", "species": ["O3"], "interval": 1.0, "stale_after": 15, "offline_after": 120},
            "CO12e": {"enabled": True, "name": "Carbon Monoxide", "subtitle": "Envea CO12e", "species": ["CO"], "interval": 1.0, "stale_after": 15, "offline_after": 120},
            "Grimm11D": {"enabled": True, "name": "Particulate Matter", "subtitle": "Grimm 11-D", "species": ["PM10", "PM4", "PM2.5", "PM1"], "interval": 6.0, "stale_after": 25, "offline_after": 120},
            "Picarro": {"enabled": True, "name": "Greenhouse Gases", "subtitle": "Picarro CRDS", "species": ["CH4", "CO2", "H2O"], "interval": 2.0, "stale_after": 15, "offline_after": 120},
            "GPS": {"enabled": True, "name": "GPS Receiver", "subtitle": "Position & Speed (NMEA)", "interval": 1.0, "stale_after": 15, "offline_after": 120},
            "Wind": {"enabled": True, "name": "Lufft Wind Sensor", "subtitle": "Wind Speed & Direction (UMB)", "interval": 1.0, "stale_after": 15, "offline_after": 120},
        }


def get_db_config():
    config = ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
    db_type = config.get('Database', 'type', fallback=None)
    db_location = config.get('Database', 'location', fallback='measurements.db')
    if db_type == 'memory':
        db_uri = 'sqlite:///:memory:'
    else:
        db_uri = f'sqlite:///{db_location}'
    return db_uri


def _nearest_location(t: datetime.datetime, loc_times: List[datetime.datetime],
                      locs: List[LocationMeasurement], max_seconds: float = 15.0):
    """Return the nearest LocationMeasurement within max_seconds of t, or None."""
    if not loc_times:
        return None
    i = bisect.bisect_left(loc_times, t)
    best, best_dt = None, None
    for j in (i - 1, i):
        if 0 <= j < len(loc_times):
            delta = abs((loc_times[j] - t).total_seconds())
            if best_dt is None or delta < best_dt:
                best_dt, best = delta, locs[j]
    if best is not None and best_dt is not None and best_dt <= max_seconds:
        return best
    return None


def _finite_float(val):
    """Return val if it is a finite real number, otherwise None."""
    return val if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val) else None


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['ACCEPT_MEASUREMENT_DATA'] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = get_db_config()
    db.init_app(app)

    live_cache = {
        "gas": {},
        "location": None,
        "wind": None,
        "logs": {},
    }
    live_cache_lock = threading.Lock()
    live_cache_cond = threading.Condition(live_cache_lock)
    live_cache_version = [0]
    startup_max_ids = {"gas": 0, "location": 0, "wind": 0, "log": 0}
    sse_semaphore = threading.BoundedSemaphore(4)
    SSE_MAX_LIFETIME_SECONDS = 90.0

    def _notify_live_update() -> None:
        with live_cache_cond:
            live_cache_version[0] += 1
            live_cache_cond.notify_all()

    def _update_live_cache(measurement_type: str, m) -> None:
        with live_cache_lock:
            if measurement_type == "gas":
                live_cache["gas"][m.type] = {
                    "concentration": m.concentration,
                    "unit": m.unit,
                    "datetime": m.datetime,
                }
            elif measurement_type == "location":
                live_cache["location"] = {
                    "latitude": m.latitude,
                    "longitude": m.longitude,
                    "speed": m.speed,
                    "heading": m.heading,
                    "datetime": m.datetime,
                }
            elif measurement_type == "wind":
                live_cache["wind"] = {
                    "speed": m.speed,
                    "heading": m.heading,
                    "datetime": m.datetime,
                }
            elif measurement_type == "log":
                live_cache["logs"][m.sensor] = {
                    "description": m.description,
                    "datetime": m.datetime,
                }

    @app.post("/measurement/<measurement_type>")
    @timeit
    def post_measurement(measurement_type: str):
        if not request.is_json:
            return {"error": "Request must be JSON"}, 415
        model_cls = measurement_type_look_up.get(measurement_type)
        if model_cls is None:
            return {"error": "Invalid measurement type"}, 415
        payload = request.get_json(silent=True)

        if isinstance(payload, list):
            if not payload:
                return {"error": "Measurement batch list must not be empty"}, 400
            measurements = []
            for idx, item in enumerate(payload):
                if not isinstance(item, dict):
                    return {"error": f"Invalid measurement item at index {idx}: expected JSON object"}, 400
                try:
                    measurements.append(model_cls.create_from_json(item))
                except (KeyError, ValueError, TypeError) as e:
                    return {"error": f"Invalid measurement payload at index {idx}: {e}"}, 400

            if measurement_type != "log" and not app.config.get("ACCEPT_MEASUREMENT_DATA", True):
                for m in measurements:
                    _update_live_cache(measurement_type, m)
                _notify_live_update()
                return {"status": "paused", "count": len(measurements)}, 200

            try:
                db.session.add_all(measurements)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                return {"error": f"Database error: {e}"}, 500
            for m in measurements:
                _update_live_cache(measurement_type, m)
            _notify_live_update()
            return {"status": "ok", "count": len(measurements)}, 200

        if not isinstance(payload, dict):
            return {"error": "Request must be a JSON object or non-empty list of objects"}, 400
        try:
            measurement = model_cls.create_from_json(payload)
        except (KeyError, ValueError, TypeError) as e:
            return {"error": f"Invalid measurement payload: {e}"}, 400

        if measurement_type != "log" and not app.config.get("ACCEPT_MEASUREMENT_DATA", True):
            _update_live_cache(measurement_type, measurement)
            _notify_live_update()
            return {"paused": True, "message": "Measurement recording is paused"}, 200

        try:
            db.session.add(measurement)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return {"error": f"Database error: {e}"}, 500
        _update_live_cache(measurement_type, measurement)
        _notify_live_update()
        return {"success": "Successfully added measurement to database"}, 201

    @app.get("/measurement/log")
    @timeit
    @serialize
    def get_logs():
        log_request = Request(request.args)
        logs = Log.get_data(log_request)
        return logs

    @app.get("/measurement/location")
    @timeit
    @serialize
    def get_location_measurements():
        measurement_request = Request(request.args)
        measurements = LocationMeasurement.get_data(measurement_request)
        return Interpolator.filter_plausible_locations(measurements)

    @app.get("/measurement/wind")
    @timeit
    @serialize
    def get_wind_measurements():
        measurement_request = Request(request.args)
        measurements = WindMeasurement.get_data(measurement_request)

        if not measurement_request.with_location or not measurements:
            return measurements

        buf = datetime.timedelta(seconds=Interpolator.MAX_INTERPOLATION_DISTANCE)
        locations = LocationMeasurement.get_data(
            measurement_request,
            apply_limit=False,
            start_datetime=measurements[0].datetime - buf,
            end_datetime=measurements[-1].datetime + buf,
        )
        measurements_with_locations = Interpolator.interpolate_measurements(
            measurements, locations, WindMeasurementWithLocation)

        if not measurement_request.t:
            return measurements_with_locations
        return AverageWindMeasurementWithLocation.calculate_average_measurements(
            measurements_with_locations, measurement_request.t)

    @app.get("/measurement/gas")
    @timeit
    @serialize
    def get_gas_measurements():
        measurement_request = Request(request.args)
        measurements = GasMeasurement.get_data(measurement_request)

        if not measurement_request.with_location or not measurements:
            return measurements

        buf = datetime.timedelta(seconds=Interpolator.MAX_INTERPOLATION_DISTANCE)
        locations = LocationMeasurement.get_data(
            measurement_request,
            apply_limit=False,
            start_datetime=measurements[0].datetime - buf,
            end_datetime=measurements[-1].datetime + buf,
        )

        measurements_with_locations = Interpolator.interpolate_measurements(
            measurements, locations, GasMeasurementWithLocation)
        return measurements_with_locations

    @app.get('/campaign/<int:campaign_id>/span')
    def campaign_span(campaign_id: int):
        c = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalar()
        if not c:
            return {"error": "Campaign not found"}, 404
        end_dt = c.end or datetime.datetime.now()
        min_dt, max_dt = db.session.execute(
            db.select(db.func.min(GasMeasurement.datetime), db.func.max(GasMeasurement.datetime))
            .where(GasMeasurement.datetime >= c.start)
            .where(GasMeasurement.datetime <= end_dt)
        ).one()
        span = (max_dt - min_dt).total_seconds() if (min_dt and max_dt) else 0.0
        return jsonify({"span_seconds": span, "short_data": span < 120.0})

    @app.route('/map/<campaign_id>')
    def campaign_map(campaign_id: int):
        show_campaign = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalar()
        if not show_campaign:
            return redirect('/campaign')
        end_dt = show_campaign.end or datetime.datetime.now()
        min_dt, max_dt = db.session.execute(
            db.select(db.func.min(GasMeasurement.datetime), db.func.max(GasMeasurement.datetime))
            .where(GasMeasurement.datetime >= show_campaign.start)
            .where(GasMeasurement.datetime <= end_dt)
        ).one()
        data_span = (max_dt - min_dt).total_seconds() if (min_dt and max_dt) else 0.0
        if show_campaign.end is None:
            available_species = None
        else:
            available_species = db.session.execute(
                db.select(GasMeasurement.type)
                .where(GasMeasurement.datetime >= show_campaign.start)
                .where(GasMeasurement.datetime <= end_dt)
                .distinct()
            ).scalars().all()
        m_settings = dict(load_settings()["map"])
        mbtiles_list = _list_mbtiles(m_settings)
        active_name = m_settings.get("active_mbtiles") or ""
        active_info = next((x for x in mbtiles_list if x["filename"] == active_name), None)
        if active_info is None and mbtiles_list:
            active_info = mbtiles_list[0]
        m_settings["active_mbtiles_info"] = active_info
        tiles_root = os.path.join(os.path.dirname(__file__), "static", "tiles")
        m_settings["has_local_png"] = os.path.isdir(os.path.join(tiles_root, "osm"))
        m_settings["has_local_gray_png"] = os.path.isdir(os.path.join(tiles_root, "osm_grayscale"))

        return render_template(
            'index.html',
            campaign=show_campaign,
            short_data=(data_span < 120.0),
            available_species=available_species,
            map_settings=m_settings,
        )

    @app.route('/campaign',  methods=['POST', 'GET'])
    def campaign():
        if request.method == 'GET':
            now = datetime.datetime.now()
            campaigns = db.session.execute(
                db.select(Campaign)
                .order_by(Campaign.start.desc())
            ).scalars().all()
            short_campaigns = set()
            for c in campaigns:
                end_dt = c.end or now
                min_dt, max_dt = db.session.execute(
                    db.select(db.func.min(GasMeasurement.datetime), db.func.max(GasMeasurement.datetime))
                    .where(GasMeasurement.datetime >= c.start)
                    .where(GasMeasurement.datetime <= end_dt)
                ).one()
                span = (max_dt - min_dt).total_seconds() if (min_dt and max_dt) else 0.0
                if span < 120.0:
                    short_campaigns.add(c.id)
            return render_template(
                'campaigns.html',
                campaigns=campaigns,
                short_campaigns=short_campaigns,
                devices_config=load_devices_config(),
                settings=load_settings(),
                now=now,
                enable_measurements=app.config["ACCEPT_MEASUREMENT_DATA"])
        else:
            campaign_id = int(request.form.get('id') or 0)
            start = ApiHelper.get_datetime_if_set(request.form['start'])
            if start is None:
                return {"error": "Invalid start date/time"}, 400
            end = ApiHelper.get_datetime_if_set(request.form.get('end', ''))
            name = ApiHelper.get_post_if_set(request.form["name"])
            author = ApiHelper.get_post_if_set(request.form["author"])
            description = ApiHelper.get_post_if_set(request.form["description"])

            if campaign_id:
                edit_campaign = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalar()
                if not edit_campaign:
                    return {"error": "Campaign not found"}, 404

                edit_campaign.start = start
                edit_campaign.end = end
                edit_campaign.name = name
                edit_campaign.author = author
                edit_campaign.description = description

                db.session.commit()
            else:
                new_campaign = Campaign(
                    start=start,
                    end=end,
                    name=name,
                    author=author,
                    description=description
                )
                db.session.add(new_campaign)
                db.session.commit()

            return redirect('/campaign')

    @app.post('/campaign/start')
    def campaign_start():
        now = datetime.datetime.now().replace(microsecond=0)
        name = ApiHelper.get_post_if_set(request.form.get('name')) or f"Campaign {now.strftime('%Y.%m.%d %H:%M')}"
        author = ApiHelper.get_post_if_set(request.form.get('author'))
        description = ApiHelper.get_post_if_set(request.form.get('description'))

        new_campaign = Campaign(
            start=now,
            end=None,
            name=name,
            author=author,
            description=description,
        )
        db.session.add(new_campaign)
        db.session.commit()
        return redirect('/campaign')

    @app.post('/campaign/<int:campaign_id>/stop')
    def campaign_stop(campaign_id: int):
        active_campaign = db.session.execute(
            db.select(Campaign).where(Campaign.id == campaign_id)
        ).scalar()
        if active_campaign and active_campaign.end is None:
            active_campaign.end = datetime.datetime.now().replace(microsecond=0)
            db.session.commit()
        return redirect('/campaign')

    def _build_live_payload(include_db: bool = True) -> dict:
        now = datetime.datetime.now()
        gas_data = {}
        loc_data = None
        wind_data = None
        logs_data = {}

        if include_db:
            # Scan only the most recent rows since server start
            recent_gases = db.session.execute(
                db.select(GasMeasurement)
                .where(GasMeasurement.id > startup_max_ids["gas"])
                .order_by(GasMeasurement.id.desc())
                .limit(300)
            ).scalars().all()
            for g in recent_gases:
                if g.type not in gas_data:
                    gas_data[g.type] = {
                        "concentration": _finite_float(g.concentration),
                        "unit": g.unit,
                        "datetime": g.datetime.isoformat(),
                        "age_seconds": max(0.0, (now - g.datetime).total_seconds()),
                    }

            latest_loc = db.session.execute(
                db.select(LocationMeasurement)
                .where(LocationMeasurement.id > startup_max_ids["location"])
                .order_by(LocationMeasurement.id.desc())
                .limit(1)
            ).scalar()
            if latest_loc:
                loc_data = {
                    "latitude": _finite_float(latest_loc.latitude),
                    "longitude": _finite_float(latest_loc.longitude),
                    "speed": _finite_float(latest_loc.speed),
                    "heading": _finite_float(latest_loc.heading),
                    "datetime": latest_loc.datetime.isoformat(),
                    "age_seconds": max(0.0, (now - latest_loc.datetime).total_seconds()),
                }

            latest_wind = db.session.execute(
                db.select(WindMeasurement)
                .where(WindMeasurement.id > startup_max_ids["wind"])
                .order_by(WindMeasurement.id.desc())
                .limit(1)
            ).scalar()
            if latest_wind:
                wind_data = {
                    "speed": _finite_float(latest_wind.speed),
                    "heading": _finite_float(latest_wind.heading),
                    "datetime": latest_wind.datetime.isoformat(),
                    "age_seconds": max(0.0, (now - latest_wind.datetime).total_seconds()),
                }

            recent_logs = db.session.execute(
                db.select(Log)
                .where(Log.id > startup_max_ids["log"])
                .order_by(Log.id.desc())
                .limit(100)
            ).scalars().all()
            for lg in recent_logs:
                if lg.sensor not in logs_data:
                    logs_data[lg.sensor] = {
                        "description": lg.description,
                        "datetime": lg.datetime.isoformat(),
                        "age_seconds": max(0.0, (now - lg.datetime).total_seconds()),
                    }

        # Overlay live_cache so paused instruments still show live readouts
        with live_cache_lock:
            for g_type, cached in live_cache["gas"].items():
                db_entry = gas_data.get(g_type)
                if db_entry is None or cached["datetime"].isoformat() >= db_entry["datetime"]:
                    gas_data[g_type] = {
                        "concentration": _finite_float(cached["concentration"]),
                        "unit": cached["unit"],
                        "datetime": cached["datetime"].isoformat(),
                        "age_seconds": max(0.0, (now - cached["datetime"]).total_seconds()),
                    }
            if live_cache["location"] is not None:
                c_loc = live_cache["location"]
                if loc_data is None or c_loc["datetime"].isoformat() >= loc_data["datetime"]:
                    loc_data = {
                        "latitude": _finite_float(c_loc["latitude"]),
                        "longitude": _finite_float(c_loc["longitude"]),
                        "speed": _finite_float(c_loc["speed"]),
                        "heading": _finite_float(c_loc["heading"]),
                        "datetime": c_loc["datetime"].isoformat(),
                        "age_seconds": max(0.0, (now - c_loc["datetime"]).total_seconds()),
                    }
            if live_cache["wind"] is not None:
                c_wind = live_cache["wind"]
                if wind_data is None or c_wind["datetime"].isoformat() >= wind_data["datetime"]:
                    wind_data = {
                        "speed": _finite_float(c_wind["speed"]),
                        "heading": _finite_float(c_wind["heading"]),
                        "datetime": c_wind["datetime"].isoformat(),
                        "age_seconds": max(0.0, (now - c_wind["datetime"]).total_seconds()),
                    }
            for sensor, c_log in live_cache["logs"].items():
                db_log = logs_data.get(sensor)
                if db_log is None or c_log["datetime"].isoformat() >= db_log["datetime"]:
                    logs_data[sensor] = {
                        "description": c_log["description"],
                        "datetime": c_log["datetime"].isoformat(),
                        "age_seconds": max(0.0, (now - c_log["datetime"]).total_seconds()),
                    }

        return {
            "server_time": now.isoformat(),
            "paused": not app.config.get("ACCEPT_MEASUREMENT_DATA", True),
            "gas": gas_data,
            "location": loc_data,
            "wind": wind_data,
            "logs": logs_data,
        }

    @app.get('/api/live')
    def api_live():
        return jsonify(_build_live_payload(include_db=True))

    @app.get('/api/live/stream')
    def api_live_stream():
        if not sse_semaphore.acquire(blocking=False):
            return {"error": "Too many live stream clients"}, 503

        once = request.args.get('once', '').lower() in ('1', 'true', 'yes')

        def event_stream():
            try:
                try:
                    snapshot = _build_live_payload(include_db=True)
                finally:
                    db.session.remove()
                with live_cache_cond:
                    last_version = live_cache_version[0]
                yield f"data: {json.dumps(snapshot, allow_nan=False)}\n\n"
                if once:
                    return

                deadline = time.monotonic() + SSE_MAX_LIFETIME_SECONDS
                while time.monotonic() < deadline:
                    wait_timeout = min(2.0, max(0.0, deadline - time.monotonic()))
                    with live_cache_cond:
                        if live_cache_version[0] == last_version:
                            live_cache_cond.wait(timeout=wait_timeout)
                        cur_version = live_cache_version[0]
                    if cur_version != last_version:
                        time.sleep(0.05)
                        with live_cache_cond:
                            last_version = live_cache_version[0]
                    if time.monotonic() >= deadline:
                        break
                    yield f"data: {json.dumps(_build_live_payload(include_db=False), allow_nan=False)}\n\n"
            except GeneratorExit:
                return
            finally:
                sse_semaphore.release()

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get('/api/logs')
    def api_logs():
        try:
            limit = min(max(int(request.args.get('limit', 100)), 1), 500)
        except ValueError:
            limit = 100
        sensor_filter = (request.args.get('sensor') or '').strip()
        errors_only = request.args.get('errors_only', '').lower() in ('1', 'true', 'yes')

        q = db.select(Log).order_by(Log.id.desc())
        if sensor_filter:
            q = q.where(Log.sensor == sensor_filter)
        if errors_only:
            q = q.where(
                db.or_(
                    Log.description.ilike('%error%'),
                    Log.description.ilike('%fail%'),
                    Log.description.ilike('%timeout%'),
                    Log.description.ilike('%exception%'),
                )
            )
        rows = db.session.execute(q.limit(limit)).scalars().all()

        recent_sensors = sorted({
            s for s in db.session.execute(
                db.select(Log.sensor).order_by(Log.id.desc()).limit(300)
            ).scalars().all()
            if s
        })

        db_size_mb = None
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if db_uri.startswith("sqlite:///") and db_uri != "sqlite:///:memory:":
            rel_path = db_uri[len("sqlite:///"):]
            candidates = [
                rel_path,
                os.path.join(app.instance_path, rel_path),
                os.path.join(os.path.dirname(__file__), "instance", rel_path),
            ]
            for p in candidates:
                if os.path.exists(p):
                    db_size_mb = round(os.path.getsize(p) / (1024 * 1024), 2)
                    break

        return jsonify({
            "recording_enabled": app.config.get("ACCEPT_MEASUREMENT_DATA", True),
            "db_size_mb": db_size_mb,
            "sensors": recent_sensors,
            "logs": [
                {
                    "id": lg.id,
                    "datetime": lg.datetime.isoformat(),
                    "sensor": lg.sensor,
                    "description": lg.description,
                }
                for lg in rows
            ],
        })

    terminal_lock = threading.Lock()
    terminal_state = {
        "cwd": os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    }

    @app.post('/api/terminal')
    def api_terminal():
        if os.environ.get("MDA_ENABLE_TERMINAL") != "1" and request.remote_addr not in ("127.0.0.1", "::1"):
            return {"error": "Terminal access is disabled"}, 403
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return {"error": "Request must be a JSON object"}, 400
        raw_cmd = payload.get('command')
        if raw_cmd is not None and not isinstance(raw_cmd, str):
            return {"error": "Command must be a string"}, 400
        cmd = (raw_cmd or '').strip()
        if not cmd:
            return jsonify({"cwd": terminal_state["cwd"], "exit_code": 0, "stdout": "", "stderr": ""})

        with terminal_lock:
            cwd = terminal_state["cwd"]
            if cmd == "cd" or cmd.startswith("cd "):
                target = cmd[2:].strip() or os.path.expanduser("~")
                new_dir = os.path.abspath(os.path.join(cwd, os.path.expanduser(target)))
                if os.path.isdir(new_dir):
                    terminal_state["cwd"] = new_dir
                    return jsonify({"cwd": new_dir, "exit_code": 0, "stdout": "", "stderr": ""})
                return jsonify({"cwd": cwd, "exit_code": 1, "stdout": "", "stderr": f"cd: no such directory: {target}\n"})

            try:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return jsonify({
                    "cwd": cwd,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                })
            except subprocess.TimeoutExpired:
                return jsonify({"cwd": cwd, "exit_code": 124, "stdout": "", "stderr": "Command timed out after 15s\n"})
            except Exception as e:
                return jsonify({"cwd": cwd, "exit_code": 1, "stdout": "", "stderr": f"{e}\n"})

    @app.get('/api/settings')
    def api_get_settings():
        return jsonify(load_settings())

    @app.post('/api/settings')
    def api_post_settings():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return {"error": "Request must be a JSON object"}, 400

        current = load_settings()
        if isinstance(payload.get("map"), dict):
            m = payload["map"]
            valid_layers = {"OSM", "Local", "LocalG", "MBTiles", "MBTilesG"}
            if m.get("default_layer") in valid_layers:
                current["map"]["default_layer"] = m["default_layer"]
            valid_palettes = {"default", "plasma", "turbo"}
            if "color_palette" in m:
                if m.get("color_palette") in valid_palettes:
                    current["map"]["color_palette"] = m["color_palette"]
                else:
                    return {"error": "Invalid color_palette"}, 400
            if "active_mbtiles" in m:
                am = m.get("active_mbtiles")
                if am == "" or (isinstance(am, str) and _MBTILES_NAME_RE.match(am)):
                    current["map"]["active_mbtiles"] = am
                else:
                    return {"error": "Invalid active_mbtiles filename"}, 400
            if isinstance(m.get("mbtiles_descriptions"), dict):
                descs = dict(current["map"].get("mbtiles_descriptions") or {})
                for k, v in m["mbtiles_descriptions"].items():
                    if isinstance(k, str) and _MBTILES_NAME_RE.match(k) and isinstance(v, str):
                        descs[k] = v.strip()
                current["map"]["mbtiles_descriptions"] = descs
            if isinstance(m.get("cached_layers"), list):
                current["map"]["cached_layers"] = [
                    l for l in m["cached_layers"] if l in ("Local", "LocalG")
                ]
            if isinstance(m.get("cache_bbox"), dict):
                try:
                    bbox = m["cache_bbox"]
                    current["map"]["cache_bbox"] = {
                        "lat_min": float(bbox["lat_min"]),
                        "lat_max": float(bbox["lat_max"]),
                        "lon_min": float(bbox["lon_min"]),
                        "lon_max": float(bbox["lon_max"]),
                    }
                except (KeyError, TypeError, ValueError):
                    return {"error": "Invalid cache_bbox coordinates"}, 400
            if isinstance(m.get("cache_zooms"), list):
                try:
                    zooms = sorted({
                        int(z) for z in m["cache_zooms"] if 1 <= int(z) <= 19
                    })
                    current["map"]["cache_zooms"] = zooms
                except (TypeError, ValueError):
                    return {"error": "Invalid cache_zooms"}, 400
            if "tile_source_url" in m:
                t_url = (m.get("tile_source_url") or "").strip() if isinstance(m.get("tile_source_url"), str) else ""
                if not _is_valid_tile_source_url(t_url):
                    return {"error": "Tile source URL must start with http:// or https:// and include {z}, {x}, {y}"}, 400
                current["map"]["tile_source_url"] = t_url

        save_settings(current)
        return jsonify({"status": "saved", "settings": current})

    @app.get('/api/offline-maps')
    def api_offline_maps():
        m_settings = load_settings()["map"]
        return jsonify({
            "active_mbtiles": m_settings.get("active_mbtiles") or "",
            "maps": _list_mbtiles(m_settings),
        })

    @app.get('/tiles/mbtiles/<map_name>/<int:z>/<int:x>/<int:y>.<ext>')
    def serve_mbtiles_tile(map_name: str, z: int, x: int, y: int, ext: str):
        if not _MBTILES_NAME_RE.match(map_name):
            return {"error": "Invalid map name"}, 400
        path = os.path.join(MAPS_DIR, map_name)
        if not os.path.isfile(path):
            return {"error": "Map not found"}, 404
        tms_y = (1 << z) - 1 - y
        try:
            conn = _get_mbtiles_conn(path)
            row = conn.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                (z, x, tms_y),
            ).fetchone()
        except sqlite3.Error as e:
            _evict_mbtiles_conn(path)
            return {"error": f"MBTiles read error: {e}"}, 500

        if not row or row[0] is None:
            return ("", 404)

        data = bytes(row[0])
        ext_lower = ext.lower()
        mime_map = {
            "pbf": "application/x-protobuf",
            "mvt": "application/x-protobuf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }
        mimetype = mime_map.get(ext_lower, "application/octet-stream")
        resp = Response(data, status=200, mimetype=mimetype)
        if ext_lower in ("pbf", "mvt") and len(data) >= 2 and data[:2] == b"\x1f\x8b":
            resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    @app.get('/api/map-tiles/status')
    def api_map_tiles_status():
        tiles_root = os.path.join(os.path.dirname(__file__), "static", "tiles")
        layers = {}
        for label, folder in (("Local", "osm"), ("LocalG", "osm_grayscale")):
            folder_path = os.path.join(tiles_root, folder)
            count = 0
            total_bytes = 0
            zooms = {}
            if os.path.isdir(folder_path):
                for z_entry in sorted(os.listdir(folder_path), key=lambda s: int(s) if s.isdigit() else 999):
                    z_path = os.path.join(folder_path, z_entry)
                    if not os.path.isdir(z_path) or not z_entry.isdigit():
                        continue
                    z_count = 0
                    z_bytes = 0
                    for root_dir, _, files in os.walk(z_path):
                        for fname in files:
                            if fname.endswith(".png"):
                                z_count += 1
                                try:
                                    z_bytes += os.path.getsize(os.path.join(root_dir, fname))
                                except OSError:
                                    pass
                    if z_count > 0:
                        zooms[z_entry] = {
                            "count": z_count,
                            "size_mb": round(z_bytes / (1024 * 1024), 2),
                        }
                    count += z_count
                    total_bytes += z_bytes
            layers[label] = {
                "count": count,
                "size_mb": round(total_bytes / (1024 * 1024), 2),
                "zooms": zooms,
            }
        return jsonify({"layers": layers})

    tile_cache_lock = threading.Lock()
    tile_cache_state = {
        "running": False,
        "cancel": False,
        "total": 0,
        "done": 0,
        "downloaded": 0,
        "failed": 0,
        "message": "Idle",
    }

    def _deg2num(lat_deg: float, lon_deg: float, zoom: int):
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return xtile, ytile

    def _tile_ranges(bbox: dict, zooms: list):
        ranges = []
        for z in zooms:
            x0, y1 = _deg2num(bbox["lat_min"], bbox["lon_min"], z)
            x1, y0 = _deg2num(bbox["lat_max"], bbox["lon_max"], z)
            xmin, xmax = min(x0, x1), max(x0, x1)
            ymin, ymax = min(y0, y1), max(y0, y1)
            ranges.append((z, xmin, xmax, ymin, ymax))
        return ranges

    @app.post('/api/map-tiles/cache')
    def api_map_tiles_cache():
        import hashlib as _hashlib
        import time as _time
        import requests as _requests
        from PIL import Image

        OSM_BLOCKED_TILE_SHA256 = "109722facb0459991ce2c9983b3ae40232e84be7273aaa454071b50049e3d88b"

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return {"error": "Request must be a JSON object"}, 400
        m = payload.get("map")
        if m is None:
            m = load_settings()["map"]
        elif not isinstance(m, dict):
            return {"error": "Invalid map configuration"}, 400
        tile_source_url = (m.get("tile_source_url") or load_settings()["map"].get("tile_source_url") or "").strip()
        if not _is_valid_tile_source_url(tile_source_url):
            return {"error": "Tile source URL must start with http:// or https:// and include {z}, {x}, {y}"}, 400
        layers = [l for l in m.get("cached_layers", []) if l in ("Local", "LocalG")]
        if not layers:
            return {"error": "Select at least one offline layer to cache"}, 400
        try:
            bbox = {
                "lat_min": float(m["cache_bbox"]["lat_min"]),
                "lat_max": float(m["cache_bbox"]["lat_max"]),
                "lon_min": float(m["cache_bbox"]["lon_min"]),
                "lon_max": float(m["cache_bbox"]["lon_max"]),
            }
            zooms = sorted({int(z) for z in m.get("cache_zooms", []) if 1 <= int(z) <= 19})
        except (KeyError, TypeError, ValueError):
            return {"error": "Invalid bounding box or zoom levels"}, 400
        if not (
            math.isfinite(bbox["lat_min"]) and math.isfinite(bbox["lat_max"])
            and math.isfinite(bbox["lon_min"]) and math.isfinite(bbox["lon_max"])
            and -85.0511 <= bbox["lat_min"] <= bbox["lat_max"] <= 85.0511
            and -180.0 <= bbox["lon_min"] <= bbox["lon_max"] <= 180.0
        ):
            return {"error": "Bounding box coordinates out of valid Web Mercator bounds"}, 400
        if not zooms:
            return {"error": "Select at least one zoom level"}, 400

        ranges = _tile_ranges(bbox, zooms)
        total_tiles = sum((xmax - xmin + 1) * (ymax - ymin + 1) for _, xmin, xmax, ymin, ymax in ranges)
        if total_tiles > 50000:
            return {"error": f"Too many tiles ({total_tiles:,}); reduce zoom or area (max 50,000 tiles)"}, 400

        with tile_cache_lock:
            if tile_cache_state["running"]:
                return {"error": "Tile download already running"}, 409
            tile_cache_state.update({
                "running": True,
                "cancel": False,
                "total": total_tiles * len(layers),
                "done": 0,
                "downloaded": 0,
                "failed": 0,
                "message": "Downloading tiles...",
            })

        tiles_root = os.path.join(os.path.dirname(__file__), "static", "tiles")
        want_local = "Local" in layers
        want_gray = "LocalG" in layers

        def worker():
            headers = {"User-Agent": "EnvBike-MDA/1.0 (offline field cache)"}
            session = _requests.Session()
            session.headers.update(headers)
            try:
                for z, xmin, xmax, ymin, ymax in ranges:
                    for x in range(xmin, xmax + 1):
                        for y in range(ymin, ymax + 1):
                            with tile_cache_lock:
                                if tile_cache_state["cancel"]:
                                    tile_cache_state["message"] = "Cancelled"
                                    return
                            color_path = os.path.join(tiles_root, "osm", str(z), str(x), f"{y}.png")
                            gray_path = os.path.join(tiles_root, "osm_grayscale", str(z), str(x), f"{y}.png")
                            need_color = want_local and not os.path.isfile(color_path)
                            need_gray = want_gray and not os.path.isfile(gray_path)

                            if need_color or need_gray:
                                tile_ok = False
                                try:
                                    img_bytes = None
                                    if os.path.isfile(color_path):
                                        with open(color_path, "rb") as f:
                                            img_bytes = f.read()
                                    else:
                                        _time.sleep(0.06)
                                        tile_url = (
                                            tile_source_url
                                            .replace("{z}", str(z))
                                            .replace("{x}", str(x))
                                            .replace("{y}", str(y))
                                        )
                                        r = session.get(tile_url, timeout=10)
                                        if r.status_code in (403, 429):
                                            with tile_cache_lock:
                                                tile_cache_state["failed"] += (1 if need_color else 0) + (1 if need_gray else 0)
                                                tile_cache_state["done"] += len(layers)
                                                tile_cache_state["message"] = f"Blocked/Rate-limited by tile server (HTTP {r.status_code})"
                                            return
                                        ctype = r.headers.get("Content-Type", "").lower()
                                        if r.status_code == 200 and ctype.startswith("image/"):
                                            if _hashlib.sha256(r.content).hexdigest() == OSM_BLOCKED_TILE_SHA256:
                                                with tile_cache_lock:
                                                    tile_cache_state["failed"] += (1 if need_color else 0) + (1 if need_gray else 0)
                                                    tile_cache_state["done"] += len(layers)
                                                    tile_cache_state["message"] = "Tile server returned an 'Access blocked' placeholder tile"
                                                return
                                            img_bytes = r.content

                                    if img_bytes:
                                        with Image.open(io.BytesIO(img_bytes)) as im:
                                            im.load()
                                            if need_color:
                                                os.makedirs(os.path.dirname(color_path), exist_ok=True)
                                                tmp_color = f"{color_path}.tmp"
                                                with open(tmp_color, "wb") as f:
                                                    f.write(img_bytes)
                                                os.replace(tmp_color, color_path)
                                            if need_gray:
                                                os.makedirs(os.path.dirname(gray_path), exist_ok=True)
                                                tmp_gray = f"{gray_path}.tmp"
                                                gray_im = im.convert("L")
                                                gray_im.save(tmp_gray, format="PNG")
                                                os.replace(tmp_gray, gray_path)
                                        tile_ok = True
                                except Exception:
                                    tile_ok = False

                                with tile_cache_lock:
                                    delta = (1 if need_color else 0) + (1 if need_gray else 0)
                                    if tile_ok:
                                        tile_cache_state["downloaded"] += delta
                                    else:
                                        tile_cache_state["failed"] += delta

                            with tile_cache_lock:
                                tile_cache_state["done"] += len(layers)
                with tile_cache_lock:
                    tile_cache_state["message"] = "Done"
            except Exception as e:
                with tile_cache_lock:
                    tile_cache_state["message"] = f"Error: {e}"
            finally:
                session.close()
                with tile_cache_lock:
                    tile_cache_state["running"] = False

        threading.Thread(target=worker, daemon=True).start()
        return jsonify({"status": "started", "total": total_tiles * len(layers)})

    @app.get('/api/map-tiles/cache/status')
    def api_map_tiles_cache_status():
        with tile_cache_lock:
            return jsonify(dict(tile_cache_state))

    @app.post('/api/map-tiles/cache/cancel')
    def api_map_tiles_cache_cancel():
        with tile_cache_lock:
            tile_cache_state["cancel"] = True
            return jsonify({"status": "cancelling"})

    @app.post('/api/map-tiles/clear')
    def api_map_tiles_clear():
        import shutil

        with tile_cache_lock:
            if tile_cache_state["running"]:
                return {"error": "Cannot clear cache while tile download is running"}, 409

        payload = request.get_json(silent=True)
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return {"error": "Invalid JSON payload"}, 400

        raw_layers = payload.get("layers")
        if not isinstance(raw_layers, list):
            return {"error": "Select at least one layer to clear"}, 400
        layers = [l for l in raw_layers if l in ("Local", "LocalG")]
        if not layers:
            return {"error": "Select at least one valid layer (Local or LocalG)"}, 400

        raw_zooms = payload.get("zooms")
        zooms = None
        if raw_zooms is not None:
            if not isinstance(raw_zooms, list):
                return {"error": "Invalid zoom levels"}, 400
            if len(raw_zooms) > 0:
                try:
                    zooms = sorted({int(z) for z in raw_zooms if 1 <= int(z) <= 19})
                except (TypeError, ValueError):
                    return {"error": "Invalid zoom levels"}, 400
                if not zooms:
                    return {"error": "Invalid zoom levels"}, 400

        folder_map = {"Local": "osm", "LocalG": "osm_grayscale"}
        tiles_root = os.path.join(os.path.dirname(__file__), "static", "tiles")
        deleted_tiles = 0
        freed_bytes = 0

        for label in layers:
            layer_dir = os.path.join(tiles_root, folder_map[label])
            if not os.path.isdir(layer_dir):
                continue
            target_dirs = (
                [os.path.join(layer_dir, str(z)) for z in zooms]
                if zooms is not None
                else [layer_dir]
            )
            for tdir in target_dirs:
                if not os.path.isdir(tdir):
                    continue
                for root_dir, _, files in os.walk(tdir):
                    for fname in files:
                        if fname.endswith(".png"):
                            deleted_tiles += 1
                            try:
                                freed_bytes += os.path.getsize(os.path.join(root_dir, fname))
                            except OSError:
                                pass
                shutil.rmtree(tdir, ignore_errors=True)
            if os.path.isdir(layer_dir) and not os.listdir(layer_dir):
                try:
                    os.rmdir(layer_dir)
                except OSError:
                    pass

        return jsonify({
            "status": "cleared",
            "deleted_tiles": deleted_tiles,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        })

    @app.get('/campaign/<int:campaign_id>/download')
    def campaign_download(campaign_id: int):
        target = db.session.execute(
            db.select(Campaign).where(Campaign.id == campaign_id)
        ).scalar()
        if not target:
            return {"error": "Campaign not found"}, 404

        start_dt = target.start
        end_dt = target.end or datetime.datetime.now()
        fmt = request.args.get('format', 'json').lower()

        buf = datetime.timedelta(seconds=15)
        locs = db.session.execute(
            db.select(LocationMeasurement)
            .where(LocationMeasurement.datetime >= start_dt - buf)
            .where(LocationMeasurement.datetime <= end_dt + buf)
            .order_by(LocationMeasurement.datetime.asc())
        ).scalars().all()
        loc_times = [l.datetime for l in locs]

        safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', target.name or f'campaign_{target.id}').strip('_')
        base_fname = f"{safe_name}_{start_dt.strftime('%Y-%m-%d_%H-%M')}"

        if fmt == 'csv':
            def generate_csv():
                out = io.StringIO()
                writer = csv.writer(out)
                writer.writerow(['datetime', 'type', 'concentration', 'unit', 'latitude', 'longitude', 'heading', 'speed'])
                row_count = 0
                gases_iter = (
                    db.session.execute(
                        db.select(GasMeasurement)
                        .where(GasMeasurement.datetime >= start_dt)
                        .where(GasMeasurement.datetime <= end_dt)
                        .order_by(GasMeasurement.datetime.asc())
                    )
                    .scalars()
                    .yield_per(500)
                )
                for g in gases_iter:
                    loc = _nearest_location(g.datetime, loc_times, locs)
                    writer.writerow([
                        g.datetime.isoformat(),
                        g.type,
                        g.concentration,
                        g.unit,
                        loc.latitude if loc else '',
                        loc.longitude if loc else '',
                        loc.heading if loc else '',
                        loc.speed if loc else '',
                    ])
                    row_count += 1
                    if row_count % 500 == 0:
                        yield out.getvalue()
                        out.seek(0)
                        out.truncate(0)
                remainder = out.getvalue()
                if remainder:
                    yield remainder

            return Response(
                stream_with_context(generate_csv()),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename="{base_fname}.csv"'},
            )

        campaign_meta = {
            'id': target.id,
            'name': target.name,
            'author': target.author,
            'description': target.description,
            'start': start_dt.isoformat(),
            'end': target.end.isoformat() if target.end else None,
        }

        def generate_json():
            yield '{\n  "campaign": ' + json.dumps(campaign_meta, allow_nan=False) + ',\n  "gas": {'
            gas_types = db.session.execute(
                db.select(GasMeasurement.type)
                .where(GasMeasurement.datetime >= start_dt)
                .where(GasMeasurement.datetime <= end_dt)
                .distinct()
                .order_by(GasMeasurement.type.asc())
            ).scalars().all()

            for t_idx, gas_type in enumerate(gas_types):
                prefix = ',\n    ' if t_idx > 0 else '\n    '
                yield prefix + json.dumps(gas_type, allow_nan=False) + ': ['
                gases_iter = (
                    db.session.execute(
                        db.select(GasMeasurement)
                        .where(GasMeasurement.datetime >= start_dt)
                        .where(GasMeasurement.datetime <= end_dt)
                        .where(GasMeasurement.type == gas_type)
                        .order_by(GasMeasurement.datetime.asc())
                    )
                    .scalars()
                    .yield_per(500)
                )
                chunks = []
                first_item = True
                for g in gases_iter:
                    loc = _nearest_location(g.datetime, loc_times, locs)
                    item = {
                        'datetime': g.datetime.isoformat(),
                        'type': g.type,
                        'concentration': _finite_float(g.concentration),
                        'unit': g.unit,
                        'latitude': _finite_float(loc.latitude) if loc else None,
                        'longitude': _finite_float(loc.longitude) if loc else None,
                        'heading': _finite_float(loc.heading) if loc else None,
                        'speed': _finite_float(loc.speed) if loc else None,
                    }
                    chunks.append(('' if first_item else ', ') + json.dumps(item, allow_nan=False))
                    first_item = False
                    if len(chunks) >= 500:
                        yield ''.join(chunks)
                        chunks.clear()
                if chunks:
                    yield ''.join(chunks)
                yield ']'

            yield ('\n  }' if gas_types else '}') + ',\n  "wind": ['
            winds_iter = (
                db.session.execute(
                    db.select(WindMeasurement)
                    .where(WindMeasurement.datetime >= start_dt)
                    .where(WindMeasurement.datetime <= end_dt)
                    .order_by(WindMeasurement.datetime.asc())
                )
                .scalars()
                .yield_per(500)
            )
            wind_chunks = []
            first_wind = True
            for w in winds_iter:
                w_item = {
                    'datetime': w.datetime.isoformat(),
                    'speed': _finite_float(w.speed),
                    'heading': _finite_float(w.heading),
                }
                wind_chunks.append(('' if first_wind else ', ') + json.dumps(w_item, allow_nan=False))
                first_wind = False
                if len(wind_chunks) >= 500:
                    yield ''.join(wind_chunks)
                    wind_chunks.clear()
            if wind_chunks:
                yield ''.join(wind_chunks)
            yield '\n  ]\n}\n'

        return Response(
            stream_with_context(generate_json()),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename="{base_fname}.json"'},
        )

    @app.route('/campaign/edit/<int:campaign_id>')
    def campaign_edit(campaign_id: int):
        edit_campaign = db.session.execute(
            db.select(Campaign)
            .where(Campaign.id == campaign_id)
        ).scalar()
        if not edit_campaign:
            return redirect('/campaign')

        return render_template('campaign.html', campaign=edit_campaign)

    @app.route('/campaign/<int:campaign_id>/stats')
    def campaign_stats(campaign_id: int):
        campaign: Campaign = db.session.execute(
            db.select(Campaign)
            .where(Campaign.id == campaign_id)
        ).scalar()
        if not campaign:
            return {"error": "Campaign not found"}, 404

        stats = [get_campaign_statistics_for_gas(gas, campaign) for gas in ['CH4', 'CO2']]
        return jsonify(stats)

    @app.route('/map/<int:campaign_id>/screenshot/<width>/<height>')
    def screenshot(campaign_id: int, width: str, height: str):
        show_campaign = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalar()
        if not show_campaign:
            return redirect('/campaign')
        end_dt = show_campaign.end or datetime.datetime.now()
        available_species = db.session.execute(
            db.select(GasMeasurement.type)
            .where(GasMeasurement.datetime >= show_campaign.start)
            .where(GasMeasurement.datetime <= end_dt)
            .distinct()
        ).scalars().all()
        return render_template(
            'index.html',
            campaign=show_campaign,
            height=height,
            width=width,
            available_species=available_species,
            map_settings=load_settings()["map"],
        )

    @app.route('/windrose')
    def windrose():
        start = datetime.datetime.strptime(request.args.get('start'), '%Y-%m-%dT%H-%M-%S')
        end = datetime.datetime.strptime(request.args.get('end'), '%Y-%m-%dT%H-%M-%S')
        station = request.args.get('station')

        return send_file(create_windrose(start, end, station), mimetype='image/png')

    @app.route('/wind-mean')
    def wind_mean():
        start = datetime.datetime.strptime(request.args.get('start'), '%Y-%m-%dT%H-%M-%S')
        end = datetime.datetime.strptime(request.args.get('end'), '%Y-%m-%dT%H-%M-%S')
        station = request.args.get('station')

        return jsonify(get_average_wind_speed_and_direction(start, end, station))

    @app.route('/campaign/delete/<int:campaign_id>')
    def campaign_delete(campaign_id: int):
        db.session.execute((db.delete(Campaign).where(Campaign.id == campaign_id)))
        db.session.commit()

        return redirect('/campaign')

    @app.route('/enable-measurements/<int:enable>')
    def enable_measurements(enable: int):
        if enable == 0:
            app.config["ACCEPT_MEASUREMENT_DATA"] = False
        else:
            app.config["ACCEPT_MEASUREMENT_DATA"] = True
        _notify_live_update()
        return redirect('/campaign')

    @app.route('/stats')
    def stats():
        def get_gas_stats_by_datetime(gas_type: str, start: datetime, end: datetime):
            ch4_measurements: List[GasMeasurement] = db.session.execute(
                db.select(GasMeasurement)
                .where(GasMeasurement.datetime >= start)
                .where(GasMeasurement.datetime <= end)
                .where(GasMeasurement.type == gas_type)
            ).scalars().all()

            concentrations = [measurement.concentration for measurement in ch4_measurements]

            return f"""
            start: {start} <br>
            end: {end} <br>
            {gas_type} min: {min(concentrations):.3f} ppm <br>
            {gas_type} max: {max(concentrations):.3f} ppm <br>
            {gas_type} mean: {sum(concentrations)/len(concentrations):.3f} ppm <br>
            <hr>
            """

        output = ""
        output += get_gas_stats_by_datetime(
            "CH4",
            datetime.datetime.strptime(request.args.get('start'), '%Y-%m-%dT%H:%M:%S'),
            datetime.datetime.strptime(request.args.get('end'), '%Y-%m-%dT%H:%M:%S'))
        return output

    @app.route("/baselines")
    def baselines():
        return send_file(plot_baselines("CH4"), mimetype='image/png')

    @app.route('/')
    def index():
        return redirect('/campaign')

    with app.app_context():
        if db.engine.dialect.name == "sqlite":
            @event.listens_for(db.engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA cache_size=-16000;")
                cursor.execute("PRAGMA temp_store=MEMORY;")
                cursor.close()
        db.create_all()
        for tbl in ('gas_measurement', 'location_measurement', 'wind_measurement', 'log'):
            db.session.execute(db.text(f"CREATE INDEX IF NOT EXISTS ix_{tbl}_datetime ON {tbl} (datetime)"))
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_gas_measurement_type_datetime ON gas_measurement (type, datetime)"))
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_log_sensor_datetime ON log (sensor, datetime)"))
        db.session.commit()
        for key, model_cls in measurement_type_look_up.items():
            startup_max_ids[key] = db.session.execute(
                db.select(db.func.max(model_cls.id))
            ).scalar() or 0

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        debug=os.environ.get("FLASK_DEBUG") == "1")
