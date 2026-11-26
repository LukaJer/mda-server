from datetime import datetime
from io import BytesIO
import os
import tempfile
from typing import List

import numpy as np
import matplotlib.pyplot as plt

from models.base_model import db
from models.campaign_model import Campaign
from models.gas_measurement_model import GasMeasurement


def get_campaign_statistics_for_gas(gas_type: str, campaign: Campaign, base_percentage: float = 0.25):
    end_dt = campaign.end or datetime.now()
    measurements: List[GasMeasurement] = db.session.execute(
        db.select(GasMeasurement)
        .where(GasMeasurement.datetime >= campaign.start)
        .where(GasMeasurement.datetime <= end_dt)
        .where(GasMeasurement.type == gas_type)
    ).scalars().all()

    concentrations = sorted(measurement.concentration for measurement in measurements)
    if not concentrations:
        return {
            gas_type: {
                "min": None,
                "max": None,
                "mean": None,
                "base_mean": None,
                "base_std": None,
            }
        }

    n_base_samples = int(len(concentrations) * base_percentage)
    base_concentrations = concentrations[:n_base_samples] if n_base_samples > 0 else concentrations[:1]

    return {
        gas_type: {
            "min": float(min(concentrations)),
            "max": float(max(concentrations)),
            "mean": float(np.mean(concentrations)),
            "base_mean": float(np.mean(base_concentrations)),
            "base_std": float(np.std(base_concentrations)),
        }
    }


# def get_gas_stats_by_datetime(gas_type: str, start: datetime, end: datetime):
#     ch4_measurements: List[GasMeasurement] = db.session.execute(
#         db.select(GasMeasurement)
#         .where(GasMeasurement.datetime >= start)
#         .where(GasMeasurement.datetime <= end)
#         .where(GasMeasurement.type == gas_type)
#     ).scalars().all()
#
#     concentrations = [measurement.concentration for measurement in ch4_measurements]
#
#     return f"""
#     start: {start} <br>
#     end: {end} <br>
#     {gas_type} min: {min(concentrations):.3f} ppm <br>
#     {gas_type} max: {max(concentrations):.3f} ppm <br>
#     {gas_type} mean: {sum(concentrations)/len(concentrations):.3f} ppm <br>
#     <hr>
#     """
#
#     output = ""
#     for gas in ["CH4", "CO2"]:
#         output += get_gas_stats(gas)
#
#     output += get_gas_stats_by_datetime(
#         "CH4",
#         datetime.datetime(2024, 8, 13, 11, 9, 0),
#         datetime.datetime(2024, 8, 13, 11, 13, 0))
#     return output


def plot_baselines(gas_type: str):
    data = {}
    percentiles = np.arange(1, 40 + 1)
    now = datetime.now()

    campaigns = db.session.scalars(db.select(Campaign).order_by(Campaign.id)).all()
    for campaign in campaigns:
        end_dt = campaign.end or now
        measurements: List[GasMeasurement] = db.session.execute(
            db.select(GasMeasurement)
            .where(GasMeasurement.datetime >= campaign.start)
            .where(GasMeasurement.datetime <= end_dt)
            .where(GasMeasurement.type == gas_type)
        ).scalars().all()

        concentrations = sorted(measurement.concentration for measurement in measurements)
        if concentrations:
            data[f"Campaign {campaign.id}"] = concentrations

    baselines_data = {}
    for campaign_label, concentrations in data.items():
        baselines = []
        for baseline_percentage in percentiles:
            R = len(concentrations) * (baseline_percentage / 100)
            idx = int(R) - 1 if int(R) > 0 else 0
            baselines.append(concentrations[idx])

        baselines = [int(baseline * 1000 + 0.5) / 1e3 for baseline in baselines]
        lowest_percentage_baseline = baselines[0]

        baselines_data[campaign_label] = [(baseline - lowest_percentage_baseline) * 1000 for baseline in baselines]

    plt.rcParams["font.family"] = "serif"
    fig, ax = plt.subplots(figsize=(7, 4))
    for campaign_label, baselines in baselines_data.items():
        ax.plot(percentiles, baselines, label=campaign_label)
    ax.minorticks_on()
    ax.grid(True, which='major', linestyle='-')
    ax.grid(True, which='minor', linestyle='--')
    if baselines_data:
        ax.legend(loc='upper right')
    ax.set(xlabel='Percentile (%)', ylabel='Background concentration deviation (ppb)')

    img = BytesIO()
    plt.tight_layout()
    plt.savefig(img, format="png")
    img.seek(0)
    plt.savefig(os.path.join(tempfile.gettempdir(), "background_vs_percentage_normalized.eps"))
    plt.close(fig)
    return img

