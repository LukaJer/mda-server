from io import BytesIO
from typing import List

import numpy as np
import matplotlib.pyplot as plt

from models.base_model import db
from models.campaign_model import Campaign
from models.gas_measurement_model import GasMeasurement


def get_campaign_statistics_for_gas(gas_type: str, campaign: Campaign, base_percentage: float = 0.25):
    measurements: List[GasMeasurement] = db.session.execute(
        db.select(GasMeasurement)
        .where(GasMeasurement.datetime >= campaign.start)
        .where(GasMeasurement.datetime <= campaign.end)
        .where(GasMeasurement.type == gas_type)
    ).scalars().all()

    concentrations = [measurement.concentration for measurement in measurements]
    concentrations.sort()

    n_base_samples = int(len(concentrations)*base_percentage)
    base_concentrations = concentrations[:n_base_samples]

    return {
        gas_type: {
            "min": min(concentrations),
            "max": max(concentrations),
            "mean": np.mean(concentrations),
            "base_mean": np.mean(base_concentrations),
            "base_std": np.std(base_concentrations)
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
    percentiles = np.arange(1, 40+1)

    for campaign_id in range(1, 11):
        campaign: Campaign = db.session.execute(db.select(Campaign).where(Campaign.id == campaign_id)).scalars().one()

        measurements: List[GasMeasurement] = db.session.execute(
            db.select(GasMeasurement)
            .where(GasMeasurement.datetime >= campaign.start)
            .where(GasMeasurement.datetime <= campaign.end)
            .where(GasMeasurement.type == gas_type)
        ).scalars().all()

        concentrations = [measurement.concentration for measurement in measurements]
        concentrations.sort()

        data[f"Campaign {campaign_id}"] = concentrations

    baselines_data = {}
    for campaign, concentrations in data.items():
        baselines = []
        for baseline_percentage in percentiles:
            R = len(concentrations) * (baseline_percentage/100)
            if R.is_integer():
                baselines.append(concentrations[int(R) - 1])
            else:
                baselines.append(concentrations[int(R) - 1])

        baselines = [int(baseline * 1000 + 0.5)/1e3 for baseline in baselines]
        lowest_percentage_baseline = baselines[0]

        baselines_data[campaign] = [(baseline - lowest_percentage_baseline)*1000 for baseline in baselines]
        # baselines_data[campaign] = baselines

    plt.rcParams["font.family"] = "serif"
    fig, ax = plt.subplots(figsize=(7, 4))
    for campaign, baselines in baselines_data.items():
        ax.plot(percentiles, baselines, label=campaign)
    ax.minorticks_on()
    ax.grid(True, which='major', linestyle='-')
    ax.grid(True, which='minor', linestyle='--')
    ax.legend(loc='upper right')
    ax.set(xlabel='Percentile (%)', ylabel='Background concentration deviation (ppb)')

    img = BytesIO()
    plt.tight_layout()
    plt.savefig(img)
    img.seek(0)
    plt.savefig("/home/christoph/Documents/Studium/EIT_M_5_WS23-24/Masterarbeit/Arbeit/Thesis/Images/Methods/background_vs_percentage_normalized.eps")
    plt.close()
    return img

