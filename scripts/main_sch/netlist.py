"""Export, load and compare KiCad netlists to prove a redraw kept the circuit."""
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

FOOTPRINT_KEYS = {"footprint", "Footprint"}
DEFAULT_RENAMES = {"/GND": "GND"}


@dataclass
class Netlist:
    comps: dict[str, dict[str, str]] = field(default_factory=dict)
    nets: dict[str, frozenset[tuple[str, str]]] = field(default_factory=dict)


def export(sch: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(sch)],
                   check=True, capture_output=True)
    return out


def load(net_path: Path) -> Netlist:
    root = parse(Path(net_path).read_text())
    nl = Netlist()
    for c in find_all(find(root, "components"), "comp"):
        ref = find(c, "ref")[1]
        d = {"value": find(c, "value")[1]}
        fp = find(c, "footprint")
        d["footprint"] = fp[1] if fp and len(fp) > 1 else ""
        fields = find(c, "fields")
        for f in find_all(fields, "field") if fields else []:
            d[find(f, "name")[1]] = f[2] if len(f) > 2 and not isinstance(f[2], list) else ""
        nl.comps[ref] = d
    for n in find_all(find(root, "nets"), "net"):
        name = find(n, "name")[1]
        nl.nets[name] = frozenset((find(x, "ref")[1], find(x, "pin")[1]) for x in find_all(n, "node"))
    return nl


def _pin_map(nl: Netlist, renames: dict[str, str]) -> dict[tuple[str, str], str]:
    return {p: renames.get(name, name) for name, pins in nl.nets.items() for p in pins}


def _unconnected(name: str) -> bool:
    return name.startswith("unconnected-")


def diff(old: Netlist, new: Netlist, renames: dict[str, str] = DEFAULT_RENAMES) -> list[str]:
    out = []
    for ref in sorted(set(old.comps) | set(new.comps)):
        if ref not in new.comps or ref not in old.comps:
            out.append(f"{ref}: only in {'old' if ref in old.comps else 'new'}")
            continue
        a = {k: v for k, v in old.comps[ref].items() if k not in FOOTPRINT_KEYS}
        b = {k: v for k, v in new.comps[ref].items() if k not in FOOTPRINT_KEYS}
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                out.append(f"{ref}: field {k} {a.get(k)!r} -> {b.get(k)!r}")
    pa, pb = _pin_map(old, renames), _pin_map(new, renames)
    for p in sorted(set(pa) | set(pb)):
        if p not in pa or p not in pb:
            out.append(f"{p[0]}.{p[1]}: pin only in {'old' if p in pa else 'new'}")
    # same partition: group pins by net on each side and compare the groups
    groups_a = {frozenset(p for p in pa if pa[p] == n) for n in set(pa.values())}
    groups_b = {frozenset(p for p in pb if pb[p] == n) for n in set(pb.values())}
    for g in sorted(groups_a ^ groups_b, key=lambda g: sorted(g)):
        side = "old" if g in groups_a else "new"
        out.append(f"net grouping only in {side}: {sorted(g)[:6]}")
    for p in sorted(set(pa) & set(pb)):
        if pa[p] != pb[p] and not (_unconnected(pa[p]) and _unconnected(pb[p])):
            out.append(f"{p[0]}.{p[1]}: net {pa[p]} -> {pb[p]}")
    return out


def footprint_changes(old: Netlist, new: Netlist) -> dict[str, tuple[str, str]]:
    return {r: (old.comps[r]["footprint"], new.comps[r]["footprint"])
            for r in sorted(set(old.comps) & set(new.comps))
            if old.comps[r]["footprint"] != new.comps[r]["footprint"]}


def reduce(nl: Netlist, removed: set[str], merges: dict[str, str]) -> Netlist:
    """The netlist after taking parts out: their pins go, and nets they separated merge under one name."""
    out = Netlist(comps={r: c for r, c in nl.comps.items() if r not in removed})
    for name, pins in nl.nets.items():
        kept = frozenset(p for p in pins if p[0] not in removed)
        if kept:
            name = merges.get(name, name)
            out.nets[name] = out.nets.get(name, frozenset()) | kept
    return out


def pin_net_mismatches(old: Netlist, new: Netlist, refs: set[str],
                       renames: dict[str, str] = DEFAULT_RENAMES) -> list[str]:
    pa, pb = _pin_map(old, renames), _pin_map(new, renames)
    out = []
    for p in sorted(p for p in pa if p[0] in refs):
        a, b = pa[p], pb.get(p)
        if b is None:
            out.append(f"{p[0]}.{p[1]}: missing in new")
        elif a != b and not (_unconnected(a) and _unconnected(b)):
            out.append(f"{p[0]}.{p[1]}: net {a} -> {b}")
    return out


if __name__ == "__main__":
    o, n = Path(sys.argv[1]), Path(sys.argv[2])
    tmp = Path("out/main_sch")
    a = load(export(o, tmp / "cli_old.net"))
    b = load(export(n, tmp / "cli_new.net"))
    d = diff(a, b)
    print("\n".join(d) or "netlists equivalent")
    for r, (x, y) in footprint_changes(a, b).items():
        print(f"footprint {r}: {x} -> {y}")
    sys.exit(1 if d else 0)
