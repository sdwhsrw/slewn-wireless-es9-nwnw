"""Build hw/main/library/Slewn_MAIN.kicad_sym.

AO4407A and TPS25940LRVCR take their pin numbers and names from the LCSC/EasyEDA imports
(library/lcsc_import/lcsc.kicad_sym, made with easyeda2kicad 1.0.1), redrawn for readability:
AO4407A uses the body of KiCad's Device:Q_PMOS; TPS25940 puts inputs left, outputs right,
ground and set-up pins at the bottom. Waveshare_DC536_5V is drawn here (no library has it).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parts import PROJECT, ROOT, load_symbol  # noqa: E402
from sexpr import Q, dump, find, find_all, parse  # noqa: E402

LCSC_LIB = PROJECT / "library" / "lcsc_import" / "lcsc.kicad_sym"
OUT = PROJECT / "library" / "Slewn_MAIN.kicad_sym"
FONT = ["effects", ["font", ["size", "1.27", "1.27"]]]


def prop(name, value, x=0.0, y=0.0, hide=True, justify=None):
    eff = ["effects", ["font", ["size", "1.27", "1.27"]]]
    if justify:
        eff.append(["justify", justify])
    p = ["property", Q(name), Q(value), ["at", f"{x:g}", f"{y:g}", "0"]]
    if hide:
        p.append(["hide", "yes"])
    return p + [eff]


def pin(kind, x, y, rot, name, number, hidden=False, length=2.54):
    p = ["pin", kind, "line", ["at", f"{x:g}", f"{y:g}", str(rot)], ["length", f"{length:g}"]]
    if hidden:
        p.append(["hide", "yes"])
    return p + [["name", Q(name), FONT], ["number", Q(number), FONT]]


def stacked(kind, x, y, rot, name, numbers):
    """Pins sharing one position connect together; only the first is visible."""
    return [pin(kind if i == 0 else "passive", x, y, rot, name, n, hidden=i > 0) for i, n in enumerate(numbers)]


def rect(x1, y1, x2, y2):
    return ["rectangle", ["start", f"{x1:g}", f"{y1:g}"], ["end", f"{x2:g}", f"{y2:g}"],
            ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", "background"]]]


def symbol(name, props, graphics, pins, pin_names_hidden=False, pin_numbers_hidden=False):
    s = ["symbol", Q(name)]
    if pin_numbers_hidden:
        s.append(["pin_numbers", ["hide", "yes"]])
    s.append(["pin_names", ["offset", "0.508"]] + ([["hide", "yes"]] if pin_names_hidden else []))
    s += [["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"]]
    s += props
    s.append(["symbol", Q(f"{name}_0_1")] + graphics)
    s.append(["symbol", Q(f"{name}_1_1")] + pins)
    s.append(["embedded_fonts", "no"])
    return s


def lcsc_pins(name: str) -> dict[str, str]:
    lib = parse(LCSC_LIB.read_text())
    sym = next(s for s in find_all(lib, "symbol") if s[1] == name)
    return {find(p, "number")[1]: find(p, "name")[1] for u in find_all(sym, "symbol") for p in find_all(u, "pin")}


def ao4407a():
    names = lcsc_pins("AO4407A")
    by = lambda n: sorted(k for k, v in names.items() if v == n)  # noqa: E731
    body = [x for x in load_symbol("Device:Q_PMOS") if isinstance(x, list) and x[0] == "symbol" and x[1].endswith("_0_1")][0][2:]
    props = [prop("Reference", "Q", 5.08, 1.27, hide=False, justify="left"),
             prop("Value", "AO4407A", 5.08, -1.27, hide=False, justify="left"),
             prop("Footprint", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", 5.08, -3.81),
             prop("Datasheet", "https://www.aosmd.com/res/datasheets/AO4407A.pdf"),
             prop("Description", "-30V P-channel MOSFET, SO-8 (S=1-3, G=4, D=5-8)"),
             prop("MPN", "AO4407A"), prop("Manufacturer", "Alpha & Omega Semiconductor"), prop("LCSC", "C16072")]
    pins = stacked("passive", 2.54, 5.08, 270, "D", by("D")) + [pin("input", -5.08, 0, 0, "G", by("G")[0])] \
        + stacked("passive", 2.54, -5.08, 90, "S", by("S"))
    return symbol("AO4407A", props, body, pins, pin_names_hidden=True, pin_numbers_hidden=True)


def tps25940():
    names = lcsc_pins("TPS25940LRVCR")
    by = lambda n: sorted((k for k, v in names.items() if v == n), key=int)  # noqa: E731
    w, h = 10.16, 10.16
    props = [prop("Reference", "U", -w, h + 1.27, hide=False, justify="left"),
             prop("Value", "TPS25940LRVCR", -w, -h - 6.35, hide=False, justify="left"),
             prop("Footprint", "Package_DFN_QFN:Texas_RVC0020A_WQFN-20-1EP_3x4mm_P0.5mm_EP1.6x2.6mm"),
             prop("Datasheet", "https://www.ti.com/lit/ds/symlink/tps25940.pdf"),
             prop("Description", "2.7-18V eFuse with OVP, dV/dt and current limit, WQFN-20"),
             prop("MPN", "TPS25940LRVCR"), prop("Manufacturer", "Texas Instruments"), prop("LCSC", "C2867756")]
    x_l, x_r, y_b = -w - 2.54, w + 2.54, -h - 2.54
    pins = stacked("power_in", x_l, 7.62, 0, "IN", by("IN")) + [
        pin("input", x_l, 2.54, 0, "EN/UVLO", "14"),
        pin("input", x_l, 0, 0, "OVP", "15"),
        pin("input", x_l, -2.54, 0, "DEVSLP", "1"),
    ] + stacked("power_out", x_r, 7.62, 180, "OUT", by("OUT")) + [
        pin("open_collector", x_r, 2.54, 180, "PGOOD", "2"),
        pin("open_collector", x_r, 0, 180, "~{FLT}", "20"),
        pin("output", x_r, -2.54, 180, "IMON", "19"),
        pin("input", -7.62, y_b, 90, "PGTH", "3"),
        pin("passive", -2.54, y_b, 90, "dVdT", "18"),
        pin("passive", 2.54, y_b, 90, "ILIM", "17"),
    ] + stacked("power_in", 7.62, y_b, 90, "GND", ["16", "21"])
    return symbol("TPS25940LRVCR", props, [rect(-w, h, w, -h)], pins)


def waveshare():
    w, h = 7.62, 5.08
    props = [prop("Reference", "U", -w, h + 1.27, hide=False, justify="left"),
             prop("Value", "Waveshare DC5-36 to 5V", -w, -h - 1.27, hide=False, justify="left"),
             prop("Footprint", "Slewn_MAIN:U1_Waveshare33x16"),
             prop("Datasheet", ""),
             prop("Description", "Waveshare DC5-36V to 3.3/5V buck module, set to 5V (pads I1-I4 in, O1-O6 out)"),
             prop("MPN", "DC5-36-TO-DC3V3-5"), prop("Manufacturer", "Waveshare")]
    pins = stacked("power_in", -w - 2.54, 2.54, 0, "VIN", ["I3", "I4"]) \
        + stacked("power_in", -w - 2.54, -2.54, 0, "GND", ["I1", "I2"]) \
        + stacked("power_out", w + 2.54, 2.54, 180, "5V", ["O4", "O5", "O6"]) \
        + stacked("power_in", w + 2.54, -2.54, 180, "GND", ["O1", "O2", "O3"])
    return symbol("Waveshare_DC536_5V", props, [rect(-w, h, w, -h)], pins)


def build() -> Path:
    lib = ["kicad_symbol_lib", ["version", "20251024"], ["generator", Q("slewn_build_symbols")],
           ["generator_version", Q("10.0")], ao4407a(), tps25940(), waveshare()]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dump(lib) + "\n")
    return OUT


if __name__ == "__main__":
    print(build())
