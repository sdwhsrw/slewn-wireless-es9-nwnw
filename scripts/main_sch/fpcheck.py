"""Compare footprint pads (number, position, size, drill) between two .kicad_mod files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402


def _num(x: str) -> float:
    return round(float(x), 3)


def pads(path: Path) -> dict[str, list[tuple]]:
    root = parse(Path(path).read_text())
    out: dict[str, list[tuple]] = {}
    for p in find_all(root, "pad"):
        at, size, drill = find(p, "at"), find(p, "size"), find(p, "drill")
        d = None
        if drill:
            vals = [v for v in drill[1:] if not isinstance(v, list) and v != "oval"]
            d = tuple(_num(v) for v in vals) or None
        out.setdefault(p[1], []).append((_num(at[1]), _num(at[2]), _num(size[1]), _num(size[2]), d))
    for v in out.values():
        v.sort()
    return out


def same_pads(a: Path, b: Path) -> bool:
    return pads(a) == pads(b)


if __name__ == "__main__":
    a, b = pads(sys.argv[1]), pads(sys.argv[2])
    for n in sorted(set(a) | set(b)):
        if a.get(n) != b.get(n):
            print(n, a.get(n), "|", b.get(n))
    print("SAME" if a == b else "DIFFERENT")
