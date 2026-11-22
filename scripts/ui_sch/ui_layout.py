"""UI sheet layout after the DIY complexity review: three titled blocks on A4, notes underneath.

1 connector J101 (mates 1:1 with MAIN J2) -> 2 display J102 -> 3 encoder ENC101 with pull-ups and RC filters.
REMOVED lists the parts the review took out, MERGED the nets they used to separate, RENAMED the references
closed up afterwards, DNP the spares left on the sheet. Every other net keeps its old name (UI_*) and every symbol its UUID, so the PCB re-links by path;
blocks meet through net labels. Stock KiCad symbols replace the per-reference boxes of the old sheet, the
footprints stay. All coordinates sit on the 1.27 mm grid.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))
from schgen import Sheet, prepare_project  # noqa: E402
from sexpr import Q  # noqa: E402

PROJECT = ROOT / "hw" / "ui"
NAME = "Slewn_V20_UI"
OLD_SCH = ROOT / "old" / "ui-backup-2026-11-21" / f"{NAME}.kicad_sch"
OUT = ROOT / "out" / "ui_sch" / "full" / f"{NAME}.kicad_sch"

SYMBOL_MAP: dict[str, str] = {
    "J101": "Connector_Generic:Conn_01x14",
    "J102": "Connector_Generic:Conn_01x08",
    "ENC101": "Device:RotaryEncoder_Switch_MP",
    **{r: "Device:R" for r in ("R101", "R102", "R103", "R104")},
    **{c: "Device:C" for c in ("C101", "C102", "C103", "C104")},
}
# unchanged from the old sheet: the UI PCB is not touched by the redraw
FOOTPRINT_MAP: dict[str, str] = {
    "J101": "Kinghelm:KH-2.54FH-1X14P-H8.5",
    "J102": "SlewnV13_UI:J2_TFT8",
    "ENC101": "SlewnV13_UI:ENC1_ENCODER",
    # 2026-11-22: KiCad's stock 0805 footprints replace the project-local copies (same size and place)
    **{r: "Resistor_SMD:R_0805_2012Metric" for r in ("R101", "R102", "R103", "R104")},
    **{c: "Capacitor_SMD:C_0805_2012Metric" for c in ("C101", "C102", "C103", "C104")},
}
OLD_FOOTPRINTS = {**{f"R10{i}": f"SlewnV13_UI:R{i}_R0805" for i in range(1, 4)}, "R104": "SlewnV13_UI:R5_R0805",
                  **{f"C10{i}": f"SlewnV13_UI:C{i}_C0805" for i in range(1, 5)}}

# J101 pin -> net: the order agreed on 2026-11-21, equal to MAIN J2 with the UI_ prefix
J101_NETS = {"1": "GND", "2": "5V", "3": "SPI_CLK", "4": "SPI_MOSI", "5": "LCD_RST", "6": "LCD_DC", "7": "LCD_CS",
             "8": "LCD_BL", "9": "GND", "10": "3V3", "11": "ENC_A", "12": "ENC_B", "13": "ENC_SW", "14": "GND"}
# display header J102 in the order of the TB147 module (GoldenMorning GMT147-01M): GND VDD SCL SDA RES DC CS BL
J102_NETS = {"1": "GND", "2": "5V", "3": "SPI_CLK", "4": "SPI_MOSI", "5": "LCD_RST", "6": "LCD_DC",
             "7": "LCD_CS", "8": "LCD_BL"}
TOP = 17.78
BOTTOM = 109.22

# complexity review 2026-11-21, DIY level: R104 was a 0R service link that no build step uses
REMOVED = {"R104"}
MERGED = {"/UI_TFT_5V": "/UI_5V"}
# references closed up after the removal (old sheet -> this sheet); the symbol keeps its UUID
RENAMED = {"R105": "R104"}
# kept on the sheet as Do Not Populate: the TB147 module carries its own LDO and capacitors (C104); the RK3566
# holds LCD_BL (GPIO3_B2) low from reset with its internal pull-down (R104); ENC_SW is debounced in software (C103)
DNP = {"C104", "R104", "C103"}

# order numbers (2026-11-22): R/C moved to JLCPCB basic parts (no feeder fee, deep stock); the KEMET 10 nF
# C0805C103K5RACTU had left JLCPCB's stock. Same values, 0805, X7R 50 V.
_R10K = {"MPN": "0805W8F1002T5E", "Manufacturer": "UNI-ROYAL", "LCSC": "C17414"}
_C10N = {"MPN": "CL21B103KBANNNC", "Manufacturer": "Samsung Electro-Mechanics", "LCSC": "C1710"}
FIELDS: dict[str, dict[str, str]] = {
    **{r: _R10K for r in ("R101", "R102", "R103", "R104")},
    **{c: _C10N for c in ("C101", "C102", "C103")},
    "C104": {"MPN": "CC0805KRX7R9BB104", "Manufacturer": "YAGEO", "LCSC": "C49678"},
    "ENC101": {"MPN": "PEC11R-4225F-S0024", "Manufacturer": "Bourns", "LCSC": "C18198884"},
    "J101": {"MPN": "KH-2.54FH-1X14P-H8.5", "Manufacturer": "Kinghelm", "LCSC": "C2905420"},
    "J102": {"MPN": "TSW-108-07-G-S", "Manufacturer": "Samtec", "LCSC": "C3335496"},
}


def net(name: str) -> str:
    return f"UI_{name}"


def stub(s: Sheet, ref: str, pin: str, name: str, side: int, length: float = 5.08) -> None:
    """Wire out of a pin (side -1 = left, +1 = right) ending in a net label."""
    x, y = s.pin(ref, pin)
    end = (x + length * side, y)
    s.wire((x, y), end)
    s.label(net(name), end, rot=0 if side > 0 else 180)


def block_connector(s: Sheet) -> None:
    s.box("1  J101  -  to MAIN J2", 15.24, TOP, 78.74, BOTTOM)
    s.place("J101", 55.88, 53.34, fields=(30.48, 80.01))
    for n in range(1, 15):
        stub(s, "J101", str(n), J101_NETS[str(n)], -1)
    s.note("1-8 display, 9-14 encoder.", (17.78, 93.98), size=1.27)
    s.note("Pin for pin to MAIN J2.", (17.78, 97.79), size=1.27)


def block_display(s: Sheet) -> None:
    s.box("2  DISPLAY  J102", 81.28, TOP, 167.64, BOTTOM)
    s.place("J102", 152.4, 40.64, fields=(101.6, 58.42))
    for n in range(1, 9):
        stub(s, "J102", str(n), J102_NETS[str(n)], -1)
    # backlight pull-down, spare (DNP)
    s.place("R104", 152.4, 71.12, fields="left", dnp=True)
    s.wire("R104.1", (152.4, 64.77))
    s.label(net("LCD_BL"), (152.4, 64.77), rot=90)
    s.wire("R104.2", (152.4, 77.47))
    s.label(net("GND"), (152.4, 77.47), rot=270)
    # display 5 V decoupling, spare (DNP): the module has its own
    s.place("C104", 124.46, 92.71, fields="right", dnp=True)
    s.wire("C104.1", (124.46, 86.36))
    s.label(net("5V"), (124.46, 86.36), rot=90)
    s.wire("C104.2", (124.46, 99.06))
    s.label(net("GND"), (124.46, 99.06), rot=270)


ENC_COLS = (("R101", "C101", "ENC_A"), ("R102", "C102", "ENC_B"), ("R103", "C103", "ENC_SW"))


def block_encoder(s: Sheet) -> None:
    s.box("3  ENCODER  ENC101", 170.18, TOP, 284.48, BOTTOM)
    # pull-up to 3V3 and 10 nF to GND on each encoder line
    rail_top, rail_gnd = 30.48, 63.5
    xs = [180.34 + 20.32 * i for i in range(3)]
    s.wire((xs[0], rail_top), (xs[-1], rail_top))
    s.label(net("3V3"), (xs[0], rail_top))
    s.wire((xs[0], rail_gnd), (xs[-1], rail_gnd))
    s.label(net("GND"), (xs[0], rail_gnd), rot=270)
    for x, (r, c, name) in zip(xs, ENC_COLS):
        s.place(r, x, 36.83, fields="right")
        s.wire(f"{r}.1", (x, rail_top))
        s.place(c, x, 53.34, fields="right", dnp=c in DNP)
        s.wire(f"{r}.2", f"{c}.1")
        s.wire(f"{c}.2", (x, rail_gnd))
        node = (x, 45.72)
        s.wire(node, (x + 2.54, 45.72))
        s.label(net(name), (x + 2.54, 45.72))
    s.place("ENC101", 226.06, 86.36, fields=(237.49, 76.2))
    stub(s, "ENC101", "A", "ENC_A", -1)
    stub(s, "ENC101", "C", "GND", -1)
    stub(s, "ENC101", "B", "ENC_B", -1)
    stub(s, "ENC101", "S1", "ENC_SW", 1)
    # switch common and mounting lugs share one ground
    xs2, ys2 = s.pin("ENC101", "S2")
    xm, ym = s.pin("ENC101", "MP")
    s.wire((xs2, ys2), (xs2 + 2.54, ys2), (xs2 + 2.54, ym + 2.54), (xm, ym + 2.54), (xm, ym))
    s.label(net("GND"), (xs2 + 2.54, ym + 2.54), rot=270)


NOTES = [
    "R101-R103 pull-ups, C101-C102 10 nF: the noise filter Bourns asks for on PEC11R A/B.",
    "DIY level, no protection on this board (complexity review 2026-11-21). 0R link in the 5 V feed removed.",
    "C103, C104, R104: DNP, spare pads only.",
    "    C103: ENC_SW is debounced in software (gpio-keys, debounce-interval).",
    "    C104: the TB147 display module carries its own LDO and capacitors.",
    "    R104: the RK3566 holds LCD_BL low from reset (internal pull-down).",
]


def notes(s: Sheet) -> None:
    x = 15.24
    s.note("UI   /   J101 接 MAIN 的 J2，按 1 至 14 脚逐一对应。", (x, 119.38), size=2.2)
    s.note("背面装直母座，开口朝箱内。", (x, 124.46), size=2.2)
    for i, line in enumerate(NOTES):
        s.note(line, (x, 134.62 + 3.81 * i))


BLOCKS = {"connector": block_connector, "display": block_display, "encoder": block_encoder, "notes": notes}


def make_sheet(blocks: list[str] | None = None) -> Sheet:
    s = Sheet(OLD_SCH, paper="A4", project=NAME, symbol_map=SYMBOL_MAP, footprint_map=FOOTPRINT_MAP)
    for ref in REMOVED:
        del s.old[ref]
    for old_ref, ref in RENAMED.items():
        s.old[ref] = s.old.pop(old_ref)
        s.old[ref]["props"]["Reference"] = (ref, False)
    for old in s.old.values():
        # the old sheet left out the fields KiCad 10 always writes
        for name in ("Datasheet", "Description"):
            old["props"].setdefault(name, ("", True))
    for ref, fields in FIELDS.items():
        props = s.old[ref]["props"]
        for name, value in fields.items():
            props[name] = (value, props[name][1] if name in props else True)
    for item in s.title_block[1:]:
        if item[0] == "date":
            item[1] = Q("2026-11-21")
        if item[:2] == ["comment", "2"]:
            item[2] = Q("MAIN / UI connector pins mate 1:1; check 5 V before fitting the Radxa.")
    for name in blocks or list(BLOCKS):
        BLOCKS[name](s)
    return s


def build(out: Path = OUT, blocks: list[str] | None = None) -> Path:
    s = make_sheet(blocks)
    prepare_project(Path(out).parent, PROJECT, NAME)
    return s.write(out)


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT))
