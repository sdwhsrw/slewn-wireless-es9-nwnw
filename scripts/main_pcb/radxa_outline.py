"""Draw the Radxa ZERO 3W position on User.Drawings of the MAIN PCB.

Source: the V20 assembly model in commit 018b1a3 ("打开 V20 整机.html", embedded glTF, same scene as
"设计/V20-直角总装.blend"). Model to PCB: x_pcb = x + 40, y_pcb = z + 120 (mm). Checked on the J1 pads
(1, 2, 39, 40) and on the four M2.5 screws, which land on the Edge.Cuts holes.

Model facts used here (heights above the MAIN top copper):
  Radxa PCB 65.0 x 30.0, bottom 6.0, top 7.6; its underside parts reach down to 3.1.
  2x USB-C and micro-HDMI overhang the far edge by 1.5.
  USB-C plug envelope (right-angle plug in the model) 89.5-101.5 x 51.5-61.5, lowest point 3.95.

Usage: python3 scripts/main_pcb/radxa_outline.py <in.kicad_pcb> <out.kicad_pcb>
Re-running replaces the previous drawing (group "Radxa ZERO 3W").
"""
import sys

import pcbnew

GROUP = "Radxa ZERO 3W"
BOARD = (72.00, 63.00, 137.01, 93.01)                 # Radxa PCB outline
OVERHANG = [(78.50, 61.50, 87.44, 63.00),            # connectors past the far edge
            (90.96, 61.50, 99.90, 63.00),
            (121.32, 61.75, 127.82, 63.00)]
USB_PLUG = (89.50, 53.50, 101.50, 61.50)             # plug envelope, clipped at the board edge
WIDTH = 0.15
TEXT = 1.0


def rect(board, group, x0, y0, x1, y1):
    shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECTANGLE)
    shape.SetLayer(pcbnew.Dwgs_User)
    shape.SetStart(pcbnew.VECTOR2I_MM(x0, y0))
    shape.SetEnd(pcbnew.VECTOR2I_MM(x1, y1))
    shape.SetWidth(pcbnew.FromMM(WIDTH))
    board.Add(shape)
    group.AddItem(shape)


def text(board, group, x, y, s):
    t = pcbnew.PCB_TEXT(board)
    t.SetLayer(pcbnew.Dwgs_User)
    t.SetText(s)
    t.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    t.SetTextSize(pcbnew.VECTOR2I_MM(TEXT, TEXT))
    t.SetTextThickness(pcbnew.FromMM(0.15))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)
    group.AddItem(t)


def main(pcb_in, pcb_out):
    board = pcbnew.LoadBoard(pcb_in)
    for old in [g for g in board.Groups() if g.GetName() == GROUP]:
        for item in list(old.GetItems()):
            board.Remove(item)
        board.Remove(old)
    group = pcbnew.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)

    rect(board, group, *BOARD)
    for box in OVERHANG:
        rect(board, group, *box)
    rect(board, group, *USB_PLUG)
    x0, y0, _, y1 = BOARD
    text(board, group, x0 + 6.0, y0 + 2.5, "RADXA ZERO 3W 65x30 (V20 3D model)")
    text(board, group, x0 + 6.0, y0 + 4.1, "Radxa bottom 6.0 above MAIN, its parts to 3.1: parts here max 3 mm")
    text(board, group, USB_PLUG[2] + 1.0, USB_PLUG[1] + 2.0, "USB-C plug, lowest 3.95 above MAIN")
    pcbnew.SaveBoard(pcb_out, board)


if __name__ == "__main__":
    main(*sys.argv[1:3])
