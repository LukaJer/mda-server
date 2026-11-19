import * as L from 'leaflet';
import { WindIcon } from './wind-icon';

export class WindControl extends L.Control {
  private showCallback: (show: boolean) => void;
  private windIcon: WindIcon;
  private button!: HTMLAnchorElement;
  private isActive = false;

  constructor(options: L.ControlOptions, showCallback: (focus: boolean) => void) {
    super(options);
    this.showCallback = showCallback;
    this.windIcon = new WindIcon();
  }
  onAdd(map: L.Map): HTMLElement {
    const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
    this.button = L.DomUtil.create('a', 'leaflet-control-button', container);
    L.DomEvent.disableClickPropagation(this.button);
    this.button.href = "#"; // Need so the button shows the click symbol when hovered


    // Add CSS to center the SVG
    this.button.style.display = 'flex';
    this.button.style.alignItems = 'center';
    this.button.style.justifyContent = 'center';

    this.button.appendChild(this.windIcon.getElement());
    this.updateColor();


    L.DomEvent.on(this.button, 'click', () => {
      this.isActive = !this.isActive;
      this.showCallback(this.isActive);
      this.updateColor()
    });

    container.title = 'Toggle Wind';
    return container;
  }

  onRemove(map: L.Map): void {}

  private updateColor() {
    const color = this.isActive ? "blue" : "grey";
    this.windIcon.updateColor(color);
  }

}
