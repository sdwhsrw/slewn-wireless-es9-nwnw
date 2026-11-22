"""MAIN PCB, first layout pass: place the remaining parts, route J1 <-> J2 and the power paths.

Not routed yet: J1 <-> J4 signals, I2C5 pull-ups R2/R3 (DNP).

Placement (2026-11-22): J4 (2x14 signals) stands at the right board edge, J5 (2x3 power) stands parallel
to it in the rear right corner; the rear strip x 119-130 stays free so the Radxa micro-HDMI stays usable. F1 sits next to J3,
Q1 at the rear left next to U1; both protect wherever they sit in the 12 V path.

Layer plan
  F.Cu  channel between J1 front row and J2: CLK, MOSI, RST, DC, 3V3 (J1.1 -> J2.10)
        12 V: J3 -> F1, Q1 -> U1 inputs, 5 V U1 -> J2.2, 3V3 J1.1 -> J5
  B.Cu  channel: CS, BL and the three encoder drops
        behind J1 (under the Radxa): encoder lanes (nested, so no crossings)
        fused 12 V: F1 -> past the coax cut-out -> lane y 70.6 -> Q1
        5 V: J2.2 -> strip under J2 (y 97.6) -> J1.4/J1.2; U1 -> lane y 60 -> J5.1/J5.2
  The Radxa standoff keep-outs (6.4 mm) close both ends of J1, so the Radxa 5 V comes in from
  below J2 rather than around J1.
  J1 and J2 pin orders force crossings between the LCD and encoder groups; the encoder group
  takes a U-turn behind J1 on B.Cu instead, so no signal between J1 and J2 needs a via.

Usage: python3 scripts/main_pcb/layout_v1.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

SIG, PWR12, PWR5, PWR5_WIDE, PWR33 = 0.2, 0.8, 1.0, 1.5, 0.2
VIA_D, VIA_DRILL = 0.6, 0.3

# Lanes in the 4 mm channel between the J1 front row (y 90.945) and J2 (y 95.07)
L1, L2, L3, L4, L5 = 92.1325, 92.57, 93.0075, 93.445, 93.8825   # equal 0.24 mm gaps pad-lane-...-lane-pad
# Behind J1 rear row (y 88.405), under the Radxa, B.Cu
YA, YB, YSW = 86.6, 85.8, 85.0      # 0.8 mm apart, clear of the J1 rear pads
GAP = 1.27            # half the J1 pitch: centre of the gap between two J1 pads
Y_MID = 89.675        # between the J1 rows

PLACE = {   # ref: (x, y, rotation)
    "J4": (146.27, 56.0, 0),         # pin 1 at the rear; pins 146.27 / 148.81, y 56.0 ... 89.02
    "J5": (139.79, 56.0, 0),         # standing like J4, just left of its first rows; pin 1 at the rear
    "Q1": (84.0, 64.5, 0),
    "F1": (140.5, 91.5, 180),        # pad 1 (rack side) towards J3
    "C4": (73.5, 59.5, 90),
    "C2": (67.0, 95.8, 0),
    "TP6": (72.0, 96.0, 0),
    "TP7": (75.5, 96.5, 0),
    "R2": (84.0, 58.0, 0),
    "R3": (88.0, 58.0, 0),
}


def chamfer(pts, size, keep=()):
    """Cut every right-angle corner to 45 degrees; the cut never takes more than half a leg.
    Corners in `keep` (pad centres, vias, T-joints) stay where they are."""
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        lu, lv = (u[0] ** 2 + u[1] ** 2) ** 0.5, (v[0] ** 2 + v[1] ** 2) ** 0.5
        if lu == 0 or lv == 0 or abs(u[0] * v[0] + u[1] * v[1]) > 1e-6 * lu * lv or \
                any(abs(b[0] - k[0]) < 1e-3 and abs(b[1] - k[1]) < 1e-3 for k in keep):
            out.append(b)
            continue
        d = min(size, lu / 2, lv / 2)
        out += [(round(b[0] - u[0] / lu * d, 4), round(b[1] - u[1] / lu * d, 4)),
                (round(b[0] + v[0] / lv * d, 4), round(b[1] + v[1] / lv * d, 4))]
    out.append(pts[-1])
    return out


class Router:
    def __init__(self, board):
        self.b = board
        self.fp = {f.GetReference(): f for f in board.Footprints()}
        self.anchors = []            # points a route must keep passing through

    def pad(self, ref, num):
        p = [p for p in self.fp[ref].Pads() if p.GetNumber() == str(num)][0]
        x, y = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
        self.anchors.append((x, y))
        return x, y, p.GetNetname()

    def net(self, name):
        return self.b.FindNet(name)

    def path(self, net, layer, width, pts):
        n = self.net(net)
        pts = chamfer([p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]], 2.0 * width + 0.2, self.anchors)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if (x0, y0) == (x1, y1):
                continue
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pcbnew.VECTOR2I_MM(x0, y0))
            t.SetEnd(pcbnew.VECTOR2I_MM(x1, y1))
            t.SetWidth(pcbnew.FromMM(width))
            t.SetLayer(layer)
            t.SetNet(n)
            self.b.Add(t)

    def via(self, net, x, y):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        v.SetWidth(pcbnew.FromMM(VIA_D))
        v.SetDrill(pcbnew.FromMM(VIA_DRILL))
        v.SetNet(self.net(net))
        self.b.Add(v)


def fix_zone_nets(board):
    """The copper pours still carried the old schematic's net name /GND; the schematic now uses GND."""
    gnd = board.FindNet("GND")
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetname() == "/GND":
            z.SetNet(gnd)


def place(r):
    for ref, (x, y, rot) in PLACE.items():
        f = r.fp[ref]
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    # the default spot above pin 1 is past the rear edge
    for ref, x, y in (("J4", 143.9, 72.5), ("J5", 137.4, 58.5)):
        text = r.fp[ref].Reference()
        text.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        text.SetTextAngleDegrees(90)


def route_j1_j2(r):
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    j1 = lambda n: r.pad("J1", n)[:2]
    j2 = lambda n: r.pad("J2", n)[:2]

    def rear_down(n, lane, j2pin, net):           # J1 rear-row pin -> front gap -> lane -> J2
        x, y = j1(n)
        gx = x - GAP
        tx, ty = j2(j2pin)
        r.path(net, F, SIG, [(x, y), (gx, Y_MID), (gx, lane), (tx, lane), (tx, ty)])

    def front_down(n, lane, j2pin, net, layer):   # J1 front-row pin -> lane -> J2
        x, y = j1(n)
        tx, ty = j2(j2pin)
        r.path(net, layer, SIG, [(x, y), (x, lane), (tx, lane), (tx, ty)])

    # F.Cu: LCD pins in J1 order = J2 order, so the lanes never cross
    rear_down(23, L1, 3, "/SPI_CLK")
    rear_down(19, L2, 4, "/SPI_MOSI")
    rear_down(15, L3, 5, "/LCD_RST")
    front_down(16, L4, 6, "/LCD_DC", F)
    x1, y1 = j1(1)                                 # 3V3 from J1.1, right of J1
    tx, ty = j2(10)
    xg = x1 + GAP - 0.08              # centred between J1.2 and the standoff keep-out
    r.path("/3V3", F, PWR33, [(x1, y1), (xg, y1 + (xg - x1)), (xg, L5), (tx, L5), (tx, ty)])

    # B.Cu channel: CS and BL
    front_down(24, L1, 7, "/LCD_CS", B)
    front_down(18, L2, 8, "/LCD_BL", B)

    # B.Cu encoder: up behind J1 (nested lanes), down through J1 gaps, short jog to J2
    def encoder(n, front, up_x, lane, drop_x, chan, j2pin, net):
        x, y = j1(n)
        tx, ty = j2(j2pin)
        start = [(x, y), (up_x, Y_MID)] if front else [(x, y)]
        r.path(net, B, SIG, start + [(up_x, lane), (drop_x, lane), (drop_x, chan), (tx, chan), (tx, ty)])

    # drops in the J1 gaps right of columns 15/16, 13/14, 11/12, i.e. 1.5 pitch right of each J2 pin
    encoder(32, True, j1(32)[0] - GAP, YA, j1(15)[0] - GAP, L3, 11, "/ENC_A")
    encoder(33, False, j1(33)[0], YB, j1(13)[0] - GAP, L4, 12, "/ENC_B")
    encoder(36, True, j1(36)[0] - GAP, YSW, j1(11)[0] - GAP, L5, 13, "/ENC_SW")


def route_power(r):
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    # 12 V: J3.9/10 -> F1 -> via -> B past the coax cut-out -> lane y 70.6 -> Q1 (drain 5-8) -> source 1-3 -> U1
    j3_9, j3_10 = r.pad("J3", 9)[:2], r.pad("J3", 10)[:2]
    f1_1, f1_2 = r.pad("F1", 1)[:2], r.pad("F1", 2)[:2]
    r.path("/RACK_12V", F, PWR12, [j3_9, j3_10, (j3_10[0], 93.2), f1_1])
    vx = f1_2[0] - 1.4
    y12 = 70.6                       # below the standoff keep-outs (bottom edge y 69.8)
    q = {n: r.pad("Q1", n)[:2] for n in range(1, 9)}
    xq = q[5][0] + 2.0
    r.path("/VIN_FUSED", F, PWR12, [f1_2, (vx, f1_2[1])])
    r.via("/VIN_FUSED", vx, f1_2[1])
    r.path("/VIN_FUSED", B, PWR12, [(vx, f1_2[1]), (vx, 85.5), (137.0, 84.8), (137.0, y12), (xq, y12)])
    r.via("/VIN_FUSED", xq, y12)
    r.path("/VIN_FUSED", F, PWR12, [(xq, y12), (xq, q[5][1]), q[5], q[6], q[7], q[8]])
    r.path("/12V_IN", F, PWR12, [q[3], q[2], q[1]])
    c4 = r.pad("C4", 1)[:2]
    i3, i4 = r.pad("U1", "I3")[:2], r.pad("U1", "I4")[:2]
    y_in = c4[1]
    r.path("/12V_IN", F, PWR12, [q[1], (q[1][0] - (q[1][1] - y_in), y_in), c4, (71.0, y_in), (71.0, i4[1]), i4, i3])

    # 5 V: U1 O4-O6 -> J2.2 (F) -> B strip under J2 -> J1.4/J1.2
    o4, o5, o6 = (r.pad("U1", n)[:2] for n in ("O4", "O5", "O6"))
    y5 = 93.4                        # below the standoff keep-out (bottom edge y 92.7)
    j2_2 = r.pad("J2", 2)[:2]
    r.path("/5V", F, PWR5, [o4, o5, o6, (o6[0], y5), (j2_2[0], y5), j2_2])
    c2 = r.pad("C2", 1)[:2]          # left of the trunk: joins it past its chamfered corner
    r.path("/5V", F, PWR5, [c2, (c2[0], y5), (o6[0] + 2.8, y5)])
    tp6 = r.pad("TP6", 1)[:2]        # under the trunk: a stub up to it
    r.path("/5V", F, PWR5, [tp6, (tp6[0], y5)])
    j1_2, j1_4 = r.pad("J1", 2)[:2], r.pad("J1", 4)[:2]
    ys = 97.6                        # strip between J2 pads and the board edge
    r.path("/5V", B, PWR5_WIDE, [j2_2, (j2_2[0], ys), (j1_4[0], ys)])
    r.path("/5V", B, PWR5, [(j1_4[0], ys), j1_4, j1_2])
    # U1 -> J5.1/J5.2: B under U1 (the module sits on F), lane y 60
    xv = 71.0                        # on the straight part of the trunk
    r.via("/5V", xv, y5)
    j5 = {n: r.pad("J5", n)[:2] for n in range(1, 5)}
    x5 = j5[1][0] - 1.6              # left of the J5 pin column
    r.path("/5V", B, PWR5, [(xv, y5), (xv, 60.0), (x5, 60.0), (x5, j5[1][1]), j5[1], j5[2]])

    # 3V3 for J5 from J1.1 (rear row), up on F past the right end of J1; J1.1 also feeds J2.10
    j1_1 = r.pad("J1", 1)[:2]
    x3 = j5[3][0] - 1.9
    r.path("/3V3", F, 0.3, [j1_1, (j1_1[0], 63.0), (x3, 63.0), (x3, j5[3][1]), j5[3], j5[4]])


def _seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
    return ((px - x0 - t * dx) ** 2 + (py - y0 - t * dy) ** 2) ** 0.5


def _box(item, grow=0.0):
    bb = item.GetBoundingBox()
    return (pcbnew.ToMM(bb.GetLeft()) - grow, pcbnew.ToMM(bb.GetTop()) - grow,
            pcbnew.ToMM(bb.GetRight()) + grow, pcbnew.ToMM(bb.GetBottom()) + grow)


def _inside(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def stitch_gnd(r, pitch=5.0):
    """GND vias on a grid wherever they clear other nets, keep-outs, courtyards and the edge.

    Boxes are used for pads, keep-outs and courtyards, so the test errs on the safe side."""
    b = r.b
    mm = pcbnew.ToMM
    gnd = b.FindNet("GND").GetNetCode()
    clear = VIA_D / 2 + 0.2 + 0.05
    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, True)
    edges = [(mm(d.GetStart().x), mm(d.GetStart().y), mm(d.GetEnd().x), mm(d.GetEnd().y), d.GetShapeStr(),
              mm(d.GetCenter().x), mm(d.GetCenter().y), mm(d.GetRadius()) if d.GetShapeStr() == "Circle" else 0)
             for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    keep = [_box(z, clear) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    yards = [_box(f, 0.3) for f in b.Footprints()]
    tracks = [(mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y), mm(t.GetWidth()) / 2)
              for t in b.GetTracks() if t.GetNetCode() != gnd]
    bb = b.GetBoardEdgesBoundingBox()
    placed = 0
    x = mm(bb.GetLeft()) + pitch / 2
    while x < mm(bb.GetRight()):
        y = mm(bb.GetTop()) + pitch / 2
        while y < mm(bb.GetBottom()):
            ok = outline.Contains(pcbnew.VECTOR2I_MM(x, y))
            for e in edges if ok else []:
                if e[4] == "Circle":
                    d = abs(((x - e[5]) ** 2 + (y - e[6]) ** 2) ** 0.5 - e[7])
                else:
                    d = _seg_dist(x, y, *e[:4])
                if d < 0.5 + VIA_D / 2 + 0.05:
                    ok = False
                    break
            ok = ok and not any(_inside(k, x, y) for k in keep) and not any(_inside(c, x, y) for c in yards)
            ok = ok and all(_seg_dist(x, y, *t[:4]) >= t[4] + clear for t in tracks)
            if ok:
                r.via("GND", x, y)
                placed += 1
            y += pitch
        x += pitch
    return placed


def fix_keepouts(board):
    """L1 is gone; the U1 keep-out follows U1 (+9 mm in x, symmetric, so the turn does not matter)."""
    rules = [z for z in board.Zones() if z.GetIsRuleArea()]
    for z in rules:
        if z.GetZoneName().startswith("U1 underside") and pcbnew.ToMM(z.GetBoundingBox().GetLeft()) < 50:
            z.Move(pcbnew.VECTOR2I_MM(9.0, 0))
    for z in rules:
        if z.GetZoneName() == "L1 winding clearance":
            board.Remove(z)


def main(pcb_in, pcb_out):
    board = pcbnew.LoadBoard(pcb_in)
    r = Router(board)
    fix_zone_nets(board)
    place(r)
    route_j1_j2(r)
    route_power(r)
    print("GND stitching vias:", stitch_gnd(r))
    fix_keepouts(board)      # last: after board.Remove() the SWIG wrappers stop resolving objects
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(pcb_out, board)


if __name__ == "__main__":
    main(*sys.argv[1:3])
