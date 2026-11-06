#!/usr/bin/env python3
"""AI Core finite2 專用的固定 Fog no-fork 候選葉節點。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import run_fog_representative_validation as representative  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "execute"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args(argv)

    if os.environ.get("AI_CORE_TMP_ARTIFACT_ACTIVE") != "1":
        parser.error("NO_GO: 必須由 AI Core tmp lifecycle 啟動")
    validation_root_text = os.environ.get("TMP_ARTIFACT_ROOT", "")
    if not validation_root_text:
        parser.error("NO_GO: 缺少 lifecycle-owned TMP_ARTIFACT_ROOT")
    source_root = args.source_root.resolve(strict=True)
    if source_root != representative.PROJECT_ROOT.resolve(strict=True):
        parser.error("NO_GO: source root 與候選程式身分不符")

    validation_root = Path(validation_root_text)
    if args.phase == "prepare":
        return representative.prepare_nofork_candidate(
            validation_root=validation_root,
            source_commit=args.source_commit,
        )
    return representative.execute_nofork_candidate(
        validation_root=validation_root,
        source_commit=args.source_commit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
