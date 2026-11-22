"""MAIN sheet layout after the DIY complexity review: three titled blocks on A4.

Row 1 (rail y=40.64): 1 rack input -> 2 5V buck.  Row 2: 3 Radxa / UI headers, build notes beside it.
REMOVED lists the parts the review took out; MERGED names the nets they used to separate.
Every net that had a name keeps it through a label; all coordinates sit on the 1.27 mm grid.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schgen import Sheet, prepare_project  # noqa: E402
from sexpr import Q  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OLD_SCH = ROOT / "old" / "main-backup-2026-11-20" / "Slewn_V20_MAIN.kicad_sch"
ROW1 = 40.64

# complexity review 2026-11-21, DIY level: eFuses, TVS, gate Zener + its resistor, LC filter, service link,
# extra test pads
REMOVED = {"D1", "D2", "C1", "C12", "TP1",
           "U2", "R10", "R11", "R12", "C10", "C3", "D3", "TP2",
           "L1", "R18", "C5", "TP3",
           "R20", "TP4",
           "R1",
           "U3", "R14", "R15", "R16", "C11", "C6", "C13", "D4", "TP5"}
# field changes: TP6's value named a net that no longer exists; Q1 AO4407A is NRND, so the parts review
# (2026-11-21) moved it to AO4407C (same SOIC-8 pinout, V_GS +-25 V); F1 stays and gets its order numbers
FIELDS = {
    "TP6": {"Value": "5V"},
    "Q1": {"Value": "AO4407C / -30V P-MOS", "MPN": "AO4407C", "Manufacturer": "Alpha & Omega Semiconductor",
           "LCSC": "C469397"},
    # parts review 2026-11-22: 2.5 A leaves headroom for the Radxa at full load plus 1 A on J5
    "F1": {"Value": "046802.5NRHF / 2.5 A fast", "MPN": "046802.5NRHF", "Manufacturer": "Littelfuse",
           "LCSC": "C187612"},
    "J3": {"Manufacturer": "Würth Elektronik", "LCSC": "C4355000"},
    # 2x20 male header: 3 mm into the Radxa, 6 mm down through MAIN, body on the 6 mm standoffs (V20 3D model)
    "J1": {"MPN": "PZ254-2-20-Z-8.5", "Manufacturer": "HCTL", "LCSC": "C3012260"},
    # the old Murata parts are NRND / end of life; both stay DNP
    "C2": {"Value": "22uF 25V X7R 1210", "MPN": "CL32B226KAJNNNE", "Manufacturer": "Samsung Electro-Mechanics",
           "LCSC": "C309062"},
    "C4": {"Value": "10uF 50V X7R", "MPN": "UMK325AB7106KM-P", "Manufacturer": "Taiyo Yuden",
           "LCSC": "C337485"},
}
# kept on the sheet as Do Not Populate: the U1 module already carries its input and output capacitors
DNP = {"C4", "C2",
       "R2", "R3"}          # optional I2C5 pull-ups: the Radxa has none there, most I2C modules bring their own
MERGED = {"/GATE": "/GND", "/VIN_PROTECTED": "/12V_IN", "/V12_LIMITED": "/12V_IN", "/VIN_FILTERED": "/12V_IN",
          "/BUCK_RAW": "/5V", "/EF_IN5": "/5V", "/5V_SAFE": "/5V"}


def shunt(s: Sheet, ref: str, x: float, rail_y: float, rot: int = 0, fields="right") -> None:
    """Two-pin part hanging from a rail: pin 1 up to the rail, pin 2 to GND."""
    s.place(ref, x, rail_y + 6.35, rot=rot, fields=fields, dnp=ref in DNP)
    s.wire(f"{ref}.1", (x, rail_y))
    s.power("GND", s.pin(ref, "2"))


def testpoint(s: Sheet, ref: str, x: float, rail_y: float) -> None:
    s.place(ref, x, rail_y - 5.08, fields="above")
    s.wire(f"{ref}.1", (x, rail_y))


def block_rack_input(s: Sheet) -> None:
    s.box("1  RACK INPUT  -  fuse, reverse-polarity P-MOS", 15.24, 17.78, 116.84, 88.9)
    # J3 Eurorack 10-pin, turned so pins 9/10 (+12V) face the rail; 3-8 GND, 1-2 unused (-12V)
    s.place("J3", 30.48, 63.5, rot=180, fields=(17.78, 80.01))
    for p in ("3", "5", "7"):
        s.wire(f"J3.{p}", (38.1, s.pin("J3", p)[1]))
    for p in ("4", "6", "8"):
        s.wire(f"J3.{p}", (20.32, s.pin("J3", p)[1]))
    s.wire((38.1, 60.96), (38.1, 71.12))
    s.wire((20.32, 60.96), (20.32, 71.12))
    s.power("GND", (38.1, 71.12))
    s.power("GND", (20.32, 71.12))
    s.wire((38.1, 71.12), (43.18, 71.12))          # GND flag on J3's ground bus
    s.power("PWR_FLAG", (43.18, 71.12))
    s.nc("J3", "1")
    s.nc("J3", "2")
    s.wire("J3.10", (17.78, 58.42), (17.78, 53.34), (40.64, 53.34))
    s.wire("J3.9", (40.64, 58.42), (40.64, ROW1))
    s.label("RACK_12V", (40.64, 50.8), rot=90)
    s.place("F1", 57.15, ROW1, rot=90, fields="below")
    s.wire((40.64, ROW1), "F1.1")
    # reverse-polarity P-MOS: drain from the fuse, source to the 12 V rail
    s.place("Q1", 88.9, 43.18, rot=90)
    s.wire("F1.2", "Q1.5")
    s.label("VIN_FUSED", (63.5, ROW1))
    s.wire("Q1.4", (88.9, 53.34))                # gate straight to GND: V_GS = -12 V, AO4407A takes +-25 V
    s.power("GND", (88.9, 53.34))
    s.label("12V_IN", (99.06, ROW1))
    s.power("PWR_FLAG", (106.68, 35.56))
    s.wire((106.68, 35.56), (106.68, ROW1))
    s.place("TP7", 111.76, 63.5, fields="above")
    s.power("GND", (111.76, 63.5))


def block_buck(s: Sheet) -> None:
    s.box("2  5 V BUCK  -  Waveshare module, set to 5 V", 119.38, 17.78, 218.44, 88.9)
    s.place("U1", 165.1, 43.18, fields="below")
    s.wire("Q1.1", "U1.I3")                      # 12V_IN rail from block 1
    shunt(s, "C4", 132.08, ROW1)
    s.power("GND", s.pin("U1", "I1"))
    s.power("GND", s.pin("U1", "O1"))
    s.wire("U1.O4", (208.28, ROW1))
    shunt(s, "C2", 187.96, ROW1)
    s.label("5V", (198.12, ROW1))
    testpoint(s, "TP6", 208.28, ROW1)


# Radxa header pin -> net (approved 2026-11-21; the rest stay unconnected). The Radxa ties its 3V3 pins 1 and 17
# together, so MAIN keeps them apart (2026-11-22): 3V3_1 from J1.1 feeds the UI board, 3V3 from J1.17 feeds J5.
# J2 goes to the UI board pin for pin:
# 1-8 in the display's own order, 9-14 the encoder. J4 brings out every other signal, one block per function;
# J5 carries the power for J4 modules (split 2026-11-22 so J4 fits the right board edge and HDMI stays free).
# J4 order (2026-11-22): groups I2S, I2C, SPI, UART, GPIO from the top; inside the groups and between them
# the pins follow their x position on J1, so the J1 -> J4 traces fan out with few crossings.
J1_NETS = {"1": "3V3_1", "2": "5V", "3": "UART3_RX", "4": "5V", "5": "UART3_TX", "7": "GPIO3_C4", "8": "UART2_TX",
           "10": "UART2_RX", "11": "GPIO3_A1", "12": "I2S_BCLK", "13": "I2S_MCLK", "15": "LCD_RST", "16": "LCD_DC",
           "17": "3V3", "18": "LCD_BL", "19": "SPI_MOSI", "21": "SPI_MISO", "22": "SPI_CS1", "23": "SPI_CLK",
           "24": "LCD_CS", "27": "I2C4_SDA", "28": "I2C4_SCL", "29": "I2C5_SCL", "31": "I2C5_SDA", "32": "ENC_A",
           "33": "ENC_B", "35": "I2S_LRCK", "36": "ENC_SW", "37": "GPIO1_A4", "38": "I2S_DIN", "40": "I2S_DOUT",
           **{p: "GND" for p in ("6", "9", "14", "20", "25", "30", "34", "39")}}
J2_NETS = {"1": "GND", "2": "5V", "3": "SPI_CLK", "4": "SPI_MOSI", "5": "LCD_RST", "6": "LCD_DC", "7": "LCD_CS",
           "8": "LCD_BL", "9": "GND", "10": "3V3_1", "11": "ENC_A", "12": "ENC_B", "13": "ENC_SW", "14": "GND"}
J4_NETS = {"1": "I2S_DOUT", "2": "I2S_DIN", "3": "I2S_LRCK", "4": "I2S_MCLK", "5": "I2S_BCLK", "6": "GND",
           "7": "I2C5_SDA", "8": "I2C5_SCL", "9": "I2C4_SCL", "10": "I2C4_SDA", "11": "GND", "12": "GND",
           "13": "SPI_CLK", "14": "SPI_MISO", "15": "SPI_CS1", "16": "SPI_MOSI", "17": "GND", "18": "GND",
           "19": "UART2_RX", "20": "UART2_TX", "21": "UART3_TX", "22": "UART3_RX", "23": "GND", "24": "GND",
           "25": "GPIO1_A4", "26": "GPIO3_A1", "27": "GPIO3_C4", "28": "GND"}
J5_NETS = {"1": "5V", "2": "5V", "3": "3V3", "4": "3V3", "5": "GND", "6": "GND"}


def _header_pin(s: Sheet, ref: str, pin: str, net: str | None, side: int) -> None:
    """Stub of 5.08 mm out of a header pin (side -1 = left, +1 = right), ending in a label or GND."""
    x, y = s.pin(ref, pin)
    if net is None:
        s.nc(ref, pin)
        return
    end = (x + 5.08 * side, y)
    s.wire((x, y), end)
    if net == "GND":
        # no "GND" text: at 2.54 mm pitch it would run into the next pin's label
        s.power("GND", end, rot=90 if side > 0 else 270, show_value=False)
    else:
        s.label(net, end, rot=0 if side > 0 else 180)


HX, HY = 15.24, 91.44                            # top-left corner of block 3


def block_headers(s: Sheet) -> None:
    s.box("3  RADXA ZERO 3W  +  UI CONNECTOR", HX, HY, HX + 134.62, HY + 93.98)
    s.place("J1", HX + 35.56, HY + 45.72, fields=(HX + 20.32, HY + 78.74))
    for n in range(1, 41):
        p = str(n)
        if p in ("2", "4"):
            continue
        _header_pin(s, "J1", p, J1_NETS.get(p), -1 if n % 2 else 1)
    s.wire("J1.2", (HX + 48.26, HY + 22.86), (HX + 48.26, HY + 25.4), "J1.4")
    s.label("5V", (HX + 48.26, HY + 22.86))
    s.place("J2", HX + 101.6, HY + 45.72, fields=(HX + 91.44, HY + 69.85))
    for n in range(1, 15):
        _header_pin(s, "J2", str(n), J2_NETS[str(n)], -1)
    i2c5_pullups(s)


def i2c5_pullups(s: Sheet) -> None:
    """R2/R3 from I2C5 to 3V3, below J2 in block 3; not fitted unless the module on J4 lacks pull-ups."""
    for ref, x, net in (("R2", 106.68, "I2C5_SCL"), ("R3", 124.46, "I2C5_SDA")):
        s.place(ref, x, 175.26, fields="right", dnp=True)
        s.wire(f"{ref}.1", (x, 168.91))
        s.label("3V3", (x, 168.91))
        s.wire(f"{ref}.2", (x, 181.61))
        s.label(net, (x, 181.61))


def block_expansion(s: Sheet) -> None:
    s.box("4  EXPANSION  J4 + POWER  J5", 220.98, 17.78, 284.48, 95.25)
    s.place("J4", 252.73, 40.64, fields=(231.14, 60.96))
    for n in range(1, 29):
        _header_pin(s, "J4", str(n), J4_NETS[str(n)], -1 if n % 2 else 1)
    s.place("J5", 252.73, 71.12, fields="below")
    for n in range(1, 7):
        _header_pin(s, "J5", str(n), J5_NETS[str(n)], -1 if n % 2 else 1)
    s.note("SPI: same bus as the display, CS1 on J1 22.", (223.52, 85.09), size=1.27)
    s.note("UART2 is the boot console, 1 500 000 baud.", (223.52, 88.9), size=1.27)
    s.note("J5 budget: 5V max 1 A, 3V3 (Radxa) small loads.", (223.52, 92.71), size=1.27)


BUILD_NOTES = [
    "1  Keyed ribbon cable, red stripe to -12 V at both ends.",
    "    Q1 blocks a reversed cable.",
    "2  Check that U1 is set to 5 V.",
    "3  Power up WITHOUT the Radxa: TP6 to TP7 reads 4.9-5.2 V.",
    "4  Only then fit the Radxa.",
    "5  Other modules in the rack whine? Add a ferrite bead",
    "    in series with 12V_IN before U1.",
]


def notes(s: Sheet) -> None:
    x = 157.48
    s.note("MAIN   /   J2 接 UI 的 J101，按 1 至 14 脚逐一对应。", (x, 97.79), size=2.2)
    s.note("正面装原厂 90° 公排针，插向面板。", (x, 102.87), size=2.2)
    s.note("BUILD AND BRING-UP", (x, 113.03), bold=True)
    for i, line in enumerate(BUILD_NOTES):
        s.note(line, (x, 118.11 + 3.81 * i))
    s.note("DIY level: no eFuse, TVS, input filter or service link (complexity review 2026-11-21).",
           (x, 149.86), size=1.27)
    s.note("C2, C4: DNP, spare pads only. The U1 module carries its own input and output capacitors.",
           (x, 152.40), size=1.27)


BLOCKS = {
    "rack": block_rack_input,
    "buck": block_buck,
    "headers": block_headers,
    "expansion": block_expansion,
    "notes": notes,
}


def make_sheet(blocks: list[str] | None = None) -> Sheet:
    s = Sheet(OLD_SCH, paper="A4")
    s.add_part("J4", "PinHeader 2x14 2.54 / expansion",
               "Radxa expansion: I2S3_M0, SPI3 with CS1, I2C5, I2C4, UART2 (debug), UART3, spare GPIO")
    s.add_part("J5", "PinHeader 2x03 2.54", "Power for J4 modules: 5V, 3V3, GND")
    for ref, mpn, lcsc in (("J4", "PZ254-2-14-Z-8.5", "C2894975"), ("J5", "PZ254-2-03-Z-8.5", "C2894964")):
        for name, value in (("MPN", mpn), ("Manufacturer", "HCTL"), ("LCSC", lcsc)):
            s.old[ref]["props"][name] = (value, True)
    for ref, net in (("R2", "SCL"), ("R3", "SDA")):
        s.add_part(ref, "4.7k 1% 0805", f"Optional I2C5 {net} pull-up to 3V3 (DNP)")
        for name, value in (("MPN", "0805W8F4701T5E"), ("Manufacturer", "UNI-ROYAL"), ("LCSC", "C17673")):
            s.old[ref]["props"][name] = (value, True)
    for ref, fields in FIELDS.items():
        props = s.old[ref]["props"]
        for name, value in fields.items():
            props[name] = (value, props[name][1] if name in props else True)
    for item in s.title_block[1:]:
        if item[0] == "date":
            item[1] = Q("2026-11-22")
        if item[:2] == ["comment", "2"]:
            item[2] = Q("MAIN / UI connector pins mate 1:1; check 5 V before fitting the Radxa.")
    for name in blocks or list(BLOCKS):
        BLOCKS[name](s)
    return s


def build(out: Path, blocks: list[str] | None = None) -> Path:
    s = make_sheet(blocks)
    prepare_project(Path(out).parent)
    return s.write(out)


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "main_sch" / "full" / "Slewn_V20_MAIN.kicad_sch"))
