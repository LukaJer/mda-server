import datetime
from configparser import ConfigParser
from functools import wraps
from typing import List

from flask import Flask, request, jsonify, render_template, redirect, send_file
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


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['ACCEPT_MEASUREMENT_DATA'] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = get_db_config()
    db.init_app(app)

    @app.post("/measurement/<measurement_type>")
    @timeit
    def post_measurement(measurement_type: str):
        if request.is_json:
            try:
                measurement = measurement_type_look_up[measurement_type].create_from_json(request.get_json())
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

    @app.route('/map/<campaign_id>')
    def campaign_map(campaign_id: int):
        show_campaign = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalar()
        if not show_campaign:
            return redirect('/campaign')
        return render_template('index.html', campaign=show_campaign)

    @app.route('/campaign',  methods=['POST', 'GET'])
    def campaign():
        if request.method == 'GET':
            campaigns = db.session.execute(
                db.select(Campaign)
                .order_by(Campaign.start.desc())
            ).scalars().all()
            return render_template(
                'campaigns.html',
                campaigns=campaigns,
                now=datetime.datetime.now(),
                enable_measurements=app.config["ACCEPT_MEASUREMENT_DATA"])
        else:
            campaign_id = int(request.form.get('id', 0))
            start = datetime.datetime.fromisoformat(request.form['start'])
            end = ApiHelper.get_datetime_if_set(request.form['end'])
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        debug=True)
