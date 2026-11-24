from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    PROJECT_ROOT
    / "tests/fixtures/fog_nofork_native"
    / "fog-nofork-native-runner-20261007.py"
)


def load_runner():
    spec = importlib.util.spec_from_file_location("fog_nofork_native_runner_20261007", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_source(module, root: Path) -> Path:
    source = root / module.PRESERVE_PATH
    (source / "nested").mkdir(parents=True)
    (source / "result.json").write_text('{"status":"PASS"}\n', encoding="utf-8")
    (source / "nested/value.txt").write_text("固定證據\n", encoding="utf-8")
    return source


def publish(module, root: Path, destination: Path, repo: Path):
    return module.publish_cross_volume_evidence(
        root=root,
        destination=destination,
        paths=[module.PRESERVE_PATH],
        repo_root=repo,
        limits={"max_bytes": 1024 * 1024, "max_file_count": 16},
    )


def test_publish_uses_destination_side_staging_and_preserves_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_runner()
    root = tmp_path / "owned-root"
    repo = tmp_path / "repo"
    destination = repo / "evidence/cycle"
    source = build_source(module, root)
    destination.parent.mkdir(parents=True)
    before = module.tree_manifest(source)
    original = module.lifecycle.rename_no_replace
    observed: dict[str, Path] = {}

    def rename(source_path: Path, destination_path: Path) -> None:
        observed["staging_parent"] = source_path.parent
        observed["destination_parent"] = destination_path.parent
        assert source_path.parent == destination_path.parent
        assert source_path.stat().st_dev == destination_path.parent.stat().st_dev
        original(source_path, destination_path)

    monkeypatch.setattr(module.lifecycle, "rename_no_replace", rename)
    result = publish(module, root, destination, repo)

    assert observed["staging_parent"] == destination.parent
    assert module.tree_manifest(source) == before
    assert module.tree_manifest(destination / module.PRESERVE_PATH) == before
    assert result["manifest_sha256"] == module.manifest_sha256(before)
    assert not list(destination.parent.glob(f".{destination.name}.staging-*"))


def test_existing_destination_is_refused_without_changing_source(tmp_path: Path) -> None:
    module = load_runner()
    root = tmp_path / "owned-root"
    repo = tmp_path / "repo"
    destination = repo / "evidence/cycle"
    source = build_source(module, root)
    destination.parent.mkdir(parents=True)
    before = module.tree_manifest(source)
    publish(module, root, destination, repo)

    with pytest.raises(module.lifecycle.LifecycleError, match="destination already exists"):
        publish(module, root, destination, repo)

    assert module.tree_manifest(source) == before
    assert module.tree_manifest(destination / module.PRESERVE_PATH) == before


def test_symlink_in_preserve_tree_is_rejected(tmp_path: Path) -> None:
    module = load_runner()
    root = tmp_path / "owned-root"
    repo = tmp_path / "repo"
    destination = repo / "evidence/cycle"
    source = build_source(module, root)
    destination.parent.mkdir(parents=True)
    (source / "link").symlink_to(source / "result.json")

    with pytest.raises(module.lifecycle.LifecycleError, match="evidence contains symlink"):
        publish(module, root, destination, repo)

    assert not destination.exists()


def test_copy_failure_removes_only_owned_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_runner()
    root = tmp_path / "owned-root"
    repo = tmp_path / "repo"
    destination = repo / "evidence/cycle"
    source = build_source(module, root)
    destination.parent.mkdir(parents=True)
    before = module.tree_manifest(source)

    def fail_copy(*_args, **_kwargs):
        raise OSError("fixture copy failure")

    monkeypatch.setattr(module.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="fixture copy failure"):
        publish(module, root, destination, repo)

    assert module.tree_manifest(source) == before
    assert not destination.exists()
    assert not list(destination.parent.glob(f".{destination.name}.staging-*"))


def test_source_change_during_copy_is_rejected_and_staging_is_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_runner()
    root = tmp_path / "owned-root"
    repo = tmp_path / "repo"
    destination = repo / "evidence/cycle"
    source = build_source(module, root)
    destination.parent.mkdir(parents=True)
    original_copy = module.shutil.copytree

    def copy_then_mutate(*args, **kwargs):
        result = original_copy(*args, **kwargs)
        if Path(args[0]).resolve() == source.resolve():
            (source / "result.json").write_text(
                '{"status":"CHANGED"}\n',
                encoding="utf-8",
            )
        return result

    monkeypatch.setattr(module.shutil, "copytree", copy_then_mutate)
    with pytest.raises(RuntimeError, match="source changed during cross-volume copy"):
        publish(module, root, destination, repo)

    assert not destination.exists()
    assert not list(destination.parent.glob(f".{destination.name}.staging-*"))


def test_fsync_failure_removes_only_owned_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_runner()
    root = tmp_path / "owned-root"
    repo = tmp_path / "repo"
    destination = repo / "evidence/cycle"
    source = build_source(module, root)
    destination.parent.mkdir(parents=True)
    before = module.tree_manifest(source)

    def fail_fsync(_root: Path) -> None:
        raise OSError("fixture fsync failure")

    monkeypatch.setattr(module, "fsync_tree", fail_fsync)
    with pytest.raises(OSError, match="fixture fsync failure"):
        publish(module, root, destination, repo)

    assert module.tree_manifest(source) == before
    assert not destination.exists()
    assert not list(destination.parent.glob(f".{destination.name}.staging-*"))
