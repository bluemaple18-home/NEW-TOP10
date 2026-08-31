#!/usr/bin/env python3
"""以 repo 內 deterministic fixture 重建並驗證 A6 closure receipt。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.a6_closure import DEFAULT_OUTPUT, verify_a6_closure
from app.research.legacy_migration import LegacySource, build_migration
from tests.test_research_ledger import corpus_with_receipt
from tests.test_research_legacy_migration import write_matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-ref", default="bb617e98aabefcc52bbf7cb1834fb5fba715d60a")
    parser.add_argument("--candidate-ref", default="HEAD")
    args = parser.parse_args()
    root = Path(tempfile.gettempdir()) / "new-top10-a6-fixed-fixture"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    try:
        corpus, _ = corpus_with_receipt(root / "corpus")
        legacy_source = root / "legacy" / "matrix.json"
        write_matrix(legacy_source)
        build_migration(corpus_root=corpus, sources=[LegacySource(legacy_source, "STRATEGY_MATRIX")])
        receipt = verify_a6_closure(
            corpus_root=corpus, output_root=root / "generated", base_ref=args.base_ref,
            candidate_ref=args.candidate_ref,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": receipt["status"], "output": str(args.output)}, sort_keys=True))
        return 0 if receipt["status"] == "PASS" else 1
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    raise SystemExit(main())
