import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import netlist  # noqa: E402
import schgen  # noqa: E402
from parts import SYMBOL_MAP  # noqa: E402

OLD_SCH = ROOT / "old" / "main-backup-2026-11-20" / "Slewn_V20_MAIN.kicad_sch"
OUT = ROOT / "out" / "main_sch"


def write_project(sheet, name):
    d = OUT / name
    schgen.prepare_project(d)
    return sheet.write(d / "Slewn_V20_MAIN.kicad_sch")


class SchGenTest(unittest.TestCase):
    def test_pin_transform(self):
        s = schgen.Sheet(OLD_SCH)
        s.place("R10", 101.6, 101.6)
        self.assertEqual(s.pin("R10", "1"), (101.6, 97.79))
        s.place("R11", 101.6, 101.6, rot=90)
        self.assertEqual(s.pin("R11", "1"), (97.79, 101.6))

    def test_roundtrip_minimal(self):
        s = schgen.Sheet(OLD_SCH)
        s.place("R10", 101.6, 101.6)
        s.place("R11", 101.6, 114.3)
        s.wire("R10.2", "R11.1")
        s.label("OV2", (101.6, 107.95))
        s.power("GND", s.pin("R11", "2"))
        sch = write_project(s, "t_min")
        new = netlist.load(netlist.export(sch, sch.with_suffix(".net")))
        self.assertEqual(new.nets["/OV2"], frozenset({("R10", "2"), ("R11", "1")}))
        self.assertIn(("R11", "2"), new.nets["GND"])
        self.assertEqual(new.comps["R10"]["value"], "124k 0.1%")
        text = sch.read_text()
        self.assertIn(schgen.Sheet(OLD_SCH).old["R10"]["uuid"], text)

    def test_junctions(self):
        s = schgen.Sheet(OLD_SCH)
        s.wire((50.8, 50.8), (76.2, 50.8))
        s.wire((63.5, 50.8), (63.5, 63.5))
        sch = write_project(s, "t_junc")
        self.assertEqual(sch.read_text().count("(junction"), 1)
        self.assertEqual(s.junctions(), [(63.5, 50.8)])

    def test_field_text_stays_horizontal_and_readable(self):
        # KiCad applies the symbol rotation to field angle and justification
        s = schgen.Sheet(OLD_SCH)
        for ref, rot in (("R10", 0), ("R11", 90), ("R12", 180), ("R14", 270)):
            s.place(ref, 50.8, 50.8, rot=rot, fields="right")
        got = {r: s.field_style(r) for r in ("R10", "R11", "R12", "R14")}
        self.assertEqual(got, {"R10": ("0", "left"), "R11": ("90", "right"),
                               "R12": ("0", "right"), "R14": ("90", "left")})

    def test_offset_shifts_literals_not_pin_coordinates(self):
        s = schgen.Sheet(OLD_SCH)
        with s.offset(10.16):
            s.place("R10", 50.8, 50.8)
            s.power("GND", s.pin("R10", "2"))
            s.wire((50.8, 40.64), (55.88, 40.64))
        self.assertEqual(s.pin("R10", "2"), (60.96, 54.61))
        gnd = next(v for k, v in s.symbols.items() if k.startswith("#"))
        self.assertEqual((gnd["x"], gnd["y"]), (60.96, 54.61))
        self.assertEqual(s.segments[-1], ((60.96, 40.64), (66.04, 40.64)))

    def test_power_value_can_be_hidden(self):
        s = schgen.Sheet(OLD_SCH)
        s.power("GND", (50.8, 50.8), rot=90, show_value=False)
        self.assertEqual(s.text_boxes(), [])
        node = s._symbol_item(next(iter(s.symbols)))
        value = next(x for x in node if isinstance(x, list) and x[:2] == ["property", "Value"])
        self.assertIn(["hide", "yes"], value)

    def test_dnp_flag(self):
        s = schgen.Sheet(OLD_SCH)
        s.place("C4", 50.8, 50.8, dnp=True)
        s.place("C2", 76.2, 50.8)
        node = {r: s._symbol_item(r) for r in ("C4", "C2")}
        self.assertIn(["dnp", "yes"], node["C4"])
        self.assertIn(["dnp", "no"], node["C2"])

    def test_new_part_has_stable_uuid_and_fields(self):
        s = schgen.Sheet(OLD_SCH)
        s.add_part("J4", "Expansion 2x12", "Radxa expansion header")
        again = schgen.Sheet(OLD_SCH)
        again.add_part("J4", "Expansion 2x12", "Radxa expansion header")
        self.assertEqual(s.old["J4"]["uuid"], again.old["J4"]["uuid"])
        s.place("J4", 101.6, 101.6)
        sch = write_project(s, "t_new")
        new = netlist.load(netlist.export(sch, sch.with_suffix(".net")))
        self.assertEqual(new.comps["J4"]["value"], "Expansion 2x12")
        self.assertEqual(new.comps["J4"]["footprint"], "Connector_PinHeader_2.54mm:PinHeader_2x14_P2.54mm_Vertical")

    def test_rejects_diagonal_wire(self):
        s = schgen.Sheet(OLD_SCH)
        with self.assertRaises(ValueError):
            s.wire((0, 0), (2.54, 2.54))

    def test_embedded_symbol_matches_library(self):
        s = schgen.Sheet(OLD_SCH)
        seen = {}
        for ref, lib_id in sorted(SYMBOL_MAP.items()):
            if lib_id not in seen:
                seen[lib_id] = ref
        for i, ref in enumerate(seen.values()):
            if ref not in s.old:
                s.add_part(ref, ref, "")
            s.place(ref, 50.8 + 30.48 * (i % 10), 50.8 + 60.96 * (i // 10))
        s.power("GND", (25.4, 25.4))
        s.power("PWR_FLAG", (25.4, 25.4))
        sch = write_project(s, "t_lib")
        rep = sch.with_suffix(".erc.json")
        subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", str(rep), str(sch)],
                       check=True, capture_output=True)
        types = {v["type"] for sh in json.loads(rep.read_text())["sheets"] for v in sh["violations"]}
        self.assertFalse(types & {"lib_symbol_mismatch", "lib_symbol_issues"}, types)


if __name__ == "__main__":
    unittest.main()
