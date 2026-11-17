export class AimIcon {
    private svgNS = "http://www.w3.org/2000/svg";
    private svg: SVGSVGElement;
    private circle: SVGCircleElement;
    private dot: SVGCircleElement;
    private lines: SVGLineElement[] = [];
  
    constructor() {
      this.svg = document.createElementNS(this.svgNS, "svg") as SVGSVGElement;
      this.svg.setAttribute("width", "24");
      this.svg.setAttribute("height", "24");
      this.svg.setAttribute("viewBox", "0 0 24 24");
  
      this.circle = document.createElementNS(this.svgNS, "circle") as SVGCircleElement;
      this.circle.setAttribute("cx", "12");
      this.circle.setAttribute("cy", "12");
      this.circle.setAttribute("r", "10");
      this.circle.setAttribute("stroke-width", "2");
      this.circle.setAttribute("fill", "none");
  
      this.dot = document.createElementNS(this.svgNS, "circle") as SVGCircleElement;
      this.dot.setAttribute("cx", "12");
      this.dot.setAttribute("cy", "12");
      this.dot.setAttribute("r", "2");
  
      const positions = [
        { x1: "12", y1: "2", x2: "12", y2: "6" },
        { x1: "12", y1: "18", x2: "12", y2: "22" },
        { x1: "2", y1: "12", x2: "6", y2: "12" },
        { x1: "18", y1: "12", x2: "22", y2: "12" }
      ];
      positions.forEach(pos => {
        const line = document.createElementNS(this.svgNS, "line") as SVGLineElement;
        line.setAttribute("x1", pos.x1);
        line.setAttribute("y1", pos.y1);
        line.setAttribute("x2", pos.x2);
        line.setAttribute("y2", pos.y2);
        line.setAttribute("stroke-width", "2");
        this.lines.push(line);
      });
  
      this.svg.appendChild(this.circle);
      this.svg.appendChild(this.dot);
      this.lines.forEach(line => this.svg.appendChild(line));
  
      this.updateColor("grey");
    }
  
    getElement(): SVGSVGElement {
      return this.svg;
    }
  
    updateColor(color: string) {
      this.circle.setAttribute("stroke", color);
      this.dot.setAttribute("fill", color);
      this.lines.forEach(line => line.setAttribute("stroke", color));
    }
  }