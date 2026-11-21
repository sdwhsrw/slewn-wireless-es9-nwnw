import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import fpcheck  # noqa: E402
import netlist  # noqa: E402
from parts import FOOTPRINT_MAP, NEW_PARTS, footprint_file  # noqa: E402

KICAD_FP = Path("/usr/share/kicad/footprints")
OLD = ROOT / "old" / "main-backup-2026-11-20"
LIB = ROOT / "hw" / "main" / "library"
OUT = ROOT / "out" / "main_sch"


def old_fp_file(lib_id):
    return footprint_file(lib_id, project=OLD, legacy=True)


class FpCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = netlist.load(netlist.export(OLD / "Slewn_V20_MAIN.kicad_sch", OUT / "old.net"))

    def test_identical(self):
        self.assertTrue(fpcheck.same_pads(OLD / "Libs/SlewnV13.pretty/C1_C1210.kicad_mod",
                                          KICAD_FP / "Capacitor_SMD.pretty/C_1210_3225Metric.kicad_mod"))

    def test_rotated_differs(self):
        self.assertFalse(fpcheck.same_pads(OLD / "Libs/SlewnV13.pretty/J1_GPIO40.kicad_mod",
                                           KICAD_FP / "Connector_PinHeader_2.54mm.pretty/PinHeader_2x20_P2.54mm_Vertical.kicad_mod"))

    def test_drill_differs(self):
        self.assertFalse(fpcheck.same_pads(OLD / "Libs/SlewnV13.pretty/J3_IDC10.kicad_mod",
                                           KICAD_FP / "Connector_IDC.pretty/IDC-Header_2x05_P2.54mm_Vertical.kicad_mod"))

    def test_map_swaps_are_identical(self):
        for ref, target in FOOTPRINT_MAP.items():
            if ref in NEW_PARTS:
                continue
            with self.subTest(ref=ref, target=target):
                current = self.old.comps[ref]["footprint"]
                self.assertTrue(fpcheck.same_pads(old_fp_file(current), footprint_file(target)))

    def test_every_ref_has_a_target(self):
        self.assertEqual(set(FOOTPRINT_MAP), set(self.old.comps) | NEW_PARTS)

    def test_nothing_points_at_legacy_libs(self):
        for ref, target in FOOTPRINT_MAP.items():
            self.assertNotRegex(target, r"^(SlewnV13|V16|Kinghelm):", ref)

    def test_connectors_match_base_commit(self):
        # J1-J3 must keep the footprints they had when the clean-up branch was created (018b1a3);
        # only the 3D model path may differ, because the models moved to library/3dmodels
        base = {"J1_GPIO40": "SlewnV13", "J3_IDC10": "SlewnV13", "KH-2.54PH90-1X14P-L13.8": "Kinghelm"}
        for name, lib in base.items():
            with self.subTest(fp=name):
                old = subprocess.run(["git", "show", f"018b1a3:设计/MAIN/Libs/{lib}.pretty/{name}.kicad_mod"],
                                     cwd=ROOT, capture_output=True, text=True, check=True).stdout
                new = (LIB / "Slewn_MAIN.pretty" / f"{name}.kicad_mod").read_text()
                strip = lambda s: re.sub(r"\s+", " ", re.sub(r'\(model\s+"[^"]*"', "(model", s)).strip()  # noqa: E731
                self.assertEqual(strip(old), strip(new))
        self.assertEqual({r: FOOTPRINT_MAP[r] for r in ("J1", "J2", "J3")},
                         {"J1": "Slewn_MAIN:J1_GPIO40", "J2": "Slewn_MAIN:KH-2.54PH90-1X14P-L13.8",
                          "J3": "Slewn_MAIN:J3_IDC10"})

    def test_models_resolve(self):
        files = list((LIB / "Slewn_MAIN.pretty").glob("*.kicad_mod"))
        self.assertTrue(files)
        for f in files:
            for m in re.findall(r'\(model\s+"([^"]+)"', f.read_text()):
                with self.subTest(fp=f.name, model=m):
                    self.assertTrue(m.startswith("${KIPRJMOD}/library/3dmodels/"))
                    self.assertTrue((LIB.parent / m.replace("${KIPRJMOD}/", "")).exists())


if __name__ == "__main__":
    unittest.main()
