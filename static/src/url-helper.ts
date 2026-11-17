export function getUrlParameter(name: string, fallback: string) {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has(name)) {
        return urlParams.get(name);
    } else {
        return fallback;
    }
}

export function is_screenshot_mode() {
    return window.location.href.includes('screenshot');
}

export function extractCampaignIdFromCurrentUrl(): number {
    const url = window.location.href;
    const match = url.match(/\/map\/(\d+)\/screenshot/);

    if (match) {
        return parseInt(match[1], 10);
    }
    return 0;
}

export interface Campaign {
    start: Date;
    end: Date;
}


export function extractStartEndFromUrlIfPresent(campaign: Campaign): Campaign {
    // Helper function to get the value of a specific query parameter
    const getQueryParam = (param: string): string | null => {
      const urlParams = new URLSearchParams(window.location.search);
      return urlParams.get(param);
    };
  
    // Extract 'start' and 'end' query parameters from the current URL
    const startParam = getQueryParam('start');
    const endParam = getQueryParam('end');
  
    // Create a new Campaign object to return
    const updatedCampaign: Campaign = {
      start: startParam ? new Date(startParam) : campaign.start,
      end: endParam ? new Date(endParam) : campaign.end
    };
  
    return updatedCampaign;
  }