
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
    private pollGeneration: number = 0;
    private abortController: AbortController | null = null;
    public onFinished?: () => void;
    public onBatch?: (totalCount: number) => void;
    public onPollSettled?: () => void;



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
        this.stopPlotting();
        this.isPolling = true;
        const gen = ++this.pollGeneration;
        this.baseInterval = interval;
        this.currentInterval = this.baseInterval;

        const poll = async () => {
            if (!this.isPolling || gen !== this.pollGeneration) return;

            const ctrl = new AbortController();
            this.abortController = ctrl;

            try {
                const hasMoreBacklog = await this.update(ctrl.signal);
                if (!this.isPolling || gen !== this.pollGeneration) return;
                if (!hasMoreBacklog) {
                    this.onPollSettled?.();
                }
                // Fetch remaining backlog batches immediately without waiting (both finished and catching-up live campaigns)
                this.currentInterval = (this.end_datetime !== null || hasMoreBacklog) ? 0 : this.baseInterval;
            } catch (error) {
                if (!this.isPolling || gen !== this.pollGeneration || (error as any)?.name === 'AbortError') {
                    return;
                }
                this.onPollSettled?.();
                if (this.end_datetime !== null) {
                    this.stopPlotting();
                    this.onFinished?.();
                    return;
                }
                this.currentInterval = Math.min(this.currentInterval * 2, this.maxInterval); // Exponential backoff
                console.error('No new "' + this.url_endpoint_type + '" data available. Next poll in ' + this.currentInterval/1000 + 's');
            } finally {
                if (this.abortController === ctrl) {
                    this.abortController = null;
                }
            }

            if (this.isPolling && gen === this.pollGeneration) {
                this.interval_id = setTimeout(poll, this.currentInterval);
            }
        };
        poll();
    }

    stopPlotting(): void {
        this.pollGeneration++;
        this.isPolling = false;
        if (this.interval_id) {
            clearTimeout(this.interval_id);
            this.interval_id = null;
        }
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }
  
    async update(signal?: AbortSignal): Promise<boolean> {
        const response = await fetch(this.getRequestUrl(), signal ? { signal } : undefined);
        if (!response.ok) {
            throw new Error("No data available.");
        }

        const data = await response.json();
        if (signal?.aborted) {
            return false;
        }
        this.plotData(data);
        // Server Request.DEFAULT_LIMIT is 2000 (interpolation may drop a few unlocated points)
        return Array.isArray(data) && data.length >= 1500;
    }

    plotData(data: any[]): void {
        let new_measurements = false;
        data.forEach((measurement) => {
            if (!this.measurements.has(measurement.datetime)) {
                this.start_datetime = new Date(measurement.datetime);
                this.measurements.set(measurement.datetime, measurement);
                this.drawMeasurement(measurement);
                this.previous_measurement = measurement;
                new_measurements = true;
            }
        });

        if (!new_measurements) {
            throw new Error("No new data available.");
        }
        this.onBatchPlotted();
        this.onBatch?.(this.measurements.size);
    }

    protected onBatchPlotted(): void {}

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
        const milliseconds = datetime.getMilliseconds();
        const frac = milliseconds > 0 ? `.${String(milliseconds).padStart(3, '0')}` : '';

        const formatted_string = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${frac}`;
        return formatted_string;
    }

    getRequestUrl(): string {
        throw new Error("To be implemented by child!");
    }
  }
  