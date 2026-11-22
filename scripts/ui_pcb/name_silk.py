"""Project name on the UI board's back silkscreen (2026-11-22): "SLEWN AIR V20 / UI" replaces the short
"SLEWN V20 UI" label in the same place, 1.0 mm high, 0.15 mm stroke.

Usage: python3 scripts/ui_pcb/name_silk.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

OLD, NEW = "SLEWN V20 UI", "SLEWN AIR V20 / UI"


def main(pcb_in, pcb_out):
    board = pcbnew.LoadBoard(pcb_in)
    hits = [d for d in board.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT)
            and d.GetLayer() == pcbnew.B_SilkS and d.GetText() in (OLD, NEW)]
    if not hits:
        raise SystemExit(f"no '{OLD}' text on B.Silkscreen")
    for d in hits:
        d.SetText(NEW)
        d.SetTextSize(pcbnew.VECTOR2I_MM(1.0, 1.0))
        d.SetTextThickness(pcbnew.FromMM(0.15))
    # the "J101" label grew to 1.0 mm on 2026-11-22 and touched J101's outline (0.11 mm, 0.15 mm needed)
    for d in board.GetDrawings():
        if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() == pcbnew.B_SilkS and d.GetText() == "J101" \
                and abs(pcbnew.ToMM(d.GetPosition().y) - 108.2) < 0.01:
            d.SetPosition(d.GetPosition() + pcbnew.VECTOR2I_MM(0, 0.25))
    pcbnew.SaveBoard(pcb_out, board)


if __name__ == "__main__":
    main(*sys.argv[1:3])
