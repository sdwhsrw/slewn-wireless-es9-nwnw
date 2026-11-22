"""Bring hw/main/Slewn_V20_MAIN.kicad_pcb in line with the MAIN schematic, before layout.

Rules from the human (2026-11-21):
  1. Board outline and cut-outs stay as they are.
  2. J1, J2, J3 keep footprint, position, rotation, everything; only their pad nets follow the schematic.
  3. Footprints without a symbol are removed (the parts cut from the schematic, fiducials).
  4. All tracks and vias are removed.
  5. Every other part is placed off the board, grouped by function.

Usage: python3 scripts/main_pcb/sync_from_sch.py <in.kicad_pcb> <netlist.net> <out.kicad_pcb> [--keep-placed]
The netlist comes from `kicad-cli sch export netlist --format kicadsexpr`.
--keep-placed: a part whose footprint did not change keeps its place (nets and fields still follow the
schematic); only new or changed footprints are parked. Without it every part except J1-J3 is parked.
"""
import os
import sys

import pcbnew

FIXED = ("J1", "J2", "J3")

# Off-board placement: rows of groups below the board, left to right.
GROUPS = [
    [("Rack power", ["F1", "Q1", "TP7"]), ("5 V buck", ["U1", "C4", "C2", "TP6"]), ("I2C5 pull-ups", ["R2", "R3"])],
    [("Expansion", ["J4", "J5"])],
]
ORIGIN = (43.0, 115.0)   # top left of the parking area, mm (board ends at y 108)
GAP, GROUP_GAP, ROW_GAP = 3.0, 10.0, 8.0


def parse(text):
    """Minimal s-expression parser: lists of str atoms."""
    out, stack, i, n = [], [], 0, len(text)
    cur = out
    while i < n:
        c = text[i]
        if c == "(":
            stack.append(cur); new = []; cur.append(new); cur = new; i += 1
        elif c == ")":
            cur = stack.pop(); i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    j += 1
                buf.append(text[j]); j += 1
            cur.append("".join(buf)); i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            cur.append(text[i:j]); i = j
    return out[0]


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key, default=None):
    hit = find(node, key)
    return hit[0][1] if hit and len(hit[0]) > 1 else default


def read_netlist(path):
    root = parse(open(path, encoding="utf-8").read())
    comps = {}
    for comp in find(find(root, "components")[0], "comp"):
        ref = first(comp, "ref")
        fields = {first(f, "name"): (f[2] if len(f) > 2 else "") for f in find(find(comp, "fields")[0], "field")} \
            if find(comp, "fields") else {}
        sheet = find(comp, "sheetpath")[0]
        flags = {first(prop, "name") for prop in find(comp, "property")}
        comps[ref] = {"value": first(comp, "value"), "footprint": first(comp, "footprint"),
                      "fields": fields, "flags": flags, "uuid": first(comp, "tstamps"),
                      "sheetpath": first(sheet, "tstamps"), "pins": {}}
    for net in find(find(root, "nets")[0], "net"):
        name = first(net, "name")
        for node in find(net, "node"):
            ref = first(node, "ref")
            if ref in comps:
                comps[ref]["pins"][first(node, "pin")] = name
    return comps


def snapshot(fp):
    """Everything about a fixed footprint except its pad nets."""
    pads = sorted((p.GetNumber(), p.GetPosition().x, p.GetPosition().y, p.GetSize().x, p.GetSize().y,
                   p.GetDrillSize().x, p.GetOrientationDegrees()) for p in fp.Pads())
    return (fp.GetFPIDAsString(), fp.GetPosition().x, fp.GetPosition().y, fp.GetOrientationDegrees(),
            fp.GetLayer(), tuple(pads))


def outline(board):
    return sorted((d.GetShapeStr(), d.GetStart().x, d.GetStart().y, d.GetEnd().x, d.GetEnd().y)
                  for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts)


def lib_dirs(project_dir):
    """Library name -> folder, from the project fp-lib-table, then the global one."""
    env = {"KIPRJMOD": project_dir,
           "KICAD10_FOOTPRINT_DIR": os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")}
    dirs = {}
    for table in (os.path.join(project_dir, "fp-lib-table"),
                  os.path.expanduser("~/.config/kicad/10.0/fp-lib-table")):
        if not os.path.exists(table):
            continue
        for lib in find(parse(open(table, encoding="utf-8").read()), "lib"):
            uri = first(lib, "uri")
            for key, val in env.items():
                uri = uri.replace("${%s}" % key, val)
            dirs.setdefault(first(lib, "name"), uri)
    return dirs


def load_footprint(lib_id, dirs):
    lib, name = lib_id.split(":", 1)
    fp = pcbnew.PCB_IO_KICAD_SEXPR().FootprintLoad(dirs[lib], name)
    if fp is None:
        raise SystemExit(f"footprint {lib_id} not found in {dirs[lib]}")
    fp.SetFPIDAsString(lib_id)
    return fp


def net_for(board, name, cache):
    if name not in cache:
        net = board.FindNet(name)
        if net is None:
            net = pcbnew.NETINFO_ITEM(board, name)
            board.Add(net)
        cache[name] = net
    return cache[name]


def apply_netlist(board, fp, comp, cache):
    for pad in fp.Pads():
        name = comp["pins"].get(pad.GetNumber())
        if name is None:
            pad.SetNetCode(0)
        else:
            pad.SetNet(net_for(board, name, cache))


def set_symbol_data(fp, ref, comp):
    fp.SetReference(ref)
    fp.SetValue(comp["value"])
    fp.SetPath(pcbnew.KIID_PATH(f"{comp['sheetpath'].rstrip('/')}/{comp['uuid']}"))
    for key, val in comp["fields"].items():
        if key in ("Reference", "Value", "Footprint"):
            continue
        new = not fp.HasField(key)
        fp.SetField(key, val)
        if new:
            field = fp.GetField(key)
            field.SetVisible(False)
            field.SetLayer(pcbnew.F_Fab)


def park(board, fps):
    y = ORIGIN[1]
    for row in GROUPS:
        x, row_h = ORIGIN[0], 0.0
        for _, refs in row:
            for ref in refs:
                if ref not in fps:
                    continue
                fp = fps[ref]
                fp.SetOrientationDegrees(0)
                fp.SetPosition(pcbnew.VECTOR2I_MM(0, 0))
                bb = fp.GetBoundingBox(False)
                w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
                dx, dy = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
                fp.SetPosition(pcbnew.VECTOR2I_MM(round(x - dx, 2), round(y - dy, 2)))
                x += w + GAP
                row_h = max(row_h, h)
            x += GROUP_GAP - GAP
        y += row_h + ROW_GAP


def main(pcb_in, net_in, pcb_out, keep_placed=False):
    board = pcbnew.LoadBoard(pcb_in)
    comps = read_netlist(net_in)
    by_ref = {fp.GetReference(): fp for fp in board.Footprints()}
    fixed_before = {r: snapshot(by_ref[r]) for r in FIXED}
    outline_before = outline(board)

    # Load every library footprint before removing anything: after board.Remove() the SWIG bindings
    # stop resolving new objects (KiCad 10.0.8).
    dirs = lib_dirs(os.path.dirname(os.path.abspath(pcb_in)))
    kept = {ref for ref, comp in comps.items() if keep_placed and ref not in FIXED and ref in by_ref
            and by_ref[ref].GetFPIDAsString() == comp["footprint"]}
    fresh = {ref: load_footprint(comp["footprint"], dirs) for ref, comp in comps.items()
             if ref not in FIXED and ref not in kept}

    tracks = list(board.GetTracks())
    n_tracks = len(tracks)
    removed = sorted(r for r in by_ref if r not in comps)
    doomed = tracks + [by_ref.pop(r) for r in removed] + [by_ref.pop(r) for r in fresh if r in by_ref]
    for item in doomed:
        board.Remove(item)

    cache, fps = {}, {}
    for ref, comp in sorted(comps.items()):
        fp = by_ref[ref] if ref in FIXED or ref in kept else fresh[ref]
        if ref in fresh:
            board.Add(fp)
        if ref not in FIXED:
            fp.SetDNP("dnp" in comp["flags"])
            fp.SetExcludedFromBOM("exclude_from_bom" in comp["flags"])
        if ref not in FIXED:   # J1-J3: only the pad nets follow the schematic
            set_symbol_data(fp, ref, comp)
        apply_netlist(board, fp, comp, cache)
        fps[ref] = fp
    park(board, {r: f for r, f in fps.items() if r in fresh})

    for zone in board.Zones():
        zone.UnFill()
        if not zone.GetIsRuleArea() and zone.GetNetname() not in ("",) and board.FindNet(zone.GetNetname()) \
                and zone.GetNetname().lstrip("/") in cache and zone.GetNetname() not in cache:
            zone.SetNet(cache[zone.GetNetname().lstrip("/")])   # old /GND pours -> GND
    board.BuildConnectivity()

    assert {r: snapshot(fps[r]) for r in FIXED} == fixed_before, "J1-J3 changed"
    assert outline(board) == outline_before, "board outline changed"
    pcbnew.SaveBoard(pcb_out, board)
    print(f"removed footprints: {' '.join(sorted(removed))}")
    print(f"removed tracks/vias: {n_tracks}")
    print(f"footprints now: {' '.join(sorted(fps))}")


if __name__ == "__main__":
    main(*sys.argv[1:4], keep_placed="--keep-placed" in sys.argv[4:])
