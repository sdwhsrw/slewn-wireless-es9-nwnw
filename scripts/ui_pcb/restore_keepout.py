"""Put the right-hand Keystone 633 bracket keep-out of the UI board back to its outline in 018b1a3 (main).

It marks the mechanical bracket and post; it was moved by accident on 2026-11-22.

Usage: python3 scripts/ui_pcb/restore_keepout.py <original.kicad_pcb> <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

NAME = "Keystone 633 bracket and post clearance"


def outline(zone):
    o = zone.Outline()
    return [o.CVertex(i) for i in range(o.FullPointCount())]


def main(orig, pcb_in, pcb_out):
    ref = [z for z in pcbnew.LoadBoard(orig).Zones() if z.GetIsRuleArea() and z.GetZoneName() == NAME]
    board = pcbnew.LoadBoard(pcb_in)
    cur = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName() == NAME]
    want = {min(p.x for p in outline(z)): outline(z) for z in ref}
    for z in cur:
        x0 = min(p.x for p in outline(z))
        orig_pts = min(want.items(), key=lambda kv: abs(kv[0] - x0))[1]     # the original nearest to this one
        if [(p.x, p.y) for p in outline(z)] == [(p.x, p.y) for p in orig_pts]:
            continue
        o = z.Outline()
        o.RemoveAllContours()
        o.NewOutline()
        for p in orig_pts:
            o.Append(p.x, p.y)
        print("restored", NAME, "at x", pcbnew.ToMM(x0), "->", pcbnew.ToMM(min(p.x for p in orig_pts)))
    pcbnew.SaveBoard(pcb_out, board)


if __name__ == "__main__":
    main(*sys.argv[1:4])
