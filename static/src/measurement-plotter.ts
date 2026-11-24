
export class MeasurementPlotter {
    interval_id: any
    start_datetime: Date
    end_datetime: Date | null
    measurements: Map<string, any>
    previous_measurement: any
    url_endpoint_type: string
    private isPolling: boolean = false;
    private baseInterval: number = 1000;
    private maxInterval: number = 10000;
    private currentInterval: number = this.baseInterval;
    public onFinished?: () => void;



    constructor(start_datetime: Date, end_datetime: Date | null, url_endpoint_type: string) {
      if (new.target === MeasurementPlotter) {
        throw new TypeError("Cannot construct Abstract instances directly");
      }
      this.interval_id = null;
      this.start_datetime = start_datetime;
      this.end_datetime = end_datetime;
      this.measurements = new Map();
      this.previous_measurement = null;
      
      this.url_endpoint_type = url_endpoint_type;
    }

    
    startPlotting(interval: number): void {
        this.isPolling = true;
        this.baseInterval = interval;
        this.currentInterval = this.baseInterval;

        const poll = async () => {
            if (!this.isPolling) return;

            try {
                await this.update();
                // Finished campaigns should fetch all remaining batches immediately without waiting
                this.currentInterval = this.end_datetime !== null ? 0 : this.baseInterval;
            } catch (error) {
                if (this.end_datetime !== null) {
                    this.stopPlotting();
                    this.onFinished?.();
                    return;
                }
                this.currentInterval = Math.min(this.currentInterval * 2, this.maxInterval); // Exponential backoff
                console.error('No new "' + this.url_endpoint_type + '" data available. Next poll in ' + this.currentInterval/1000 + 's');
            }

            if (this.isPolling) {
                this.interval_id = setTimeout(poll, this.currentInterval);
            }
        };
        poll();
    }

    stopPlotting(): void {
        this.isPolling = false;
        if (this.interval_id) {
            clearTimeout(this.interval_id);
            this.interval_id = null;
        }
    }
  
    async update(): Promise<void> {
        const response = await fetch(this.getRequestUrl());
        if (!response.ok) {
            throw new Error("No data available.");
        }

        const data = await response.json();
        this.plotData(data);
    }

    plotData(data: any[]): void {
        var new_measurements: Boolean = false;
        data.forEach((measurement) => {
            if (this.previous_measurement === null) {
                this.previous_measurement = measurement;
                this.measurements.set(measurement.datetime, measurement);
            } else {
                if (!this.measurements.has(measurement.datetime)) {
                    this.start_datetime = new Date(measurement.datetime);
                    this.drawMeasurement(measurement);
                    this.previous_measurement = measurement;
                    this.measurements.set(measurement.datetime, measurement);
                    new_measurements = true;
                }
            }
        });

        if (!new_measurements) {
            throw new Error("No new data available.");
        }
    }

    drawMeasurement(measurement: any) {
        throw new Error("To be implemented by child!");
    }

    static formatToISODateTime(datetime: Date): string {
        const year = datetime.getFullYear();
        const month = String(datetime.getMonth() + 1).padStart(2, '0'); // Months are zero-based
        const day = String(datetime.getDate()).padStart(2, '0');
        const hours = String(datetime.getHours()).padStart(2, '0');
        const minutes = String(datetime.getMinutes()).padStart(2, '0');
        const seconds = String(datetime.getSeconds()).padStart(2, '0');

        const formatted_string = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
        return formatted_string;
    }

    getRequestUrl(): string {
        throw new Error("To be implemented by child!");
    }
  }
  