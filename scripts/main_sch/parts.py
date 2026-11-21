"""Per-reference symbol and footprint choices for the MAIN redraw (spec: symbol map, footprint map)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "hw" / "main"
KICAD_FP = Path("/usr/share/kicad/footprints")
KICAD_SYM = Path("/usr/share/kicad/symbols")
LEGACY_LIBS = {"SlewnV13", "V16", "Kinghelm"}

_STOCK_FP = {
    "C1": "Capacitor_SMD:C_1210_3225Metric",
    "C2": "Capacitor_SMD:C_1210_3225Metric",
    "D1": "Diode_SMD:D_SOD-123",
    "F1": "Fuse:Fuse_1206_3216Metric",
    "Q1": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "R1": "Resistor_SMD:R_0805_2012Metric",
    # kept as-is: stock or LCSC pads differ (J1 rotated, J3/J2 drill, L1 pad size, U1 no library)
    "J1": "Slewn_MAIN:J1_GPIO40",
    "J3": "Slewn_MAIN:J3_IDC10",
    "U1": "Slewn_MAIN:U1_Waveshare33x16",
    "J2": "Slewn_MAIN:KH-2.54PH90-1X14P-L13.8",
    "L1": "Slewn_MAIN:WE_LHMI_74437324022",
}

_TP = "TestPoint:TestPoint_Pad_D1.5mm"
_R0805 = "Resistor_SMD:R_0805_2012Metric"
_C0805 = "Capacitor_SMD:C_0805_2012Metric"
_C1210 = "Capacitor_SMD:C_1210_3225Metric"
_DSMA = "Diode_SMD:D_SMA"
_RVC = "Package_DFN_QFN:Texas_RVC0020A_WQFN-20-1EP_3x4mm_P0.5mm_EP1.6x2.6mm"

# parts added after the redraw; they have no footprint in the old sheet to compare against
NEW_PARTS = {"J4", "R2", "R3"}

FOOTPRINT_MAP: dict[str, str] = {
    **{f"TP{i}": _TP for i in range(1, 8)},
    **{r: _R0805 for r in ("R10", "R11", "R12", "R14", "R15", "R16")},
    **{c: _C0805 for c in ("C6", "C10", "C11", "C12", "C13")},
    "C3": _C1210, "C4": _C1210,
    "C5": "Capacitor_SMD:CP_Elec_6.3x5.8",
    "D2": _DSMA, "D3": _DSMA, "D4": _DSMA,
    "R18": "Resistor_SMD:R_1206_3216Metric",
    "R20": "Resistor_SMD:R_2512_6332Metric",
    "U2": _RVC, "U3": _RVC,
    "J4": "Connector_PinHeader_2.54mm:PinHeader_2x17_P2.54mm_Vertical",
    "R2": _R0805, "R3": _R0805,
    **_STOCK_FP,
}


def footprint_file(lib_id: str, project: Path = PROJECT, legacy: bool = False) -> Path:
    """Resolve a footprint lib ID to its .kicad_mod file."""
    lib, name = lib_id.split(":", 1)
    if lib == "Slewn_MAIN":
        return project / "library" / "Slewn_MAIN.pretty" / f"{name}.kicad_mod"
    if lib in LEGACY_LIBS:
        if not legacy:
            raise ValueError(f"{lib_id} points at the legacy Libs/ folder")
        return project / "Libs" / f"{lib}.pretty" / f"{name}.kicad_mod"
    return KICAD_FP / f"{lib}.pretty" / f"{name}.kicad_mod"


SYMBOL_MAP: dict[str, str] = {
    **{f"TP{i}": "Connector:TestPoint" for i in range(1, 8)},
    **{r: "Device:R" for r in ("R1", "R2", "R3", "R10", "R11", "R12", "R14", "R15", "R16", "R18", "R20")},
    **{c: "Device:C" for c in ("C1", "C2", "C3", "C4", "C6", "C10", "C11", "C12", "C13")},
    "C5": "Device:C_Polarized",
    "L1": "Device:L",
    "D1": "Device:D_Zener",
    "D2": "Diode:SMAJ12A",
    "D3": "Device:D_Schottky", "D4": "Device:D_Schottky",
    "F1": "Device:Fuse",
    "Q1": "Slewn_MAIN:AO4407A",
    "U1": "Slewn_MAIN:Waveshare_DC536_5V",
    "U2": "Slewn_MAIN:TPS25940LRVCR", "U3": "Slewn_MAIN:TPS25940LRVCR",
    "J1": "Connector_Generic:Conn_02x20_Odd_Even",
    "J2": "Connector_Generic:Conn_01x14",
    "J3": "Connector_Generic:Conn_02x05_Odd_Even",
    "J4": "Connector_Generic:Conn_02x17_Odd_Even",
}

_lib_cache: dict[Path, list] = {}


def _library(lib: str) -> list:
    import sexpr
    path = PROJECT / "library" / "Slewn_MAIN.kicad_sym" if lib == "Slewn_MAIN" else KICAD_SYM / f"{lib}.kicad_sym"
    if path not in _lib_cache:
        _lib_cache[path] = sexpr.parse(path.read_text())
    return _lib_cache[path]


def load_symbol(lib_id: str) -> list:
    """The symbol as a schematic embeds it: named `Lib:Name`, with any `extends` flattened."""
    import copy
    import sexpr
    lib, name = lib_id.split(":", 1)
    syms = {s[1]: s for s in sexpr.find_all(_library(lib), "symbol")}
    sym = syms[name]
    ext = sexpr.find(sym, "extends")
    if ext:
        base = copy.deepcopy(load_symbol(f"{lib}:{ext[1]}"))
        child_props = {p[1]: p for p in sexpr.find_all(sym, "property")}
        out = [base[0], sexpr.Q(lib_id)]
        for item in base[2:]:
            if isinstance(item, list) and item[0] == "property" and item[1] in child_props:
                item = child_props.pop(item[1])
            elif isinstance(item, list) and item[0] == "symbol":
                item = [item[0], sexpr.Q(item[1].replace(ext[1] + "_", name + "_", 1))] + item[2:]
            out.append(item)
        # child-only properties go after the inherited ones
        last_prop = max(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == "property")
        out[last_prop + 1:last_prop + 1] = list(child_props.values())
        return out
    out = copy.deepcopy(sym)
    out[1] = sexpr.Q(lib_id)
    return out


def _pins(lib_id: str) -> list[list]:
    import sexpr
    return [p for u in sexpr.find_all(load_symbol(lib_id), "symbol") for p in sexpr.find_all(u, "pin")]


def symbol_pins(lib_id: str) -> dict[str, str]:
    import sexpr
    return {sexpr.find(p, "number")[1]: sexpr.find(p, "name")[1] for p in _pins(lib_id)}


def symbol_pin_types(lib_id: str) -> dict[str, str]:
    import sexpr
    return {sexpr.find(p, "number")[1]: p[1] for p in _pins(lib_id)}
