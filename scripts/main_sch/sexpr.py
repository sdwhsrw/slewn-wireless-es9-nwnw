"""Minimal KiCad s-expression reader/writer.

Quoted strings parse to `Q` (a str subclass) so they are written back quoted;
bare atoms parse to plain str.
"""
import re

_TOKEN = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')


class Q(str):
    """A string that was (or must be) written in double quotes."""


def parse(text: str) -> list:
    stack = [[]]
    for tok in _TOKEN.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif tok.startswith('"'):
            stack[-1].append(Q(re.sub(r'\\(.)', lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), tok[1:-1])))
        else:
            stack[-1].append(tok)
    return stack[0][0]


def _atom(a) -> str:
    if isinstance(a, Q) or a == "" or re.search(r'[\s()"]', a):
        return '"' + a.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return a


def dump(node, indent: int = 0) -> str:
    if not isinstance(node, list):
        return _atom(node)
    atoms = []
    i = 0
    while i < len(node) and not isinstance(node[i], list):
        atoms.append(_atom(node[i]))
        i += 1
    rest = node[i:]
    if all(not isinstance(x, list) for x in rest) and not any(isinstance(x, list) for x in node):
        return "(" + " ".join(atoms) + ")"
    # short all-leaf children stay inline, e.g. (at 1 2 0) inside (property ...)
    if all(isinstance(x, list) and not any(isinstance(y, list) for y in x) for x in rest) and len(rest) <= 3 \
            and sum(len(dump(x)) for x in rest) < 60:
        return "(" + " ".join(atoms + [dump(x) for x in rest]) + ")"
    pad = "\t" * (indent + 1)
    lines = ["(" + " ".join(atoms)]
    for x in rest:
        lines.append(pad + dump(x, indent + 1) if isinstance(x, list) else pad + _atom(x))
    lines.append("\t" * indent + ")")
    return "\n".join(lines)


def find(node: list, key: str) -> list | None:
    """First direct child list whose head is `key`."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(node: list, key: str) -> list:
    return [c for c in node if isinstance(c, list) and c and c[0] == key]
