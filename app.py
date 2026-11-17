import bisect
import csv
import datetime
import io
import json
import os
import re
from configparser import ConfigParser
from functools import wraps
from typing import List

from flask import Flask, Response, request, jsonify, render_template, redirect, send_file
import numpy as np

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
            return {"error": str(error)}
    return wrapper


DEVICES_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "devices.json")
)


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
    config.read('config.ini')
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

    def _update_live_cache(measurement_type: str, m) -> None:
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
        if request.is_json:
            try:
                measurement = measurement_type_look_up[measurement_type].create_from_json(request.get_json())
                _update_live_cache(measurement_type, measurement)
                if measurement_type != "log" and not app.config.get("ACCEPT_MEASUREMENT_DATA", True):
                    return {"paused": True, "message": "Measurement recording is paused"}, 200
                db.session.add(measurement)
                db.session.commit()
                return {"success": "Successfully added measurement to database"}, 201
            except KeyError:
                return {"error": "Invalid JSON or measurement type"}, 415
        return {"error": "Request must be JSON"}, 415

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
        return measurements

    @app.get("/measurement/wind")
    @timeit
    @serialize
    def get_wind_measurements():
        measurement_request = Request(request.args)
        measurements = WindMeasurement.get_data(measurement_request)

        if not measurement_request.with_location:
            return measurements

        locations = LocationMeasurement.get_data(
            measurement_request,
            15,
            datetime.timedelta(seconds=Interpolator.MAX_INTERPOLATION_DISTANCE)
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

        if not measurement_request.with_location:
            return measurements
        locations = LocationMeasurement.get_data(
            measurement_request,
            15,
            datetime.timedelta(seconds=Interpolator.MAX_INTERPOLATION_DISTANCE)
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
        available_species = db.session.execute(
            db.select(GasMeasurement.type)
            .where(GasMeasurement.datetime >= show_campaign.start)
            .where(GasMeasurement.datetime <= end_dt)
            .distinct()
        ).scalars().all()
        return render_template(
            'index.html',
            campaign=show_campaign,
            short_data=(data_span < 120.0),
            available_species=available_species,
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
                edit_campaign = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalars().one()

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
        name = ApiHelper.get_post_if_set(request.form.get('name')) or f"Campaign {now.strftime('%Y-%m-%d %H:%M')}"
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

    @app.get('/api/live')
    def api_live():
        now = datetime.datetime.now()

        # Scan only the most recent rows by primary key (fast O(1) index lookup)
        recent_gases = db.session.execute(
            db.select(GasMeasurement).order_by(GasMeasurement.id.desc()).limit(300)
        ).scalars().all()
        gas_data = {}
        for g in recent_gases:
            if g.type not in gas_data:
                gas_data[g.type] = {
                    "concentration": g.concentration,
                    "unit": g.unit,
                    "datetime": g.datetime.isoformat(),
                    "age_seconds": max(0.0, (now - g.datetime).total_seconds()),
                }

        latest_loc = db.session.execute(
            db.select(LocationMeasurement).order_by(LocationMeasurement.id.desc()).limit(1)
        ).scalar()
        loc_data = (
            {
                "latitude": latest_loc.latitude,
                "longitude": latest_loc.longitude,
                "speed": latest_loc.speed,
                "heading": latest_loc.heading,
                "datetime": latest_loc.datetime.isoformat(),
                "age_seconds": max(0.0, (now - latest_loc.datetime).total_seconds()),
            }
            if latest_loc
            else None
        )

        latest_wind = db.session.execute(
            db.select(WindMeasurement).order_by(WindMeasurement.id.desc()).limit(1)
        ).scalar()
        wind_data = (
            {
                "speed": latest_wind.speed,
                "heading": latest_wind.heading,
                "datetime": latest_wind.datetime.isoformat(),
                "age_seconds": max(0.0, (now - latest_wind.datetime).total_seconds()),
            }
            if latest_wind
            else None
        )

        recent_logs = db.session.execute(
            db.select(Log).order_by(Log.id.desc()).limit(100)
        ).scalars().all()
        logs_data = {}
        for lg in recent_logs:
            if lg.sensor not in logs_data:
                logs_data[lg.sensor] = {
                    "description": lg.description,
                    "datetime": lg.datetime.isoformat(),
                    "age_seconds": max(0.0, (now - lg.datetime).total_seconds()),
                }

        # Overlay live_cache so paused instruments still show live readouts
        for g_type, cached in live_cache["gas"].items():
            db_entry = gas_data.get(g_type)
            if db_entry is None or cached["datetime"].isoformat() >= db_entry["datetime"]:
                gas_data[g_type] = {
                    "concentration": cached["concentration"],
                    "unit": cached["unit"],
                    "datetime": cached["datetime"].isoformat(),
                    "age_seconds": max(0.0, (now - cached["datetime"]).total_seconds()),
                }
        if live_cache["location"] is not None:
            c_loc = live_cache["location"]
            if loc_data is None or c_loc["datetime"].isoformat() >= loc_data["datetime"]:
                loc_data = {
                    "latitude": c_loc["latitude"],
                    "longitude": c_loc["longitude"],
                    "speed": c_loc["speed"],
                    "heading": c_loc["heading"],
                    "datetime": c_loc["datetime"].isoformat(),
                    "age_seconds": max(0.0, (now - c_loc["datetime"]).total_seconds()),
                }
        if live_cache["wind"] is not None:
            c_wind = live_cache["wind"]
            if wind_data is None or c_wind["datetime"].isoformat() >= wind_data["datetime"]:
                wind_data = {
                    "speed": c_wind["speed"],
                    "heading": c_wind["heading"],
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

        return jsonify({
            "server_time": now.isoformat(),
            "paused": not app.config.get("ACCEPT_MEASUREMENT_DATA", True),
            "gas": gas_data,
            "location": loc_data,
            "wind": wind_data,
            "logs": logs_data,
        })

    @app.get('/campaign/<int:campaign_id>/download')
    def campaign_download(campaign_id: int):
        target = db.session.execute(
            db.select(Campaign).where(Campaign.id == campaign_id)
        ).scalar()
        if not target:
            return {"error": "Campaign not found"}, 404

        end_dt = target.end or datetime.datetime.now()
        fmt = request.args.get('format', 'json').lower()

        gases = db.session.execute(
            db.select(GasMeasurement)
            .where(GasMeasurement.datetime >= target.start)
            .where(GasMeasurement.datetime <= end_dt)
            .order_by(GasMeasurement.datetime.asc())
        ).scalars().all()

        buf = datetime.timedelta(seconds=15)
        locs = db.session.execute(
            db.select(LocationMeasurement)
            .where(LocationMeasurement.datetime >= target.start - buf)
            .where(LocationMeasurement.datetime <= end_dt + buf)
            .order_by(LocationMeasurement.datetime.asc())
        ).scalars().all()
        loc_times = [l.datetime for l in locs]

        winds = db.session.execute(
            db.select(WindMeasurement)
            .where(WindMeasurement.datetime >= target.start)
            .where(WindMeasurement.datetime <= end_dt)
            .order_by(WindMeasurement.datetime.asc())
        ).scalars().all()

        safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', target.name or f'campaign_{target.id}').strip('_')
        base_fname = f"{safe_name}_{target.start.strftime('%Y-%m-%d_%H-%M')}"

        if fmt == 'csv':
            out = io.StringIO()
            writer = csv.writer(out)
            writer.writerow(['datetime', 'type', 'concentration', 'unit', 'latitude', 'longitude', 'heading', 'speed'])
            for g in gases:
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
            return Response(
                out.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename="{base_fname}.csv"'},
            )

        gas_by_type = {}
        for g in gases:
            loc = _nearest_location(g.datetime, loc_times, locs)
            gas_by_type.setdefault(g.type, []).append({
                'datetime': g.datetime.isoformat(),
                'type': g.type,
                'concentration': g.concentration,
                'unit': g.unit,
                'latitude': loc.latitude if loc else None,
                'longitude': loc.longitude if loc else None,
                'heading': loc.heading if loc else None,
                'speed': loc.speed if loc else None,
            })

        payload = {
            'campaign': {
                'id': target.id,
                'name': target.name,
                'author': target.author,
                'description': target.description,
                'start': target.start.isoformat(),
                'end': target.end.isoformat() if target.end else None,
            },
            'gas': gas_by_type,
            'wind': [
                {
                    'datetime': w.datetime.isoformat(),
                    'speed': w.speed,
                    'heading': w.heading,
                }
                for w in winds
            ],
        }
        return Response(
            json.dumps(payload, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename="{base_fname}.json"'},
        )

    @app.route('/campaign/edit/<int:campaign_id>')
    def campaign_edit(campaign_id: int):
        edit_campaign = db.session.execute(
            db.select(Campaign)
            .where(Campaign.id == campaign_id)
        ).scalars().one()

        return render_template('campaign.html', campaign=edit_campaign)

    @app.route('/campaign/<int:campaign_id>/stats')
    def campaign_stats(campaign_id: int):
        campaign: Campaign = db.session.execute(
            db.select(Campaign)
            .where(Campaign.id == campaign_id)
        ).scalars().one()

        stats = [get_campaign_statistics_for_gas(gas, campaign) for gas in ['CH4', 'CO2']]
        return jsonify(stats)

    @app.route('/map/<int:campaign_id>/screenshot/<width>/<height>')
    def screenshot(campaign_id: int, width: str, height: str):
        show_campaign = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalar()
        if not show_campaign:
            return redirect('/campaign')
        return render_template('index.html', campaign=show_campaign, height=height, width=width)

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
        db.create_all()
        for tbl in ('gas_measurement', 'location_measurement', 'wind_measurement'):
            db.session.execute(db.text(f"CREATE INDEX IF NOT EXISTS ix_{tbl}_datetime ON {tbl} (datetime)"))
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_gas_measurement_type_datetime ON gas_measurement (type, datetime)"))
        db.session.commit()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        debug=True)
