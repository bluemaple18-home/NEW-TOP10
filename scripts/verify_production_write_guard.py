#!/usr/bin/env python3
"""驗證 verify 腳本不會覆寫正式 data/clean。"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
FORBIDDEN_CALLS: list[dict[str, object]] = []
SAFE = "safe"
PRODUCTION = "production"
UNKNOWN = "unknown"


def _is_pipeline_call(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Name)
        and func.id == "ETLPipeline"
        or isinstance(func, ast.Attribute)
        and func.attr == "ETLPipeline"
    )


def _literal_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _production_literal(value: str) -> bool:
    try:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        return path == (PROJECT_ROOT / "data").resolve()
    except OSError:
        return value == "data"


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _expr_state(node: ast.AST, names: dict[str, str]) -> str:
    literal = _literal_text(node)
    if literal is not None:
        return PRODUCTION if _production_literal(literal) else SAFE

    if isinstance(node, ast.Name):
        return names.get(node.id, UNKNOWN)

    if isinstance(node, ast.Call):
        call_name = _call_name(node)
        if call_name in {"str", "Path"} and len(node.args) == 1:
            return _expr_state(node.args[0], names)
        if call_name == "TemporaryDirectory":
            return SAFE
        return UNKNOWN

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _expr_state(node.left, names)
        if left == PRODUCTION:
            return PRODUCTION
        right_literal = _literal_text(node.right)
        if left == SAFE and right_literal is not None and not Path(right_literal).is_absolute():
            return SAFE
        right = _expr_state(node.right, names)
        if left == SAFE and right == SAFE:
            return SAFE
        return UNKNOWN

    return UNKNOWN


def _record_assign(node: ast.AST, names: dict[str, str]) -> None:
    if isinstance(node, ast.Assign):
        state = _expr_state(node.value, names)
        for target in node.targets:
            if isinstance(target, ast.Name):
                names[target.id] = state
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        names[node.target.id] = _expr_state(node.value, names)
    elif isinstance(node, ast.With):
        for item in node.items:
            if isinstance(item.optional_vars, ast.Name) and _expr_state(item.context_expr, names) == SAFE:
                names[item.optional_vars.id] = SAFE


def _forbidden_calls_in_source(path: Path, source: str) -> list[dict[str, object]]:
    tree = ast.parse(source, filename=str(path))
    relative_path = str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)
    forbidden: list[dict[str, object]] = []
    names: dict[str, str] = {}

    for node in ast.walk(tree):
        _record_assign(node, names)
        if not isinstance(node, ast.Call) or not _is_pipeline_call(node):
            continue

        data_dir_keyword = next((keyword for keyword in node.keywords if keyword.arg == "data_dir"), None)
        if data_dir_keyword is None:
            forbidden.append({"path": relative_path, "line": node.lineno, "reason": "ETLPipeline default data_dir"})
            continue

        state = _expr_state(data_dir_keyword.value, names)
        if state == PRODUCTION:
            forbidden.append({"path": relative_path, "line": node.lineno, "reason": "production data_dir"})
        elif state == UNKNOWN:
            forbidden.append({"path": relative_path, "line": node.lineno, "reason": "unresolved data_dir source"})

    return forbidden


def _scan_verify_scripts() -> None:
    for path in sorted((PROJECT_ROOT / "scripts").glob("verify_*.py")):
        if path.name == Path(__file__).name:
            continue
        FORBIDDEN_CALLS.extend(_forbidden_calls_in_source(path, path.read_text(encoding="utf-8")))


def _verify_static_guard_cases() -> None:
    cases = {
        "default": ("from app.pipeline import ETLPipeline\nETLPipeline()\n", True),
        "literal_production": ("from app.pipeline import ETLPipeline\nETLPipeline(data_dir='data')\n", True),
        "variable_production": ("from app.pipeline import ETLPipeline\ndata_dir = 'data'\nETLPipeline(data_dir=data_dir)\n", True),
        "unknown_variable": ("from app.pipeline import ETLPipeline\nETLPipeline(data_dir=data_dir)\n", True),
        "temp_path": (
            "from pathlib import Path\n"
            "from tempfile import TemporaryDirectory\n"
            "from app.pipeline import ETLPipeline\n"
            "with TemporaryDirectory() as tmp_dir:\n"
            "    workspace = Path(tmp_dir)\n"
            "    ETLPipeline(data_dir=str(workspace / 'data'))\n",
            False,
        ),
        "data_test": ("from app.pipeline import ETLPipeline\nETLPipeline(data_dir='data/test')\n", False),
    }
    for name, (source, should_block) in cases.items():
        blocked = bool(_forbidden_calls_in_source(PROJECT_ROOT / f"scripts/verify_static_case_{name}.py", source))
        if blocked != should_block:
            raise AssertionError(f"static guard case failed: {name} blocked={blocked} expected={should_block}")


def _verify_runtime_guard() -> None:
    from app.pipeline import ETLPipeline

    try:
        ETLPipeline(data_dir="data", artifacts_dir="artifacts")
    except RuntimeError as exc:
        if "verify scripts must not write production" not in str(exc):
            raise
    else:
        raise AssertionError("ETLPipeline allowed verify context to write production data_dir='data'")

    with tempfile.TemporaryDirectory(prefix="new-top10-write-guard-") as tmp_dir:
        ETLPipeline(data_dir=str(Path(tmp_dir) / "data"), artifacts_dir=str(Path(tmp_dir) / "artifacts"))


def main() -> int:
    _verify_static_guard_cases()
    _scan_verify_scripts()
    if FORBIDDEN_CALLS:
        print(json.dumps({"status": "FAILED", "forbidden_calls": FORBIDDEN_CALLS}, ensure_ascii=False, indent=2))
        return 1

    _verify_runtime_guard()
    print("PRODUCTION_WRITE_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
