"""Swap the UI board's project-local 0805 footprints for KiCad's stock ones (2026-11-22).

Same size, same place: each part keeps its position, rotation, side, nets, fields and reference text; only the
footprint (pads, courtyard, fab, 3D model) comes from the KiCad library. Pad centres move by at most 0.04 mm
(KiCad's resistor pads sit at +-0.9125 instead of +-0.95), so the existing tracks still land on them.

Usage: python3 scripts/ui_pcb/swap_passives.py <in.kicad_pcb> <out.kicad_pcb>
"""
import os
import sys

import pcbnew

KICAD_FP = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
STOCK = {"R": ("Resistor_SMD", "R_0805_2012Metric"), "C": ("Capacitor_SMD", "C_0805_2012Metric")}
REFS = ["R101", "R102", "R103", "R104", "C101", "C102", "C103", "C104"]


def main(pcb_in, pcb_out):
    board = pcbnew.LoadBoard(pcb_in)
    old = {f.GetReference(): f for f in board.Footprints() if f.GetReference() in REFS}
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    new = {}
    for ref in REFS:                  # load everything before any board.Remove()
        lib, name = STOCK[ref[0]]
        fp = io.FootprintLoad(os.path.join(KICAD_FP, lib + ".pretty"), name)
        fp.SetFPIDAsString(f"{lib}:{name}")
        new[ref] = fp
    for ref in REFS:
        o, n = old[ref], new[ref]
        board.Add(n)
        pos = o.GetPosition()
        n.SetPosition(pos)
        if o.GetLayer() == pcbnew.B_Cu:
            n.Flip(pos, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        n.SetOrientation(o.GetOrientation())
        n.SetPath(o.GetPath())
        n.SetSheetname(o.GetSheetname())
        n.SetSheetfile(o.GetSheetfile())
        n.SetDNP(o.IsDNP())
        n.SetExcludedFromBOM(o.IsExcludedFromBOM())
        n.SetExcludedFromPosFiles(o.IsExcludedFromPosFiles())
        n.SetReference(ref)
        n.SetValue(o.GetValue())
        for field in o.GetFields():
            name = field.GetName()
            if name in ("Reference", "Value", "Footprint"):
                continue
            if not n.HasField(name):
                n.SetField(name, field.GetText())
                f = n.GetField(name)
                f.SetVisible(False)
                f.SetLayer(pcbnew.B_Fab if o.GetLayer() == pcbnew.B_Cu else pcbnew.F_Fab)
            else:
                n.SetField(name, field.GetText())
        # reference text exactly where it was
        ro, rn = o.Reference(), n.Reference()
        rn.SetLayer(ro.GetLayer())
        rn.SetVisible(ro.IsVisible())
        rn.SetMirrored(ro.IsMirrored())
        rn.SetTextSize(ro.GetTextSize())
        rn.SetTextThickness(ro.GetTextThickness())
        rn.SetPosition(ro.GetPosition())
        rn.SetTextAngle(ro.GetTextAngle())
        rn.SetHorizJustify(ro.GetHorizJustify())
        rn.SetVertJustify(ro.GetVertJustify())
        opads = {p.GetNumber(): p for p in o.Pads()}
        for p in n.Pads():
            q = opads[p.GetNumber()]
            p.SetNet(q.GetNet())
            d = (p.GetPosition() - q.GetPosition()).EuclideanNorm()
            assert pcbnew.ToMM(d) < 0.05, (ref, p.GetNumber(), pcbnew.ToMM(d))
    # KiCad's courtyards are wider than the old ones: C103 and R103 sat 1.9 mm apart and now overlap.
    # C103 (DNP) moves 0.25 mm away; its tracks still end inside the pads.
    new["C103"].Move(pcbnew.VECTOR2I_MM(0.25, 0))
    new["C103"].Reference().Move(pcbnew.VECTOR2I_MM(-0.25, 0))   # its label stays where it was
    for ref in REFS:                  # last: after board.Remove() the SWIG wrappers stop resolving objects
        board.Remove(old[ref])
    pcbnew.SaveBoard(pcb_out, board)
    print("swapped", " ".join(REFS))


if __name__ == "__main__":
    main(*sys.argv[1:3])
