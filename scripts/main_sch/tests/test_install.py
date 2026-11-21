import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "main_sch"))

import layout  # noqa: E402
from parts import NEW_PARTS  # noqa: E402
import netlist  # noqa: E402

OLD = ROOT / "old" / "main-backup-2026-11-20"
PROJECT = ROOT / "hw" / "main"
OUT = ROOT / "out" / "main_sch"
REPORTS = ROOT / "out" / "reports"


class InstallTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = layout.build(OUT / "full" / "Slewn_V20_MAIN.kicad_sch")
        subprocess.run(["tools/scripts/check.sh", "main"], cwd=ROOT, capture_output=True)
        cls.drc = json.loads((REPORTS / "Slewn_V20_MAIN-drc.json").read_text())
        cls.erc = json.loads((REPORTS / "Slewn_V20_MAIN-erc.json").read_text())

    def test_installed_sheet_is_generated(self):
        # the generator writes fresh UUIDs for wires each run, so compare circuits, not bytes
        installed = PROJECT / "Slewn_V20_MAIN.kicad_sch"
        self.assertNotIn('(lib_id "Slewn_MAIN:TPS25940LRVCR")', installed.read_text(),
                         "hw/main still holds the sheet from before the complexity review")
        a = netlist.load(netlist.export(installed, OUT / "installed.net"))
        b = netlist.load(netlist.export(self.generated, OUT / "generated.net"))
        self.assertEqual(netlist.diff(a, b, renames={}), [])
        self.assertEqual(netlist.footprint_changes(a, b), {})

    def test_erc_clean(self):
        found = [(v["severity"], v["type"]) for sh in self.erc["sheets"] for v in sh["violations"]]
        self.assertEqual(found, [])

    # nets still unrouted after scripts/main_pcb/layout_v1.py; shrink this as J4 gets routed
    UNROUTED = {"/3V3", "/I2C5_SCL", "/I2C5_SDA", "/I2C4_SCL", "/I2C4_SDA", "/I2S_MCLK", "/I2S_BCLK",
                "/I2S_LRCK", "/I2S_DIN", "/I2S_DOUT", "/SPI_CLK", "/SPI_MOSI", "/SPI_MISO", "/SPI_CS1",
                "/UART2_TX", "/UART2_RX", "/UART3_TX", "/UART3_RX", "/GPIO3_C4", "/GPIO3_A1", "/GPIO1_A4"}

    def test_drc_unchanged(self):
        self.assertEqual(self.drc["violations"], [])
        open_nets = {m for u in self.drc["unconnected_items"] for i in u["items"]
                     for m in re.findall(r"\[([^\]]+)\]", i["description"])}
        self.assertEqual(open_nets - self.UNROUTED, set())

    def test_parity_only_expected(self):
        old = netlist.load(netlist.export(OLD / "Slewn_V20_MAIN.kicad_sch", OUT / "old.net"))
        new = netlist.load(netlist.export(PROJECT / "Slewn_V20_MAIN.kicad_sch", OUT / "installed.net"))
        changed = set(netlist.footprint_changes(old, new))
        # the PCB is not synced yet: removed parts still sit on it, and their old nets still name pads
        renamed = {(a, netlist.DEFAULT_RENAMES.get(b, b)) for a, b in layout.MERGED.items()} | {("/GND", "GND")}
        unexpected = []
        for v in self.drc["schematic_parity"]:
            text = v["description"] + " " + " ".join(i["description"] for i in v["items"])
            if v["type"] == "extra_footprint" and any(f"Footprint {r} " in text + " " for r in layout.REMOVED):
                continue
            if v["type"] == "footprint_symbol_mismatch" and any(f"Value ({r}) " in text for r, f in layout.FIELDS.items() if "Value" in f):
                continue
            # pinout of J1/J2 changed on purpose (2026-11-21); J4 is new and not on the PCB yet
            if v["type"] == "net_conflict" and re.search(r" of J[12]( |$)", text):
                continue
            if v["type"] == "missing_footprint" and any(f"Missing footprint {r} " in text for r in NEW_PARTS):
                continue
            if "'Do not populate' settings differ" in text and any(text.endswith(f"Footprint {r}") for r in layout.DNP):
                continue
            if v["type"] == "footprint_symbol_mismatch" or "footprint" in v["type"]:
                if any(f" {r} " in f" {text} " or f"{r}:" in text or f"({r})" in text for r in changed):
                    continue
            m = re.match(r"Pad net \((.*)\) doesn.t match net given by schematic \((.*)\)", v["description"])
            if v["type"] == "net_conflict" and m and (
                    m.groups() in renamed
                    or all(n.startswith("unconnected-") for n in m.groups())):
                continue
            unexpected.append((v["type"], text))
        self.assertEqual(unexpected, [])


if __name__ == "__main__":
    unittest.main()
