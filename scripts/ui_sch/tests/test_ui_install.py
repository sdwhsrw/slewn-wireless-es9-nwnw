import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "ui_sch"))
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import netlist  # noqa: E402
import ui_layout  # noqa: E402

OUT = ROOT / "out" / "ui_sch"
REPORTS = ROOT / "out" / "reports"


class UiInstallTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = ui_layout.build()
        subprocess.run(["tools/scripts/check.sh", "ui"], cwd=ROOT, capture_output=True)
        cls.drc = json.loads((REPORTS / "Slewn_V20_UI-drc.json").read_text())
        cls.erc = json.loads((REPORTS / "Slewn_V20_UI-erc.json").read_text())

    def test_installed_sheet_is_generated(self):
        # the generator writes fresh UUIDs for wires each run, so compare circuits, not bytes
        installed = ui_layout.PROJECT / f"{ui_layout.NAME}.kicad_sch"
        self.assertNotIn('(lib_id "SlewnV13_UI:', installed.read_text(),
                         "hw/ui still holds the sheet from before the redraw")
        a = netlist.load(netlist.export(installed, OUT / "installed.net"))
        b = netlist.load(netlist.export(self.generated, OUT / "generated.net"))
        self.assertEqual(netlist.diff(a, b, renames={}), [])
        self.assertEqual(netlist.footprint_changes(a, b), {})

    def test_erc_clean(self):
        found = [(v["severity"], v["type"]) for sh in self.erc["sheets"] for v in sh["violations"]]
        self.assertEqual(found, [])

    def test_drc_clean_but_unrouted(self):
        # PCB synced 2026-11-21 (scripts/ui_pcb/sync_from_sch.py): tracks removed, routing is the next step,
        # so the only open items are pad-to-pad airwires
        self.assertEqual(self.drc["violations"], [])
        for v in self.drc["unconnected_items"]:
            self.assertTrue(all(i["description"].startswith(("Pad", "PTH pad")) for i in v["items"]), v)

    def test_pcb_in_sync(self):
        self.assertEqual(self.drc["schematic_parity"], [])

    def test_pcb_mechanics_match_release(self):
        # the human's rule (2026-11-21): J101, J102, ENC101 and the board outline stay as in release 018b1a3
        import pcbnew

        def mech(path):
            board = pcbnew.LoadBoard(str(path))
            fps = {fp.GetReference(): (fp.GetFPIDAsString(), fp.GetPosition().x, fp.GetPosition().y,
                                       fp.GetOrientationDegrees(), fp.GetLayer(),
                                       tuple(sorted((p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
                                                    for p in fp.Pads())))
                   for fp in board.Footprints() if fp.GetReference() in ("J101", "J102", "ENC101")}
            edges = sorted((d.GetShapeStr(), d.GetStart().x, d.GetStart().y, d.GetEnd().x, d.GetEnd().y)
                           for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts)
            return fps, edges

        release = OUT / "release_018b1a3.kicad_pcb"
        release.write_bytes(subprocess.run(["git", "show", "018b1a3:设计/UI/Slewn_V20_UI.kicad_pcb"], cwd=ROOT,
                                           capture_output=True, check=True).stdout)
        self.assertEqual(mech(ui_layout.PROJECT / f"{ui_layout.NAME}.kicad_pcb"), mech(release))

    def test_pcb_j101_pads_mate_main_j2(self):
        # the pads that touch MAIN J2 carry J2's nets, pin for pin
        import pcbnew
        from layout import J2_NETS  # noqa: E402  (MAIN)

        board = pcbnew.LoadBoard(str(ui_layout.PROJECT / f"{ui_layout.NAME}.kicad_pcb"))
        j101 = next(fp for fp in board.Footprints() if fp.GetReference() == "J101")
        got = {p.GetNumber(): p.GetNetname() for p in j101.Pads()}
        self.assertEqual(got, {n: f"/UI_{net}" for n, net in J2_NETS.items()})

if __name__ == "__main__":
    unittest.main()
