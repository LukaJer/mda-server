

class WindVane:
    Y_OFFSET = 2
    Y_START = 17.3

    def __init__(self, kt):
        self.kt = kt
        self.y = 19
        self.svg = (f'<?xml version="1.0" encoding="UTF-8"?>'
                    f'<svg width="200mm" height="200mm" version="1.1" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">'
                    f'<path d="m 10 0 v17.3" stroke="#000" stroke-width=".6"/>')

    def write_svg(self):
        n_triangles = int(self.kt / 50)
        n_big_vanes = int((self.kt - n_triangles * 50) / 10)
        small_vane = True if self.kt % 10 else False

        if n_triangles:
            self.y = self.Y_START
        elif not n_triangles and not n_big_vanes and small_vane:
            self.y -= self.Y_OFFSET
        else:
            pass

        for n in range(n_triangles):
            self._add_triangle()

        for n in range(n_big_vanes):
            self._add_big_vane()

        if small_vane:
            self._add_small_vane()

        self.svg += '</svg>'

        with open(f"{self.kt}kt-wind-vane.svg", "w") as svg:
            svg.write(self.svg)

    def _add_triangle(self):
        self.svg += f'<path d="m10 {self.y} 6 -2 -6 -2z"/>'
        self.y -= 2 * self.Y_OFFSET

    def _add_big_vane(self):
        self.y -= self.Y_OFFSET
        self.svg += f'<path d="m10 {self.y} 6 2" stroke="#000" stroke-width=".6"/>'

    def _add_small_vane(self):
        self.y -= self.Y_OFFSET
        self.svg += f'<path d="m10 {self.y} 3 1" stroke="#000" stroke-width=".6"/>'


def main():
    for kt in range(5, 120, 5):
        wind_vane = WindVane(kt)
        wind_vane.write_svg()


if __name__ == "__main__":
    main()
