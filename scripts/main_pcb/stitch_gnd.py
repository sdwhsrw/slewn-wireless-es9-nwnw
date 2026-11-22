"""Add GND stitching vias between the F.Cu and B.Cu GND pours, leaving every track and via in place.

A via goes on a grid point only where both refilled GND pours cover a circle of the via radius plus a
margin around it, so it lands in copper on both layers and clears every other net by the pour's own
clearance. Points too close to an existing hole or GND via are skipped.

Usage: python3 scripts/main_pcb/stitch_gnd.py <in.kicad_pcb> <out.kicad_pcb> [pitch_mm]
"""
import math
import sys

import pcbnew

VIA_D, VIA_DRILL = 0.8, 0.4
MARGIN = 0.25          # extra copper around the via ring, both layers
HOLE_GAP = 0.5         # drill edge to any other drill edge
VIA_GAP = 2.0          # centre distance to an existing GND via


def main(pcb_in, pcb_out, pitch=4.0):
    b = pcbnew.LoadBoard(pcb_in)
    mm, nm = pcbnew.ToMM, pcbnew.FromMM
    gnd = b.FindNet("GND")
    pours = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == gnd.GetNetCode()]
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    fills = {layer: [z.GetFilledPolysList(layer) for z in pours if z.IsOnLayer(layer)]
             for layer in (pcbnew.F_Cu, pcbnew.B_Cu)}

    holes = []                                                     # (x, y, drill radius)
    for f in b.Footprints():
        for p in f.Pads():
            if p.GetDrillSize().x:
                holes.append((mm(p.GetPosition().x), mm(p.GetPosition().y), mm(p.GetDrillSize().x) / 2))
    gnd_vias = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            holes.append((mm(t.GetPosition().x), mm(t.GetPosition().y), mm(t.GetDrillValue()) / 2))
            if t.GetNetCode() == gnd.GetNetCode():
                gnd_vias.append((mm(t.GetPosition().x), mm(t.GetPosition().y)))

    def covered(x, y):
        r = VIA_D / 2 + MARGIN
        pts = [(x, y)] + [(x + r * math.cos(a), y + r * math.sin(a)) for a in [k * math.pi / 6 for k in range(12)]]
        for polys in fills.values():
            for px, py in pts:
                if not any(poly.Contains(pcbnew.VECTOR2I(nm(px), nm(py))) for poly in polys):
                    return False
        return True

    bb = b.GetBoardEdgesBoundingBox()
    added = []
    y = mm(bb.GetTop()) + pitch / 2
    while y < mm(bb.GetBottom()):
        x = mm(bb.GetLeft()) + pitch / 2
        while x < mm(bb.GetRight()):
            ok = all(math.hypot(x - hx, y - hy) >= hr + VIA_DRILL / 2 + HOLE_GAP for hx, hy, hr in holes) and \
                all(math.hypot(x - vx, y - vy) >= VIA_GAP for vx, vy in gnd_vias + added) and covered(x, y)
            if ok:
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I_MM(round(x, 3), round(y, 3)))
                v.SetWidth(nm(VIA_D))
                v.SetDrill(nm(VIA_DRILL))
                v.SetNet(gnd)
                b.Add(v)
                added.append((x, y))
                holes.append((x, y, VIA_DRILL / 2))
            x += pitch
        y += pitch
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb_out, b)
    print(f"added {len(added)} GND vias {VIA_D}/{VIA_DRILL} mm")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(float(a) for a in sys.argv[3:4]))
