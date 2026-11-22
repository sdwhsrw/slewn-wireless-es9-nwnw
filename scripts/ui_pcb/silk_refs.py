"""UI PCB silkscreen clean-up (2026-11-22).

The back-side R/C labels were free texts left at the parts' old places after the R/C moved behind the
encoder ("R105" even names a part that is R104 now). They are replaced by the footprints' own reference
fields, which move with the part. Every silkscreen text gets JLCPCB's minimum size: 1.0 mm high,
0.15 mm stroke.

Usage: python3 scripts/ui_pcb/silk_refs.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

HEIGHT, STROKE = 1.0, 0.15

# reference -> (x, y, angle) on B.Silkscreen, chosen clear of pads, other text and the board edge
REF_SPOT = {
    "C101": (133.2, 100.3, 90), "R101": (135.3, 100.3, 90),
    "C102": (137.4, 100.3, 90), "R102": (139.5, 100.3, 90),
    "R103": (131.3, 96.8, 0), "C103": (139.6, 96.8, 0),
    "C104": (111.2, 92.3, 90), "R104": (120.7, 108.1, 90),     # left of R104 sit J102's pads
}
STALE = {"C101", "C102", "C103", "C104", "R101", "R102", "R103", "R104", "R105"}


def size(text):
    text.SetTextSize(pcbnew.VECTOR2I_MM(HEIGHT, HEIGHT))
    text.SetTextThickness(pcbnew.FromMM(STROKE))


def main(pcb_in, pcb_out):
    board = pcbnew.LoadBoard(pcb_in)
    silk = (pcbnew.F_SilkS, pcbnew.B_SilkS)
    texts = [d for d in board.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() in silk]
    for d in texts:
        if d.GetText() not in STALE:
            size(d)
        if d.GetText() == "J101" and d.GetLayer() == pcbnew.B_SilkS:
            # at 1.0 mm the label reaches J101's outline; 0.25 mm lower keeps the 0.15 mm silk clearance
            d.SetPosition(d.GetPosition() + pcbnew.VECTOR2I_MM(0, 0.25))
    for f in board.Footprints():
        spot = REF_SPOT.get(f.GetReference())
        if spot is None:
            continue
        ref = f.Reference()
        ref.SetLayer(pcbnew.B_SilkS)
        ref.SetMirrored(True)
        ref.SetVisible(True)
        size(ref)
        ref.SetPosition(pcbnew.VECTOR2I_MM(spot[0], spot[1]))
        ref.SetTextAngleDegrees(spot[2])
    for d in texts:                  # last: after board.Remove() the SWIG wrappers stop resolving objects
        if d.GetText() in STALE:
            board.Remove(d)
    pcbnew.SaveBoard(pcb_out, board)


if __name__ == "__main__":
    main(*sys.argv[1:3])
