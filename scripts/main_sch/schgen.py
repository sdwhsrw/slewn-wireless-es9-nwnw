"""Write a KiCad 10 schematic sheet from code: place symbols, draw wires, labels and boxes.

Symbols keep the UUID and fields of the same reference in the old sheet, so the PCB re-links by
path. Library coordinates are Y-up and sheet coordinates Y-down; see `Sheet.pin`.
"""
import contextlib
import math
import shutil
import sys
import uuid as uuidlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parts import FOOTPRINT_MAP, PROJECT, SYMBOL_MAP, load_symbol  # noqa: E402
from sexpr import Q, dump, find, find_all, parse  # noqa: E402

VERSION = "20260306"
GRID = 1.27
PAPER = {"A3": (420.0, 297.0), "A4": (297.0, 210.0)}


class SheetXY(tuple):
    """An absolute sheet coordinate (from a pin); offset() does not shift it."""


def _u() -> str:
    return str(uuidlib.uuid4())


def _f(v: float) -> str:
    return f"{round(v, 4):g}"


def _font(size=1.27, justify=None, hide=False):
    eff = ["effects", ["font", ["size", _f(size), _f(size)]]]
    if justify:
        eff.append(["justify", *justify.split()])
    return eff


def _has_hide(node) -> bool:
    return any(x == "hide" or (isinstance(x, list) and (x[0] == "hide" or _has_hide(x))) for x in node[1:]
               if not isinstance(x, str) or x == "hide")


def text_width(text: str, size: float = 1.27) -> float:
    """Approximate rendered width of KiCad's stroke font (CJK glyphs are about square)."""
    text = text.replace("~{", "").replace("}", "")
    return size * sum(1.25 if ord(c) > 0x2E80 else 0.95 for c in text)


def pin_name_boxes(lib_id: str) -> list[tuple[str, tuple]]:
    """Library-space boxes of the visible pin names drawn inside a symbol body."""
    sym = load_symbol(lib_id)
    pn = find(sym, "pin_names")
    off = float(find(pn, "offset")[1]) if pn and find(pn, "offset") else 0.508
    out = []
    for u in find_all(sym, "symbol"):
        for p in find_all(u, "pin"):
            if find(p, "hide"):
                continue
            at = find(p, "at")
            x, y, a = float(at[1]), float(at[2]), int(float(at[3]))
            ln = float(find(p, "length")[1])
            name = find(p, "name")[1]
            w, h = text_width(name), 1.27
            dx, dy = {0: (1, 0), 180: (-1, 0), 90: (0, 1), 270: (0, -1)}[a]
            sx, sy = x + dx * (ln + off), y + dy * (ln + off)
            if dy == 0:
                box = (sx, sy - h / 2, sx + w, sy + h / 2) if dx > 0 else (sx - w, sy - h / 2, sx, sy + h / 2)
            else:
                box = (sx - h / 2, sy, sx + h / 2, sy + w) if dy > 0 else (sx - h / 2, sy - w, sx + h / 2, sy)
            out.append((name, box))
    return out


def prepare_project(d: Path) -> None:
    """A throw-away project folder that resolves the same libraries as hw/main."""
    d.mkdir(parents=True, exist_ok=True)
    for f in ("Slewn_V20_MAIN.kicad_pro", "sym-lib-table", "fp-lib-table"):
        shutil.copy(PROJECT / f, d / f)
    for name in ("library", "Libs"):
        link = d / name
        if not link.exists():
            link.symlink_to(PROJECT / name)


class Sheet:
    def __init__(self, old_sch: Path, paper: str = "A3"):
        root = parse(Path(old_sch).read_text())
        self.root_uuid = find(root, "uuid")[1]
        self.title_block = find(root, "title_block")
        self.paper = paper
        self.old: dict[str, dict] = {}
        for s in find_all(root, "symbol"):
            props = {}
            for p in find_all(s, "property"):
                props[p[1]] = (p[2], _has_hide(p))
            ref = props["Reference"][0]
            self.old[ref] = {"uuid": find(s, "uuid")[1], "props": props}
        self.symbols: dict[str, dict] = {}   # ref -> placement
        self.items: list[list] = []          # wires, labels, no_connects, graphics
        self.segments: list[tuple] = []
        self.lib_ids: set[str] = set()
        self.rects: list[tuple] = []         # block boxes
        self.origin = (0.0, 0.0)             # added to every literal (x, y) while inside offset()
        self._texts: list[tuple] = []        # (owner, text, x, y, size, kind, rot) for labels and notes
        self._pwr = 0

    def add_part(self, ref: str, value: str, description: str) -> None:
        """A part the old sheet does not have; its UUID derives from the reference so reruns keep it."""
        self.old[ref] = {"uuid": str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, f"slewn-main/{ref}")),
                         "props": {"Reference": (ref, False), "Value": (value, False), "Footprint": ("", True),
                                   "Datasheet": ("", True), "Description": (description, True)}}

    # --- geometry -------------------------------------------------------------------------
    def _xform(self, ref: str, px: float, py: float) -> tuple[float, float]:
        s = self.symbols[ref]
        a = math.radians(s["rot"])
        rx = px * math.cos(a) - py * math.sin(a)
        ry = px * math.sin(a) + py * math.cos(a)
        return SheetXY((round(s["x"] + rx, 2), round(s["y"] - ry, 2)))

    def _lib_pins(self, lib_id: str) -> list[list]:
        return [p for u in find_all(load_symbol(lib_id), "symbol") for p in find_all(u, "pin")]

    def pin(self, ref: str, num: str) -> tuple[float, float]:
        for p in self._lib_pins(self.symbols[ref]["lib_id"]):
            if find(p, "number")[1] == num:
                at = find(p, "at")
                return self._xform(ref, float(at[1]), float(at[2]))
        raise KeyError(f"{ref} has no pin {num}")

    def pins(self, ref: str) -> dict[str, tuple[float, float]]:
        return {find(p, "number")[1]: self.pin(ref, find(p, "number")[1])
                for p in self._lib_pins(self.symbols[ref]["lib_id"])}

    def bbox(self, ref: str) -> tuple[float, float, float, float]:
        """Sheet-space (x1, y1, x2, y2) of the symbol body and pins."""
        lib_id = self.symbols[ref]["lib_id"]
        pts = []
        for u in find_all(load_symbol(lib_id), "symbol"):
            for g in u[2:]:
                if not isinstance(g, list):
                    continue
                if g[0] == "rectangle":
                    pts += [tuple(map(float, find(g, "start")[1:3])), tuple(map(float, find(g, "end")[1:3]))]
                elif g[0] == "polyline":
                    pts += [(float(xy[1]), float(xy[2])) for xy in find_all(find(g, "pts"), "xy")]
                elif g[0] == "circle":
                    cx, cy = map(float, find(g, "center")[1:3])
                    r = float(find(g, "radius")[1])
                    pts += [(cx - r, cy - r), (cx + r, cy + r)]
                elif g[0] == "arc":
                    pts += [tuple(map(float, find(g, k)[1:3])) for k in ("start", "mid", "end")]
                elif g[0] == "pin":
                    at = find(g, "at")
                    x, y, a = float(at[1]), float(at[2]), math.radians(float(at[3]))
                    ln = float(find(g, "length")[1])
                    pts += [(x, y), (x + ln * math.cos(a), y + ln * math.sin(a))]
        sp = [self._xform(ref, x, y) for x, y in pts]
        xs, ys = [p[0] for p in sp], [p[1] for p in sp]
        return min(xs), min(ys), max(xs), max(ys)

    # --- placing --------------------------------------------------------------------------
    @contextlib.contextmanager
    def offset(self, dx: float, dy: float = 0.0):
        """Shift literal coordinates (not pin references) by (dx, dy) inside the block."""
        saved = self.origin
        self.origin = (saved[0] + dx, saved[1] + dy)
        try:
            yield self
        finally:
            self.origin = saved

    def place(self, ref: str, x: float, y: float, rot: int = 0, fields="auto", dnp: bool = False) -> None:
        """Place `ref`; `fields` puts Reference/Value 'right', 'left', 'above' or 'below' the body,
        or at an (x, y) for Reference with Value one line below. `dnp` marks it Do Not Populate."""
        lib_id = SYMBOL_MAP[ref]
        self.lib_ids.add(lib_id)
        ox, oy = self.origin
        if isinstance(fields, tuple):
            fields = (fields[0] + ox, fields[1] + oy)
        self.symbols[ref] = {"lib_id": lib_id, "x": round(x + ox, 2), "y": round(y + oy, 2), "rot": rot,
                             "fields": fields, "dnp": dnp}

    def _xy(self, p) -> tuple[float, float]:
        if isinstance(p, str):
            ref, num = p.rsplit(".", 1)
            return self.pin(ref, num)
        if isinstance(p, SheetXY):
            return round(p[0], 2), round(p[1], 2)
        return round(p[0] + self.origin[0], 2), round(p[1] + self.origin[1], 2)

    def wire(self, *pts) -> None:
        xy = [self._xy(p) for p in pts]
        for a, b in zip(xy, xy[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                raise ValueError(f"diagonal wire {a} -> {b}")
            if a == b:
                continue
            self.segments.append((a, b))
            self.items.append(["wire", ["pts", ["xy", _f(a[0]), _f(a[1])], ["xy", _f(b[0]), _f(b[1])]],
                               ["stroke", ["width", "0"], ["type", "default"]], ["uuid", Q(_u())]])

    def label(self, net: str, at, rot: int = 0, size: float = 1.27) -> None:
        x, y = self._xy(at)
        just = {0: "left bottom", 90: "left bottom", 180: "right bottom", 270: "right bottom"}[rot]
        self.items.append(["label", Q(net), ["at", _f(x), _f(y), str(rot)], _font(size, just), ["uuid", Q(_u())]])
        self._texts.append((f"label {net}", net, x, y, size, "label", rot))

    def power(self, name: str, at, rot: int = 0, show_value: bool = True) -> None:
        """`power:GND` or `power:PWR_FLAG` with its pin at `at`."""
        x, y = self._xy(at)
        lib_id = f"power:{name}"
        self.lib_ids.add(lib_id)
        self._pwr += 1
        ref = f"#{'FLG' if name == 'PWR_FLAG' else 'PWR'}{self._pwr:02d}"
        self.symbols[ref] = {"lib_id": lib_id, "x": x, "y": y, "rot": rot, "power": name,
                             "show_value": show_value and name != "PWR_FLAG"}

    def nc(self, ref: str, num: str) -> None:
        x, y = self.pin(ref, num)
        self.items.append(["no_connect", ["at", _f(x), _f(y)], ["uuid", Q(_u())]])

    def box(self, title: str, x1: float, y1: float, x2: float, y2: float) -> None:
        self.rects.append((x1, y1, x2, y2))
        self.items.append(["rectangle", ["start", _f(x1), _f(y1)], ["end", _f(x2), _f(y2)],
                           ["stroke", ["width", "0.254"], ["type", "dash"]], ["fill", ["type", "none"]],
                           ["uuid", Q(_u())]])
        self.note(title, (x1 + 1.27, y1 + 3.81), size=2.0, bold=True)

    def note(self, text: str, at, size: float = 1.8, bold: bool = False) -> None:
        self._texts.append((f"note {text[:12]}", text, at[0], at[1], size, "note", 0))
        font = ["font", ["size", _f(size), _f(size)]] + ([["bold", "yes"]] if bold else [])
        self.items.append(["text", Q(text), ["exclude_from_sim", "no"], ["at", _f(at[0]), _f(at[1]), "0"],
                           ["effects", font, ["justify", "left"]], ["uuid", Q(_u())]])

    # --- text extents (for layout checks) --------------------------------------------------
    def text_boxes(self) -> list[tuple[str, tuple]]:
        """Approximate sheet-space boxes of every visible text: fields, power values, labels, notes."""
        def box(x, y, w, h, just):
            if just == "left":
                return (x, y - h / 2, x + w, y + h / 2)
            if just == "right":
                return (x - w, y - h / 2, x, y + h / 2)
            return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)

        out = []
        for ref, s in self.symbols.items():
            if "power" in s:
                if s["show_value"]:
                    vx, vy = self._value_pos(ref)
                    out.append((f"{ref} GND", box(vx, vy, text_width("GND"), 1.27, None)))
                continue
            (rx, ry, rj), (vx, vy, vj) = self._field_positions(ref)
            out.append((f"{ref} ref", box(rx, ry, text_width(ref), 1.27, rj)))
            value = self.old[ref]["props"]["Value"][0]
            out.append((f"{ref} value", box(vx, vy, text_width(value), 1.27, vj)))
        for owner, text, x, y, size, kind, rot in self._texts:
            w, h = text_width(text, size), size
            if kind == "note":
                out.append((owner, box(x, y, w, h, "left")))
            elif rot == 0:
                out.append((owner, (x, y - h - 0.6, x + w, y - 0.1)))
            elif rot == 180:
                out.append((owner, (x - w, y - h - 0.6, x, y - 0.1)))
            elif rot == 90:
                out.append((owner, (x - h - 0.3, y - w, x - 0.2, y)))
            else:
                out.append((owner, (x - h - 0.3, y, x - 0.2, y + w)))
        return out

    # --- junctions ------------------------------------------------------------------------
    def junctions(self) -> list[tuple[float, float]]:
        def on_interior(p, seg):
            (ax, ay), (bx, by) = seg
            if ax == bx == p[0]:
                return min(ay, by) < p[1] < max(ay, by)
            if ay == by == p[1]:
                return min(ax, bx) < p[0] < max(ax, bx)
            return False

        ends: dict[tuple, int] = {}
        for a, b in self.segments:
            ends[a] = ends.get(a, 0) + 1
            ends[b] = ends.get(b, 0) + 1
        pin_pts = {p for ref, s in self.symbols.items() for p in self.pins(ref).values()}
        out = []
        for p, n in ends.items():
            n += sum(on_interior(p, s) for s in self.segments) * 2 + (p in pin_pts)
            if n >= 3:
                out.append(p)
        return sorted(out)

    # --- output ---------------------------------------------------------------------------
    def _field_positions(self, ref: str):
        s = self.symbols[ref]
        x1, y1, x2, y2 = self.bbox(ref)
        side = s["fields"]
        if isinstance(side, tuple):
            return (side[0], side[1], "left"), (side[0], side[1] + 2.54, "left")
        if side == "auto":
            side = "above" if s["rot"] in (90, 270) and (x2 - x1) > (y2 - y1) else "right"
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if side == "right":
            return (x2 + 0.635, cy - 1.0, "left"), (x2 + 0.635, cy + 1.6, "left")
        if side == "left":
            return (x1 - 0.635, cy - 1.0, "right"), (x1 - 0.635, cy + 1.6, "right")
        if side == "above":
            return (cx, y1 - 3.3, None), (cx, y1 - 1.0, None)
        return (cx, y2 + 1.8, None), (cx, y2 + 4.1, None)

    def _value_pos(self, ref: str) -> tuple[float, float]:
        """Power symbol value: below a GND (in symbol space), pushed clear of the pin when rotated."""
        s = self.symbols[ref]
        if s["power"] != "GND":
            return self._xform(ref, 0, 3.81)
        if s["rot"] in (90, 270):
            gx, gy = self._xform(ref, 0, -2.54)        # tip of the ground symbol
            return gx + (2.6 if gx > s["x"] else -2.6), gy
        return self._xform(ref, 0, -3.81)

    def field_style(self, ref: str, just: str | None = "left") -> tuple[str, str | None]:
        """Stored (angle, justify) that KiCad shows as horizontal text with justification `just`.

        KiCad applies the symbol's rotation to its fields, so rotated symbols need compensating."""
        rot = self.symbols[ref]["rot"]
        if just and rot in (90, 180):
            just = {"left": "right", "right": "left"}[just]
        return ("90" if rot in (90, 270) else "0"), just

    def _symbol_item(self, ref: str) -> list:
        s = self.symbols[ref]
        lib_sym = load_symbol(s["lib_id"])
        node = ["symbol", ["lib_id", Q(s["lib_id"])], ["at", _f(s["x"]), _f(s["y"]), str(s["rot"])], ["unit", "1"],
                ["body_style", "1"], ["exclude_from_sim", "no"], ["in_bom", "no" if "power" in s else "yes"],
                ["on_board", "no" if "power" in s else "yes"], ["in_pos_files", "yes"], ["dnp", "yes" if s.get("dnp") else "no"]]
        if "power" in s:
            node.append(["uuid", Q(_u())])
            name = s["power"]
            ref_txt = ["property", Q("Reference"), Q(ref), ["at", _f(s["x"]), _f(s["y"]), "0"], ["hide", "yes"],
                       _font()]
            vx, vy = self._value_pos(ref)
            angle, _ = self.field_style(ref, None)
            val = ["property", Q("Value"), Q(name), ["at", _f(vx), _f(vy), angle], _font()]
            if not s["show_value"]:
                val.insert(4, ["hide", "yes"])
            node += [ref_txt, val]
            for k in ("Footprint", "Datasheet", "Description"):
                node.append(["property", Q(k), Q(""), ["at", _f(s["x"]), _f(s["y"]), "0"], ["hide", "yes"], _font()])
        else:
            old = self.old[ref]
            node.append(["uuid", Q(old["uuid"])])
            (rx, ry, rj), (vx, vy, vj) = self._field_positions(ref)
            for name, (value, hidden) in old["props"].items():
                if name == "Footprint":
                    value, hidden = FOOTPRINT_MAP[ref], True
                angle = "0"
                if name == "Reference":
                    at, hidden = (rx, ry), False
                    angle, just = self.field_style(ref, rj)
                elif name == "Value":
                    at, hidden = (vx, vy), False
                    angle, just = self.field_style(ref, vj)
                else:
                    at, just = (s["x"], s["y"]), None
                p = ["property", Q(name), Q(value), ["at", _f(at[0]), _f(at[1]), angle]]
                if hidden:
                    p.append(["hide", "yes"])
                node.append(p + [_font(1.27, just)])
        for num in dict.fromkeys(find(p, "number")[1] for u in find_all(lib_sym, "symbol")
                                 for p in find_all(u, "pin")):
            node.append(["pin", Q(num), ["uuid", Q(_u())]])
        node.append(["instances", ["project", Q("Slewn_V20_MAIN"),
                                   ["path", Q("/" + self.root_uuid), ["reference", Q(ref)], ["unit", "1"]]]])
        return node

    def write(self, path: Path) -> Path:
        sheet = ["kicad_sch", ["version", VERSION], ["generator", Q("eeschema")], ["generator_version", Q("10.0")],
                 ["uuid", Q(self.root_uuid)], ["paper", Q(self.paper)]]
        if self.title_block:
            sheet.append(self.title_block)
        sheet.append(["lib_symbols"] + [load_symbol(l) for l in sorted(self.lib_ids)])
        for j in self.junctions():
            sheet.append(["junction", ["at", _f(j[0]), _f(j[1])], ["diameter", "0"], ["color", "0", "0", "0", "0"],
                          ["uuid", Q(_u())]])
        sheet += self.items
        sheet += [self._symbol_item(r) for r in self.symbols]
        sheet.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        sheet.append(["embedded_fonts", "no"])
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump(sheet) + "\n")
        return path
