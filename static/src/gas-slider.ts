import * as L from 'leaflet';

export class Slider {
    private slider_element: HTMLInputElement;
    public gas_name: string | null = null;
    private data_map: Map<string, any> | null = null;
    private map: L.Map;
    private popup: L.Popup | null = null;

    constructor(
        slider_id: string,
        map: L.Map
    ) {
        this.slider_element = document.getElementById(slider_id) as HTMLInputElement;
        this.map = map;
        this.slider_element.addEventListener('input', this.showPopupOnDrag.bind(this));
        this.slider_element.addEventListener('mousedown', this.showPopupOnDrag.bind(this));
        this.slider_element.addEventListener('touchstart', this.showPopupOnDrag.bind(this));
        this.slider_element.addEventListener('mouseup', this.hidePopup.bind(this));
        this.slider_element.addEventListener('touchend', this.hidePopup.bind(this));
        this.updateSliderMax();
    }

    public updateSliderMax() {
        if ( this.data_map ) {
            this.slider_element.max = (this.data_map.size - 1).toString();
        }
    }

    public updateGasType(gas: string, data_map: Map<string, any>) {
        this.gas_name = gas;
        this.data_map = data_map;
        this.updateSliderMax();
    }

    private showPopupOnDrag() {
        const index = parseInt(this.slider_element.value, 10);
        this.updatePopup(index);
    }

    private hidePopup() {
        if (this.popup) {
            this.map.closePopup(this.popup);
            this.popup = null;
        }
    }

    private updatePopup(index: number) {
        if (this.data_map) {
            const dateKeys = Array.from(this.data_map.keys());
            const selectedDate = dateKeys[index];
            const data = this.data_map.get(selectedDate);
            const pop_up_content = `${selectedDate}<br>${this.gas_name}: <b>${data.concentration.toFixed(3)}</b>${data.unit}`
    
            if (data) {
                if (this.popup) {
                    this.popup.setLatLng([data.latitude, data.longitude])
                              .setContent(pop_up_content)
                              .openOn(this.map);
                } else {
                    this.popup = L.popup()
                                 .setLatLng([data.latitude, data.longitude])
                                 .setContent(pop_up_content)
                                 .openOn(this.map);
                }
                this.map.panTo(new L.LatLng(data.latitude, data.longitude));
            }
        }
    }
}