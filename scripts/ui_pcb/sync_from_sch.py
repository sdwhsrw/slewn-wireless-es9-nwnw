"""Bring hw/ui/Slewn_V20_UI.kicad_pcb in line with the UI schematic, before routing.

Rules (2026-11-21, after the MAIN sync):
  1. Board outline, zones and keep-outs stay as they are.
  2. J101, J102 and ENC101 sit where the front panel and MAIN J2 need them: they keep footprint, position,
     rotation, everything; only their pad nets follow the schematic.
  3. Footprints are matched to symbols by UUID path, so a renumbered part keeps its place and takes the new
     reference (R105 -> R104). Footprints without a symbol are removed (the 0R link cut by the review).
  4. All tracks and vias are removed: the new J101 pin order changes almost every connection.
  5. The other parts (R/C on the back) keep their place; value, fields, DNP and pad nets follow the schematic.

Usage: python3 scripts/ui_pcb/sync_from_sch.py <in.kicad_pcb> <netlist.net> <out.kicad_pcb>
The netlist comes from `kicad-cli sch export netlist --format kicadsexpr`.
"""
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main_sch"))
from sexpr import find, find_all, parse  # noqa: E402

FIXED = ("J101", "J102", "ENC101")


def read_netlist(path: Path) -> dict[str, dict]:
    root = parse(Path(path).read_text())
    comps = {}
    for c in find_all(find(root, "components"), "comp"):
        ref = find(c, "ref")[1]
        fields = {find(f, "name")[1]: (f[2] if len(f) > 2 and not isinstance(f[2], list) else "")
                  for f in find_all(find(c, "fields") or [], "field")}
        comps[ref] = {"value": find(c, "value")[1], "fields": fields,
                      "flags": {find(p, "name")[1] for p in find_all(c, "property")},
                      "uuid": find(c, "tstamps")[1], "sheetpath": find(find(c, "sheetpath"), "tstamps")[1],
                      "pins": {}}
    for n in find_all(find(root, "nets"), "net"):
        for node in find_all(n, "node"):
            ref = find(node, "ref")[1]
            if ref in comps:
                comps[ref]["pins"][find(node, "pin")[1]] = find(n, "name")[1]
    return comps


def snapshot(fp):
    """Everything about a fixed footprint except its pad nets."""
    pads = sorted((p.GetNumber(), p.GetPosition().x, p.GetPosition().y, p.GetSize().x, p.GetSize().y,
                   p.GetDrillSize().x, p.GetOrientationDegrees()) for p in fp.Pads())
    fields = sorted((f.GetName(), f.GetText()) for f in fp.GetFields())
    return (fp.GetFPIDAsString(), fp.GetPosition().x, fp.GetPosition().y, fp.GetOrientationDegrees(),
            fp.GetLayer(), tuple(pads), tuple(fields))


def placement(fp):
    return fp.GetFPIDAsString(), fp.GetPosition().x, fp.GetPosition().y, fp.GetOrientationDegrees(), fp.GetLayer()


def outline(board):
    return sorted((d.GetShapeStr(), d.GetStart().x, d.GetStart().y, d.GetEnd().x, d.GetEnd().y)
                  for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts)


def zones(board):
    return sorted((str(z.GetNetname()), z.GetLayerSet().FmtHex(), z.GetNumCorners()) for z in board.Zones())


def net_for(board, name, cache):
    if name not in cache:
        net = board.FindNet(name)
        if net is None:
            net = pcbnew.NETINFO_ITEM(board, name)
            board.Add(net)
        cache[name] = net
    return cache[name]


def path_of(comp):
    return f"{comp['sheetpath'].rstrip('/')}/{comp['uuid']}"


def set_symbol_data(fp, ref, comp):
    fp.SetReference(ref)
    fp.SetValue(comp["value"])
    fp.SetPath(pcbnew.KIID_PATH(path_of(comp)))
    for key, val in comp["fields"].items():
        if key in ("Reference", "Value", "Footprint"):
            continue
        new = not fp.HasField(key)
        fp.SetField(key, val)
        if new:
            field = fp.GetField(key)
            field.SetVisible(False)
            field.SetLayer(pcbnew.B_Fab if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_Fab)


def main(pcb_in, net_in, pcb_out):
    board = pcbnew.LoadBoard(str(pcb_in))
    comps = read_netlist(net_in)
    by_path = {fp.GetPath().AsString(): fp for fp in board.Footprints()}
    missing = sorted(r for r, c in comps.items() if path_of(c) not in by_path)
    if missing:
        raise SystemExit(f"parts missing on the board: {missing}")
    by_ref = {ref: by_path[path_of(c)] for ref, c in comps.items()}
    fixed_before = {r: snapshot(by_ref[r]) for r in FIXED}
    kept_before = {r: placement(by_ref[r]) for r in comps}
    outline_before, zones_before = outline(board), zones(board)

    tracks = list(board.GetTracks())
    linked = {path_of(c) for c in comps.values()}
    doomed = [fp for path, fp in by_path.items() if path not in linked]
    removed = sorted(fp.GetReference() for fp in doomed)
    for item in tracks + doomed:
        board.Remove(item)

    cache = {}
    for ref, comp in sorted(comps.items()):
        fp = by_ref[ref]
        if ref not in FIXED:
            set_symbol_data(fp, ref, comp)
            fp.SetDNP("dnp" in comp["flags"])
            fp.SetExcludedFromBOM("exclude_from_bom" in comp["flags"])
        for pad in fp.Pads():
            name = comp["pins"].get(pad.GetNumber())
            if name is None:
                pad.SetNetCode(0)
            else:
                pad.SetNet(net_for(board, name, cache))

    for z in board.Zones():
        z.UnFill()
    board.BuildConnectivity()

    assert {r: snapshot(by_ref[r]) for r in FIXED} == fixed_before, "J101/J102/ENC101 changed"
    assert {r: placement(by_ref[r]) for r in comps} == kept_before, "a part moved"
    assert outline(board) == outline_before, "board outline changed"
    assert zones(board) == zones_before, "zones changed"
    pcbnew.SaveBoard(str(pcb_out), board)
    print(f"removed footprints: {' '.join(removed)}")
    print(f"removed tracks/vias: {len(tracks)}")
    print(f"footprints now: {' '.join(sorted(by_ref))}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
