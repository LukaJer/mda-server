import { is_screenshot_mode, getUrlParameter } from "./url-helper";

interface GasData {
    base_mean: number;
    base_std: number;
    max: number;
    mean: number;
    min: number;
}

interface GasResponse {
    CH4?: GasData;
    CO2?: GasData;
    "CH4-LI"?: GasData;
    "CO2-LI"?: GasData;
}

type GasApiResponse = GasResponse[];

async function fetchCampaignStatistics(campaign_id: Number): Promise<GasApiResponse> {
    const response = await fetch(`/campaign/${campaign_id}/stats`);

    if (!response.ok) {
        throw new Error(`Error fetching campaign statistics data: ${response.statusText}`);
    }

    const data: GasApiResponse = await response.json();
    return data;
}

export async function getBaseConcentration(campaign_id: Number, gas: 'CH4' | 'CO2' | 'CH4-LI' | 'CO2-LI', fallbackValue: number): Promise<number> {
    if (is_screenshot_mode()) {
        try {
            const data = await fetchCampaignStatistics(campaign_id);
            const gas_campaign_statistics = data.find(entry => entry[gas])?.[gas];

            if (gas_campaign_statistics) {
                return gas_campaign_statistics.base_mean;
            } else {
                return fallbackValue;
            }
        } catch (error) {
            console.error(`Error fetching campaign statistics for ${gas}:`, error);
            return fallbackValue;
        }
    } else {
        return Number(getUrlParameter("min", fallbackValue.toString()));
    }
}