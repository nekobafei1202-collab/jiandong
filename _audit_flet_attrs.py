"""Enumerate Flet symbols used by jiandong_ai and check availability on Flet 1.x."""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "jiandong_ai"


def collect_ft_attrs(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()

    class V(ast.NodeVisitor):
        def visit_Attribute(self, node: ast.Attribute) -> None:
            # ft.Xxx or ft.Xxx.YYY
            parts: list[str] = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name) and cur.id == "ft":
                found.add(parts[-1])  # top-level attr after ft.
            self.generic_visit(node)

    V().visit(tree)
    return found


def main() -> int:
    import flet as ft

    used: set[str] = set()
    for py in ROOT.rglob("*.py"):
        used |= collect_ft_attrs(py)

    missing = []
    ok = []
    for name in sorted(used):
        try:
            getattr(ft, name)
            ok.append(name)
        except Exception as e:
            missing.append((name, type(e).__name__, str(e)))

    print(f"used={len(used)} ok={len(ok)} missing={len(missing)}")
    for name, et, msg in missing:
        print(f"MISSING {name}: {et}: {msg}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
