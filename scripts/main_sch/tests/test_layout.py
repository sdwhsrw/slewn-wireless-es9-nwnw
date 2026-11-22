import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import layout  # noqa: E402
import netlist  # noqa: E402
from parts import FOOTPRINT_MAP, NEW_PARTS  # noqa: E402

OLD_SCH = ROOT / "old" / "main-backup-2026-11-20" / "Slewn_V20_MAIN.kicad_sch"
OUT = ROOT / "out" / "main_sch"

HEADERS = {"J1", "J2", "J4", "J5"}
HEADER_SPEC = {
    "5V": {("J1", "2"), ("J1", "4"), ("J2", "2"), ("J5", "1"), ("J5", "2")},
    "3V3": {("J1", "1"), ("J1", "17"), ("J2", "10"), ("J5", "3"), ("J5", "4")},
    "SPI_CLK": {("J1", "23"), ("J2", "3"), ("J4", "13")},
    "SPI_MOSI": {("J1", "19"), ("J2", "4"), ("J4", "16")},
    "SPI_MISO": {("J1", "21"), ("J4", "14")},
    "SPI_CS1": {("J1", "22"), ("J4", "15")},
    "LCD_RST": {("J1", "15"), ("J2", "5")},
    "LCD_DC": {("J1", "16"), ("J2", "6")},
    "LCD_CS": {("J1", "24"), ("J2", "7")},
    "LCD_BL": {("J1", "18"), ("J2", "8")},
    "ENC_A": {("J1", "32"), ("J2", "11")},
    "ENC_B": {("J1", "33"), ("J2", "12")},
    "ENC_SW": {("J1", "36"), ("J2", "13")},
    "I2S_MCLK": {("J1", "13"), ("J4", "4")},
    "I2S_BCLK": {("J1", "12"), ("J4", "5")},
    "I2S_LRCK": {("J1", "35"), ("J4", "3")},
    "I2S_DOUT": {("J1", "40"), ("J4", "1")},
    "I2S_DIN": {("J1", "38"), ("J4", "2")},
    "I2C5_SCL": {("J1", "29"), ("J4", "8")},
    "I2C5_SDA": {("J1", "31"), ("J4", "7")},
    "GPIO3_C4": {("J1", "7"), ("J4", "27")},
    "GPIO3_A1": {("J1", "11"), ("J4", "26")},
    "GPIO1_A4": {("J1", "37"), ("J4", "25")},
    "I2C4_SCL": {("J1", "28"), ("J4", "9")},
    "I2C4_SDA": {("J1", "27"), ("J4", "10")},
    "UART2_TX": {("J1", "8"), ("J4", "20")},
    "UART2_RX": {("J1", "10"), ("J4", "19")},
    "UART3_TX": {("J1", "5"), ("J4", "21")},
    "UART3_RX": {("J1", "3"), ("J4", "22")},
}


def without_pins(nl, refs):
    """Drop the pins (and parts) of `refs`; nets left empty disappear."""
    out = netlist.Netlist(comps={r: c for r, c in nl.comps.items() if r not in refs})
    for name, pins in nl.nets.items():
        kept = frozenset(p for p in pins if p[0] not in refs)
        if kept:
            out.nets[name] = kept
    return out


class LayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = netlist.load(netlist.export(OLD_SCH, OUT / "old.net"))

    def test_reduced_circuit(self):
        # the DIY complexity review: the old circuit minus the removed parts, with the nets they split merged;
        # headers are checked on their own below, because their pinout was changed on purpose
        sch = layout.build(OUT / "full" / "Slewn_V20_MAIN.kicad_sch")
        new = netlist.load(netlist.export(sch, sch.with_suffix(".net")))
        expected = netlist.reduce(self.old, layout.REMOVED, layout.MERGED)
        for ref, fields in layout.FIELDS.items():
            for name, value in fields.items():
                expected.comps[ref]["value" if name == "Value" else name] = value
        a, b = without_pins(expected, HEADERS | NEW_PARTS), without_pins(new, HEADERS | NEW_PARTS)
        self.assertEqual(netlist.diff(a, b), [])
        self.assertEqual(len(new.comps), 14)   # 13 + J5 (J4 split, 2026-11-22)
        changed = {r for r, fp in FOOTPRINT_MAP.items() if r in self.old.comps and r in new.comps
                   and fp != self.old.comps[r]["footprint"]}
        self.assertEqual(set(netlist.footprint_changes(self.old, new)), changed)

    def test_header_pinout(self):
        # approved 2026-11-21: J2 1-8 in display order, 9-14 encoder; J4 brings out complete I2S3_M0, the shared SPI
        # bus, I2C5, I2C4, UART2 (debug console), UART3 and spare GPIO; only J1 26 (NC) stays unconnected.
        # 2026-11-22: J4 split into J4 (2x14 signals) and J5 (2x3 power); J4 reordered to follow J1
        sch = layout.build(OUT / "full" / "Slewn_V20_MAIN.kicad_sch")
        new = netlist.load(netlist.export(sch, sch.with_suffix(".net")))
        got = {}
        for name, pins in new.nets.items():
            for ref, pin in pins:
                if ref in HEADERS:
                    got[(ref, pin)] = netlist.DEFAULT_RENAMES.get(name, name).lstrip("/")
        want = {}
        for net, pins in HEADER_SPEC.items():
            for p in pins:
                want[p] = net
        for p in [("J1", str(n)) for n in (6, 9, 14, 20, 25, 30, 34, 39)] + [("J4", str(n)) for n in (6, 11, 12, 17, 18, 23, 24, 28)] \
                + [("J2", str(n)) for n in (1, 9, 14)] + [("J5", "5"), ("J5", "6")]:
            want[p] = "GND"
        self.assertEqual({p: n for p, n in got.items() if not n.startswith("unconnected-")}, want)
        free = {p for p, n in got.items() if n.startswith("unconnected-")}
        self.assertEqual(free, {("J1", "26")})

    def test_part_choices(self):
        # parts review 2026-11-21: AO4407A is NRND, AO4407C is AOS's active part with the same SOIC-8 pinout
        sch = layout.build(OUT / "full" / "Slewn_V20_MAIN.kicad_sch")
        comps = netlist.load(netlist.export(sch, sch.with_suffix(".net"))).comps
        self.assertEqual((comps["Q1"]["MPN"], comps["Q1"]["LCSC"]), ("AO4407C", "C469397"))
        self.assertTrue(comps["Q1"]["value"].startswith("AO4407C"))
        self.assertEqual((comps["F1"]["MPN"], comps["F1"]["LCSC"]), ("0466002.NRHF", "C3105"))
        self.assertEqual((comps["J4"]["MPN"], comps["J4"]["LCSC"]), ("PZ254-2-14-Z-8.5", "C2894975"))
        self.assertEqual(comps["J4"]["footprint"], "Connector_PinHeader_2.54mm:PinHeader_2x14_P2.54mm_Vertical")
        self.assertEqual((comps["J5"]["MPN"], comps["J5"]["LCSC"]), ("PZ254-2-03-Z-8.5", "C2894964"))
        self.assertEqual(comps["J5"]["footprint"], "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical")

    def test_i2c5_pullups(self):
        # 2026-11-21: optional 4.7k pull-ups for I2C5 (no pull-ups on the Radxa there), not fitted by default
        sch = layout.build(OUT / "full" / "Slewn_V20_MAIN.kicad_sch")
        new = netlist.load(netlist.export(sch, sch.with_suffix(".net")))
        net = {p: netlist.DEFAULT_RENAMES.get(n, n).lstrip("/") for n, ps in new.nets.items() for p in ps}
        self.assertEqual({net[("R2", "1")], net[("R2", "2")]}, {"3V3", "I2C5_SCL"})
        self.assertEqual({net[("R3", "1")], net[("R3", "2")]}, {"3V3", "I2C5_SDA"})
        for r in ("R2", "R3"):
            self.assertEqual(new.comps[r]["footprint"], "Resistor_SMD:R_0805_2012Metric")
            self.assertEqual((new.comps[r]["MPN"], new.comps[r]["LCSC"]), ("0805W8F4701T5E", "C17673"))
        self.assertLessEqual({"R2", "R3"}, layout.DNP)

    def test_kept_spares_are_dnp(self):
        s = layout.make_sheet()
        self.assertEqual({r for r, sym in s.symbols.items() if sym.get("dnp")}, layout.DNP)

    def test_layout_geometry(self):
        s = layout.make_sheet()
        boxes = {r: s.bbox(r) for r in s.symbols if not r.startswith("#")}
        refs = sorted(boxes)
        for i, a in enumerate(refs):
            ax1, ay1, ax2, ay2 = boxes[a]
            with self.subTest(ref=a):
                self.assertTrue(10 <= ax1 and ax2 <= 287 and 10 <= ay1 and ay2 <= 200, boxes[a])
                self.assertFalse(ax2 > 175 and ay2 > 162, f"{a} in the title block area")
            for b in refs[i + 1:]:
                bx1, by1, bx2, by2 = boxes[b]
                overlap = ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2
                self.assertFalse(overlap, f"{a} {boxes[a]} overlaps {b} {boxes[b]}")

        def on_grid(v):
            return abs(v / 1.27 - round(v / 1.27)) < 0.005

        for ref, sym in s.symbols.items():
            self.assertTrue(on_grid(sym["x"]) and on_grid(sym["y"]), ref)
            for num, (x, y) in s.pins(ref).items():
                self.assertTrue(on_grid(x) and on_grid(y), f"{ref}.{num}")
        for a, b in s.segments:
            self.assertTrue(all(on_grid(v) for v in (*a, *b)), (a, b))

    def test_text_does_not_overlap(self):
        s = layout.make_sheet()
        texts = s.text_boxes()                          # [(owner, (x1, y1, x2, y2))]
        bodies = {r: s.bbox(r) for r in s.symbols if not r.startswith("#")}

        def hit(a, b, m=0.05):
            return a[0] + m < b[2] and b[0] + m < a[2] and a[1] + m < b[3] and b[1] + m < a[3]

        clashes = []
        for i, (oa, a) in enumerate(texts):
            clashes += [(oa, ob) for ob, b in texts[i + 1:] if hit(a, b)]
            clashes += [(oa, r) for r, b in bodies.items() if hit(a, b)]
            for x1, y1, x2, y2 in s.rects:
                edges = [(x1, y1, x2, y1), (x1, y2, x2, y2), (x1, y1, x1, y2), (x2, y1, x2, y2)]
                clashes += [(oa, "block border")] if any(hit(a, e, 0) for e in edges) else []
        self.assertEqual(clashes, [])

    def test_blocks_inside_frame(self):
        for x1, y1, x2, y2 in layout.make_sheet().rects:
            self.assertTrue(15.24 <= x1 and x2 <= 284.48 and 15.24 <= y1 and y2 <= 195, (x1, y1, x2, y2))
            self.assertFalse(x2 > 175 and y2 > 162, "block in the title block area")

    def test_erc_clean(self):
        sch = layout.build(OUT / "full" / "Slewn_V20_MAIN.kicad_sch")
        rep = OUT / "full" / "erc.json"
        subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", str(rep), str(sch)],
                       check=True, capture_output=True)
        found = [(v["severity"], v["type"], v["description"]) for sh in json.loads(rep.read_text())["sheets"]
                 for v in sh["violations"]]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
