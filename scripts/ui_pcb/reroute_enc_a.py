"""Move the UI board's ENC_A track (B.Cu) out of the restored Keystone bracket keep-out (2026-11-22).

The old run lay on y 107.6, the keep-out's lower edge. The new run takes the same shape 0.35 mm lower,
on y 107.95, then up past the keep-out's left edge (x 120.33), clear of R104 and J102.

Usage: python3 scripts/ui_pcb/reroute_enc_a.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

OLD = [((133.20, 104.75), (130.35, 107.60)), ((130.35, 107.60), (121.70, 107.60)), ((121.70, 107.60), (116.80, 102.70))]
NEW = [(133.20, 104.75), (130.00, 107.95), (120.00, 107.95), (120.00, 105.90), (116.80, 102.70)]


def key(p):
    return round(pcbnew.ToMM(p.x), 2), round(pcbnew.ToMM(p.y), 2)


def main(pcb_in, pcb_out):
    board = pcbnew.LoadBoard(pcb_in)
    net = board.FindNet("/UI_ENC_A")
    old = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "/UI_ENC_A"
           and t.GetLayer() == pcbnew.B_Cu and {key(t.GetStart()), key(t.GetEnd())} in [set(s) for s in OLD]]
    if len(old) != len(OLD):
        raise SystemExit(f"expected {len(OLD)} old ENC_A segments, found {len(old)}")
    width = old[0].GetWidth()
    for a, b in zip(NEW, NEW[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I_MM(*a))
        t.SetEnd(pcbnew.VECTOR2I_MM(*b))
        t.SetWidth(width)
        t.SetLayer(pcbnew.B_Cu)
        t.SetNet(net)
        board.Add(t)
    for t in old:                    # last: after board.Remove() the SWIG wrappers stop resolving objects
        board.Remove(t)
    pcbnew.SaveBoard(pcb_out, board)


if __name__ == "__main__":
    main(*sys.argv[1:3])
