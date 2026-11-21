import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import fpcheck  # noqa: E402
import netlist  # noqa: E402
from parts import FOOTPRINT_MAP, NEW_PARTS, SYMBOL_MAP, footprint_file, symbol_pin_types, symbol_pins  # noqa: E402
from schgen import pin_name_boxes  # noqa: E402

OLD = ROOT / "old" / "main-backup-2026-11-20"
LIB = ROOT / "hw" / "main" / "library" / "Slewn_MAIN.kicad_sym"
OUT = ROOT / "out" / "main_sch"


class SymbolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = netlist.load(netlist.export(OLD / "Slewn_V20_MAIN.kicad_sch", OUT / "old.net"))

    def test_all_refs_mapped(self):
        self.assertEqual(set(SYMBOL_MAP), set(self.old.comps) | NEW_PARTS)

    def test_symbol_pins_match_footprint_pads(self):
        for ref in sorted(SYMBOL_MAP):
            with self.subTest(ref=ref):
                pads = {n for n in fpcheck.pads(footprint_file(FOOTPRINT_MAP[ref])) if n}
                self.assertEqual(set(symbol_pins(SYMBOL_MAP[ref])), pads)

    def test_u1_pins(self):
        pins = symbol_pins("Slewn_MAIN:Waveshare_DC536_5V")
        types = symbol_pin_types("Slewn_MAIN:Waveshare_DC536_5V")
        self.assertEqual(set(pins), {"I1", "I2", "I3", "I4", "O1", "O2", "O3", "O4", "O5", "O6"})
        names = {p: pins[p] for p in pins}
        self.assertEqual(names, {"I1": "GND", "I2": "GND", "I3": "VIN", "I4": "VIN", "O1": "GND", "O2": "GND",
                                 "O3": "GND", "O4": "5V", "O5": "5V", "O6": "5V"})
        # the first pin of each stack carries the type, the hidden rest are passive
        self.assertEqual({p: types[p] for p in ("I3", "I1", "O4", "O1")},
                         {"I3": "power_in", "I1": "power_in", "O4": "power_out", "O1": "power_in"})
        self.assertEqual({types[p] for p in ("I4", "I2", "O5", "O6", "O2", "O3")}, {"passive"})

    def test_tps25940_names(self):
        pins = {k: v.upper() for k, v in symbol_pins("Slewn_MAIN:TPS25940LRVCR").items()}
        self.assertEqual(pins["15"], "OVP")
        self.assertEqual(pins["17"], "ILIM")
        self.assertEqual(pins["18"], "DVDT")
        self.assertEqual(pins["14"], "EN/UVLO")
        self.assertIn("21", pins)

    def test_no_unspecified_pins(self):
        for lib_id in ("Slewn_MAIN:TPS25940LRVCR", "Slewn_MAIN:AO4407A", "Slewn_MAIN:Waveshare_DC536_5V"):
            with self.subTest(lib_id=lib_id):
                self.assertNotIn("unspecified", set(symbol_pin_types(lib_id).values()))

    def test_ao4407a_pinout(self):
        pins = symbol_pins("Slewn_MAIN:AO4407A")
        self.assertEqual({k for k, v in pins.items() if v == "S"}, {"1", "2", "3"})
        self.assertEqual({k for k, v in pins.items() if v == "G"}, {"4"})
        self.assertEqual({k for k, v in pins.items() if v == "D"}, {"5", "6", "7", "8"})

    def test_pin_names_do_not_overlap(self):
        for lib_id in ("Slewn_MAIN:TPS25940LRVCR", "Slewn_MAIN:Waveshare_DC536_5V"):
            boxes = pin_name_boxes(lib_id)
            for i, (na, a) in enumerate(boxes):
                for nb, b in boxes[i + 1:]:
                    with self.subTest(lib_id=lib_id, a=na, b=nb):
                        self.assertFalse(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])

    def test_library_parses(self):
        out = OUT / "symcheck.kicad_sym"
        out.unlink(missing_ok=True)
        r = subprocess.run(["kicad-cli", "sym", "upgrade", "--force", str(LIB), "-o", str(out)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
