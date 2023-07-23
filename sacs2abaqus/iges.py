import sys, math
from collections.abc import Sequence

Point = tuple[float, float, float]


def hollerith(s: str) -> str:
    return "{}H{}".format(len(s), s)


class Iges:
    def __init__(self):
        self.buffer = {"D": [], "P": []}
        self.lineno = {"D": 0, "P": 0}

    def add_line(self, section: str, line: str, index: int = None) -> None:
        self.lineno[section] += 1
        lineno = self.lineno[section]
        buf = "{:64s}{:>8s}{}{:7d}\n".format(line, str(index or ""), section, lineno)
        self.buffer[section].append(buf)

    def update(self, section: str, params: Sequence, index: int = None):
        params = [str(p) for p in params]
        lines = [params[0]]
        for p in params[1:]:
            if len(lines[-1] + p) + 1 < 64:
                lines[-1] += "," + p
            else:
                lines[-1] += ","
                lines.append(p)
        for line in lines[:-1]:
            self.add_line(section, line + ",", index=index)
        self.add_line(section, lines[-1] + ";", index=index)

    def start_section(self, comment: str = None):
        comment = comment or ""
        self.buffer["S"] = []
        self.lineno["S"] = 0
        self.update("S", [comment])

    def global_section(self, filename: str):
        self.buffer["G"] = []
        self.lineno["G"] = 0
        self.update(
            "G",
            [
                "1H,",  # 1  parameter delimiter
                "1H;",  # 2  record delimiter
                "6HNoname",  # 3  product id of sending system
                hollerith(filename),  # 4  file name
                "6HNoname",  # 5  native system id
                "6HNoname",  # 6  preprocessor system
                "32",  # 7  binary bits for integer
                "38",  # 8  max power represented by float
                "6",  # 9  number of significant digits in float
                "308",  # 10 max power represented in double
                "15",  # 11 number of significant digits in double
                "6HNoname",  # 12 product id of receiving system
                "1.00",  # 13 model space scale
                "6",  # 14 units flag (2=mm, 6=m)
                "1HM",  # 15 units name (2HMM)
                "1",  # 16 number of line weight graduations
                "1.00",  # 17 width of max line weight
                "15H20181210.181412",  # 18 file generation time
                "1.0e-006",  # 19 min resolution
                "0.00",  # 20 max coordinate value
                "6HNoname",  # 21 author
                "6HNoname",  # 22 organization
                "11",  # 23 specification version
                "0",  # 24 drafting standard
                "15H20181210.181412",  # 25 time model was created
            ],
        )

    def entity(
        self, code: int, params: Sequence, label: str = "", child: bool = False
    ) -> int:
        status = "00010001" if child else "1"
        dline = self.lineno["D"] + 1
        pline = self.lineno["P"] + 1
        self.buffer["D"].append(
            "{:>8d}{:8d}{:8d}{:8d}{:8d}{:8d}{:8d}{:8d}{:>8s}D{:7d}\n".format(
                code, pline, 0, 0, 0, 0, 0, 0, status, dline
            )
        )
        self.buffer["D"].append(
            "{:>8d}{:8d}{:8d}{:8d}{:8d}{:8d}{:8d}{:8s}{:8d}D{:7d}\n".format(
                code, 1, 0, 1, 0, 0, 0, label, 0, dline + 1
            )
        )
        self.update("P", [code] + list(params), index=dline)
        self.lineno["D"] = dline + 1
        return dline

    def pos(self, pt: Point, origin: Point) -> Point:
        x, y, z = origin
        return (pt[0] + x, pt[1] + y, pt[2] + z)

    def origin(self, size, origin, centerx=False, centery=False):
        w, h = size
        x, y, z = origin
        if centerx:
            x -= w / 2
        if centery:
            y -= h / 2
        return x, y, z

    def mapping(self, points, origin):
        start = points[-1]
        refs = []
        for p in points:
            refs.append(self.line(start, p, origin, child=True))
            start = p
        return self.entity(102, [len(refs)] + refs, child=True)

    def surface(self, directrix, vector, points: Sequence[Point], origin: Point):
        surface = self.entity(122, [directrix] + list(vector), child=True)
        mapping = self.mapping(points, origin)
        curve = self.entity(142, [1, surface, 0, mapping, 2], child=True)
        self.entity(144, [surface, 1, 0, curve])

    def cylinder(self, directrix, vector, origin):
        self.entity(120, [directrix, vector, 0, 2 * math.pi])

    def write(self, filename: str = None):
        self.start_section()
        self.global_section(filename or "")
        # Select between a file writer or writing to stdout
        if filename is None:
            outputHandle = open(sys.stdout.fileno(), "wt", closefd=False)
        else:
            outputHandle = open(filename, "wt")
        with outputHandle as f:
            f.write("".join(self.buffer["S"]))
            f.write("".join(self.buffer["G"]))
            f.write("".join(self.buffer["D"]))
            f.write("".join(self.buffer["P"]))
            f.write(
                "S{:7d}G{:7d}D{:7d}P{:7d}{:40s}T{:7d}\n".format(
                    self.lineno["S"],
                    self.lineno["G"],
                    self.lineno["D"],
                    self.lineno["P"],
                    "",
                    1,
                )
            )

    def line(
        self, start: Point, end: Point, origin: Point = (0, 0, 0), child: bool = False
    ):
        start = self.pos(start, origin)
        end = self.pos(end, origin)
        return self.entity(110, start + end, child=child)

    def plane(self, size: tuple[float, float], origin: Point = (0, 0, 0), **kw):
        w, h = size
        x, y, z = origin = self.origin(size, origin, **kw)
        points = [(w, 0, 0), (w, h, 0), (0, h, 0), (0, 0, 0)]
        directrix = self.line((0, 0, 0), (w, 0, 0), origin, child=True)
        self.surface(directrix, (x, y + h, z), points, origin)

    def ypipe(self, length, rad, origin: Point = (0, 0, 0)):
        directrix = self.line((0, 0, 0), (0, 1, 0), origin, child=True)
        vector = self.line((0, 0, rad), (0, length, rad), origin, child=True)
        self.cylinder(directrix, vector, origin)

    def xpipe(self, length, rad, origin: Point = (0, 0, 0)):
        directrix = self.line((0, 0, 0), (1, 0, 0), origin, child=True)
        vector = self.line((0, 0, rad), (length, 0, rad), origin, child=True)
        self.cylinder(directrix, vector, origin)

