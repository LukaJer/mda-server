import * as L from 'leaflet';
import { AimIcon } from './aim-icon';

export class FocusControl extends L.Control {
  private setFocusCallback: (focus: boolean) => void;
  private aimIcon: AimIcon;
  private button!: HTMLAnchorElement;
  private isActive = false;

  constructor(options: L.ControlOptions, setFocusCallback: (focus: boolean) => void, initialActive = false) {
    super(options);
    this.setFocusCallback = setFocusCallback;
    this.isActive = initialActive;
    this.aimIcon = new AimIcon();
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

    this.button.appendChild(this.aimIcon.getElement());
    this.updateColor();


    L.DomEvent.on(this.button, 'click', () => {
      this.isActive = !this.isActive;
      this.setFocusCallback(this.isActive);
      this.updateColor()
    });

    container.title = 'Toggle Focus';
    return container;
  }

  onRemove(map: L.Map): void {}

  private updateColor() {
    const color = this.isActive ? "red" : "grey";
    this.aimIcon.updateColor(color);
  }

}
