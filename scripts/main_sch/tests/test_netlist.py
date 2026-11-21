import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import netlist  # noqa: E402
import sexpr  # noqa: E402

OLD_SCH = ROOT / "old" / "main-backup-2026-11-20" / "Slewn_V20_MAIN.kicad_sch"
OUT = ROOT / "out" / "main_sch"


def move_pin(nl, pin, src, dst):
    nl.nets[src] = nl.nets[src] - {pin}
    nl.nets[dst] = nl.nets[dst] | {pin}


def rename_net(nl, old, new):
    nl.nets[new] = nl.nets.pop(old)


class NetlistTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = netlist.load(netlist.export(OLD_SCH, OUT / "old.net"))

    def test_identical_is_empty(self):
        self.assertEqual(netlist.diff(self.old, self.old), [])

    def test_counts(self):
        self.assertEqual(len(self.old.comps), 39)
        self.assertIn(("J3", "3"), self.old.nets["/GND"])
        self.assertIn(("U2", "21"), self.old.nets["/GND"])
        self.assertIn(("J1", "2"), self.old.nets["/5V_SAFE"])

    def test_reduce_drops_parts_and_merges_nets(self):
        r = netlist.reduce(self.old, {"R20"}, {"/BUCK_RAW": "/5V", "/EF_IN5": "/5V"})
        self.assertNotIn("R20", r.comps)
        self.assertIn(("U1", "O4"), r.nets["/5V"])
        self.assertIn(("U3", "9"), r.nets["/5V"])
        self.assertNotIn("/BUCK_RAW", r.nets)
        self.assertFalse(any(p[0] == "R20" for pins in r.nets.values() for p in pins))

    def test_moved_pin_detected(self):
        new = copy.deepcopy(self.old)
        move_pin(new, ("R10", "2"), "/OV2", "/OV3")
        self.assertNotEqual(netlist.diff(self.old, new), [])

    def test_gnd_rename_allowed(self):
        new = copy.deepcopy(self.old)
        rename_net(new, "/GND", "GND")
        self.assertEqual(netlist.diff(self.old, new), [])

    def test_other_rename_detected(self):
        new = copy.deepcopy(self.old)
        rename_net(new, "/OV2", "/OVP2")
        self.assertNotEqual(netlist.diff(self.old, new), [])

    def test_unconnected_rename_allowed(self):
        new = copy.deepcopy(self.old)
        rename_net(new, "unconnected-(J1-NC-Pad3)", "unconnected-(J1-Pin_3-Pad3)")
        self.assertEqual(netlist.diff(self.old, new), [])

    def test_value_change_detected(self):
        new = copy.deepcopy(self.old)
        new.comps["R12"]["value"] = "1k"
        self.assertTrue(any("R12" in d for d in netlist.diff(self.old, new)))

    def test_footprint_change_reported_not_diffed(self):
        new = copy.deepcopy(self.old)
        new.comps["C1"]["footprint"] = "Capacitor_SMD:C_1210_3225Metric"
        new.comps["C1"]["Footprint"] = "Capacitor_SMD:C_1210_3225Metric"
        self.assertEqual(netlist.diff(self.old, new), [])
        self.assertEqual(list(netlist.footprint_changes(self.old, new)), ["C1"])

    def test_pin_net_mismatches(self):
        new = copy.deepcopy(self.old)
        move_pin(new, ("R10", "2"), "/OV2", "/OV3")
        self.assertEqual(netlist.pin_net_mismatches(self.old, new, {"R11"}), [])
        self.assertTrue(netlist.pin_net_mismatches(self.old, new, {"R10"}))

    def test_sexpr_roundtrip(self):
        t = OLD_SCH.read_text()
        self.assertEqual(sexpr.parse(sexpr.dump(sexpr.parse(t))), sexpr.parse(t))


if __name__ == "__main__":
    unittest.main()
