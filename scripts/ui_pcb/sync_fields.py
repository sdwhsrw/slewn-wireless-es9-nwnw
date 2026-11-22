"""Copy the order fields (MPN, Manufacturer, LCSC) from the UI schematic's netlist onto the PCB footprints.

Only fields change; placement, pads and tracks stay. New fields are hidden on the Fab layer of the part's side.

Usage: python3 scripts/ui_pcb/sync_fields.py <netlist.net> <in.kicad_pcb> <out.kicad_pcb>
"""
import re
import sys

import pcbnew

FIELDS = ("MPN", "Manufacturer", "LCSC")


def read_fields(path):
    text = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)(.*?)\(tstamps', text, re.S):
        out[m.group(1)] = dict(re.findall(r'\(field\s+\(name "([^"]+)"\)\s+"([^"]*)"\)', m.group(2)))
    return out


def main(net, pcb_in, pcb_out):
    fields = read_fields(net)
    board = pcbnew.LoadBoard(pcb_in)
    for fp in board.Footprints():
        want = fields.get(fp.GetReference(), {})
        for name in FIELDS:
            if name not in want:
                continue
            new = not fp.HasField(name)
            fp.SetField(name, want[name])
            if new:
                field = fp.GetField(name)
                field.SetVisible(False)
                field.SetLayer(pcbnew.B_Fab if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_Fab)
    pcbnew.SaveBoard(pcb_out, board)


if __name__ == "__main__":
    main(*sys.argv[1:4])
