from __future__ import annotations

import ast
from pathlib import Path


def _function_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    checked = 0

    for path in sorted((root / "tests").glob("test*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _function_name(node) != "build_phase8_verification":
                continue

            checked += 1
            keywords = {
                keyword.arg
                for keyword in node.keywords
                if keyword.arg is not None
            }
            if "raw_jd_text" not in keywords:
                failures.append(
                    f"{path.relative_to(root)}:{node.lineno}"
                )

    print("Phase 8 test calls checked:", checked)
    if failures:
        print("Missing raw_jd_text argument:")
        for failure in failures:
            print(" -", failure)
        print("PHASE 8 TEST CALL SIGNATURE CHECK: FAIL")
        return 1

    print("PHASE 8 TEST CALL SIGNATURE CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
