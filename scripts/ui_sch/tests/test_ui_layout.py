import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "ui_sch"))
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import netlist  # noqa: E402
import ui_layout  # noqa: E402
from layout import J2_NETS  # noqa: E402  (MAIN)

OUT = ROOT / "out" / "ui_sch"


def rename(nl, refs):
    """The same netlist with references renamed old -> new."""
    out = netlist.Netlist(comps={refs.get(r, r): c for r, c in nl.comps.items()})
    out.nets = {n: frozenset((refs.get(r, r), p) for r, p in pins) for n, pins in nl.nets.items()}
    return out


class UiLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = netlist.load(netlist.export(ui_layout.OLD_SCH, OUT / "old.net"))
        sch = ui_layout.build()
        cls.new = netlist.load(netlist.export(sch, sch.with_suffix(".net")))

    def test_reduced_circuit(self):
        # the DIY complexity review: the old circuit minus the removed parts, with the nets they split merged;
        # every other part keeps its fields, footprint and net names
        expected = rename(netlist.reduce(self.old, ui_layout.REMOVED, ui_layout.MERGED), ui_layout.RENAMED)
        self.assertEqual(netlist.diff(expected, self.new, renames={}), [])
        self.assertEqual(netlist.footprint_changes(expected, self.new), {})
        self.assertEqual(len(self.new.comps), 11)

    def test_spares_are_dnp(self):
        # 2026-11-21: C104 (module has its own LDO and caps), R104 (RK3566 pulls LCD_BL down), C103 (software debounce)
        s = ui_layout.make_sheet()
        self.assertEqual({r for r, sym in s.symbols.items() if sym.get("dnp")}, ui_layout.DNP)
        self.assertEqual(ui_layout.DNP, {"C103", "C104", "R104"})

    def test_references_have_no_gaps(self):
        s = ui_layout.make_sheet()
        refs = sorted(r for r in s.symbols if not r.startswith("#"))
        self.assertEqual(refs, ["C101", "C102", "C103", "C104", "ENC101", "J101", "J102",
                                "R101", "R102", "R103", "R104"])
        # the new R104 is the old R105 (backlight pull-down), not the removed 0R link
        self.assertEqual(s.old["R104"]["uuid"], ui_layout.Sheet(ui_layout.OLD_SCH).old["R105"]["uuid"])

    def test_j101_mates_main_j2(self):
        # approved 2026-11-21: J101 pin n carries MAIN J2 pin n's net, with the UI_ prefix
        got = {pin: name for name, pins in self.new.nets.items() for ref, pin in pins if ref == "J101"}
        self.assertEqual(got, {p: f"/UI_{n}" for p, n in J2_NETS.items()})
        self.assertEqual(ui_layout.J101_NETS, J2_NETS)

    def test_display_pins_follow_j101(self):
        # J102 1-8 is the TB147 module's order (GND VDD SCL SDA RES DC CS BL), the same as J101 1-8
        got = {pin: name for name, pins in self.new.nets.items() for ref, pin in pins if ref == "J102"}
        self.assertEqual(got, {p: f"/UI_{J2_NETS[p]}" for p in map(str, range(1, 9))})

    def test_layout_geometry(self):
        s = ui_layout.make_sheet()
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
        s = ui_layout.make_sheet()
        texts = s.text_boxes()
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

    def test_texts_do_not_cross_wires(self):
        s = ui_layout.make_sheet()
        clashes = []
        for owner, (x1, y1, x2, y2) in s.text_boxes():
            for (ax, ay), (bx, by) in s.segments:
                if min(ax, bx) < x2 - 0.05 and x1 + 0.05 < max(ax, bx) and min(ay, by) < y2 - 0.05 \
                        and y1 + 0.05 < max(ay, by):
                    clashes.append((owner, (ax, ay), (bx, by)))
        self.assertEqual(clashes, [])

    def test_blocks_inside_frame(self):
        s = ui_layout.make_sheet()
        self.assertEqual(s.paper, "A4")
        for x1, y1, x2, y2 in s.rects:
            self.assertTrue(15.24 <= x1 and x2 <= 284.48 and 15.24 <= y1 and y2 <= 195, (x1, y1, x2, y2))
            self.assertFalse(x2 > 175 and y2 > 162, "block in the title block area")
        for owner, (x1, y1, x2, y2) in s.text_boxes():
            self.assertTrue(10 <= x1 and x2 <= 287 and y2 <= 200, owner)
            self.assertFalse(x2 > 175 and y2 > 162, f"{owner} in the title block area")

    def test_uuids_kept(self):
        # the PCB links footprints to symbols by UUID path; the redraw must keep every one
        old = ui_layout.Sheet(ui_layout.OLD_SCH).old
        text = ui_layout.build().read_text()
        for ref, o in old.items():
            if ref not in ui_layout.REMOVED:
                self.assertIn(o["uuid"], text, ref)
        self.assertIn(ui_layout.Sheet(ui_layout.OLD_SCH).root_uuid, text)

    def test_erc_clean(self):
        sch = ui_layout.build()
        rep = sch.parent / "erc.json"
        subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", str(rep), str(sch)],
                       check=True, capture_output=True)
        found = [(v["severity"], v["type"], v["description"]) for sh in json.loads(rep.read_text())["sheets"]
                 for v in sh["violations"]]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
