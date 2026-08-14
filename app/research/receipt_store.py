"""Research Spine immutable JSON corpus writer。"""

from __future__ import annotations

import json
import os
import secrets
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from app.research.contracts import canonical_json_bytes


Validator = Callable[[Mapping[str, Any]], list[str]]
_ENTITIES = {"trial_specs", "intents", "attempts", "receipts", "reconciliations", "batch_intents"}


class SchemaValidationError(ValueError):
    pass


class ImmutableCollisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class WriteResult:
    status: str
    path: Path


def write_immutable_json(
    target: Path,
    payload: Mapping[str, Any],
    *,
    validator: Validator,
    identity_field: str | None = None,
) -> WriteResult:
    errors = validator(payload)
    if errors:
        raise SchemaValidationError("; ".join(errors))
    if identity_field:
        identity = str(payload.get(identity_field) or "").removeprefix("sha256:")
        stem = target.name.removesuffix(".started.json").removesuffix(".orphan.json").removesuffix(".json")
        if stem != identity:
            raise ValueError(f"immutable path does not match {identity_field}")
    encoded = json.dumps(
        json.loads(canonical_json_bytes(payload)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() == encoded:
            return WriteResult("EXISTS_IDENTICAL", target)
        raise ImmutableCollisionError(f"immutable target collision: {target}")

    temp = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, target)
        except FileExistsError:
            if target.read_bytes() == encoded:
                return WriteResult("EXISTS_IDENTICAL", target)
            raise ImmutableCollisionError(f"immutable target collision: {target}")
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return WriteResult("CREATED", target)
    finally:
        temp.unlink(missing_ok=True)


def corpus_path(root: Path, entity: str, identity: str, *, suffix: str = ".json") -> Path:
    if entity not in _ENTITIES:
        raise ValueError("immutable entity 無效")
    if not identity or identity in {".", ".."} or "/" in identity or "\\" in identity:
        raise ValueError("immutable identity path 無效")
    safe_identity = identity.removeprefix("sha256:")
    return root / entity / f"{safe_identity}{suffix}"


def publish_file_to_cas(corpus_root: Path, source: Path) -> tuple[str, Path]:
    """將source bytes原子發布至content-addressed corpus。"""
    encoded = source.read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    target = corpus_root / "source_corpus" / "sha256" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != encoded:
            raise ImmutableCollisionError(f"CAS digest collision: {target}")
        return f"sha256:{digest}", target
    temp = target.parent / f".{digest}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, target)
        except FileExistsError:
            if target.read_bytes() != encoded:
                raise ImmutableCollisionError(f"CAS digest collision: {target}")
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return f"sha256:{digest}", target
    finally:
        temp.unlink(missing_ok=True)


def publish_bytes_to_cas(corpus_root: Path, encoded: bytes) -> tuple[str, Path]:
    """發布記憶體中的 immutable bytes；供migration mapping/manifest共用。"""
    digest = hashlib.sha256(encoded).hexdigest()
    target = corpus_root / "source_corpus" / "sha256" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != encoded:
            raise ImmutableCollisionError(f"CAS digest collision: {target}")
        return f"sha256:{digest}", target
    temp = target.parent / f".{digest}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return f"sha256:{digest}", target
    except FileExistsError:
        if target.read_bytes() != encoded:
            raise ImmutableCollisionError(f"CAS digest collision: {target}")
        return f"sha256:{digest}", target
    finally:
        temp.unlink(missing_ok=True)
