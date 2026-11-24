#!/usr/bin/env python3
"""TOP10 固定 Fog 兩葉 no-fork 實機驗證；不提供正式啟動 authority。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import signal
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

AI_CORE = Path(os.environ.get('AI_CORE_DIR', str(Path.home() / 'ai-core')))
PROJECT = Path(__file__).resolve().parents[3]
VOLUME = Path('/Volumes/VibeCode')
EXPECTED_VOLUME_UUID = '27BEBF8F-6320-4E2F-965B-FF4517016A1F'
PRESERVE_PATH = 'artifacts/autonomous_research/validation_fixture'

from scripts.storage_validation.boundary import core_module
lifecycle = core_module('tmp_artifact_lifecycle')


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def tree_manifest(root: Path) -> list[dict[str, object]]:
    """以 no-follow FD 建立 deterministic tree manifest，拒絕 symlink／特殊節點。"""

    lexical = Path(os.path.abspath(root))
    if lexical.is_symlink() or lexical.resolve(strict=True) != lexical or not lexical.is_dir():
        raise RuntimeError('evidence tree root is unsafe')
    rows: list[dict[str, object]] = []
    for path in sorted(lexical.rglob('*')):
        relative = str(path.relative_to(lexical))
        info = os.lstat(path)
        if stat.S_ISDIR(info.st_mode):
            rows.append({'path': relative, 'kind': 'dir'})
            continue
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError(f'unsupported evidence node: {relative}')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            opened = os.fstat(descriptor)
            expected = (info.st_dev, info.st_ino, info.st_size)
            if not stat.S_ISREG(opened.st_mode) or (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
            ) != expected:
                raise RuntimeError(f'evidence file identity changed: {relative}')
            digest = hashlib.sha256()
            with os.fdopen(descriptor, 'rb', closefd=False) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            if os.fstat(descriptor).st_size != info.st_size:
                raise RuntimeError(f'evidence file size changed: {relative}')
        finally:
            os.close(descriptor)
        rows.append(
            {
                'path': relative,
                'kind': 'file',
                'size': info.st_size,
                'sha256': digest.hexdigest(),
            }
        )
    return rows


def manifest_sha256(rows: list[dict[str, object]]) -> str:
    encoded = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def fsync_tree(root: Path) -> None:
    """發布前 fsync regular files 與目錄；任何未知均 fail closed。"""

    directories = [root]
    for path in sorted(root.rglob('*')):
        info = os.lstat(path)
        if stat.S_ISDIR(info.st_mode):
            directories.append(path)
        elif stat.S_ISREG(info.st_mode):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        else:
            raise RuntimeError(f'unsupported staged evidence node: {path}')
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def publish_cross_volume_evidence(
    *,
    root: Path,
    destination: Path,
    paths: list[str],
    repo_root: Path,
    limits: dict[str, int],
) -> dict[str, object]:
    """在 destination filesystem staging，核對 hash 後原子 no-replace 發布。"""

    if paths != [PRESERVE_PATH]:
        raise RuntimeError('unexpected evidence preserve plan')
    plan = lifecycle.validate_evidence_plan(root, destination, paths, repo_root)
    if len(plan) != 1 or not plan[0][2]:
        raise RuntimeError('fixed evidence directory plan required')
    source, target, _ = plan[0]
    destination_abs = lifecycle.lexical_absolute(destination)
    if not destination_abs.parent.is_dir() or destination_abs.parent.is_symlink():
        raise RuntimeError('evidence destination parent is unsafe')

    source_before = tree_manifest(source)
    file_rows = [row for row in source_before if row['kind'] == 'file']
    logical_bytes = sum(int(row['size']) for row in file_rows)
    if logical_bytes > limits['max_bytes'] or len(file_rows) > limits['max_file_count']:
        raise RuntimeError('evidence preserve tree exceeds lifecycle budget')

    staging = destination_abs.parent / f'.{destination_abs.name}.staging-{uuid.uuid4().hex}'
    published = False
    try:
        os.mkdir(staging, mode=0o700)
        staged_target = staging / target.relative_to(destination_abs)
        staged_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, staged_target)

        source_after = tree_manifest(source)
        staged_manifest = tree_manifest(staged_target)
        if source_before != source_after:
            raise RuntimeError('evidence source changed during cross-volume copy')
        if source_before != staged_manifest:
            raise RuntimeError('cross-volume evidence hash verification failed')
        fsync_tree(staging)
        lifecycle.rename_no_replace(staging, destination_abs)
        published = True

        destination_manifest = tree_manifest(destination_abs / PRESERVE_PATH)
        if destination_manifest != source_before:
            raise RuntimeError('published evidence verification failed')
        parent_fd = os.open(
            destination_abs.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return {
            'destination': str(destination_abs),
            'source_device': os.stat(source, follow_symlinks=False).st_dev,
            'destination_device': os.stat(destination_abs, follow_symlinks=False).st_dev,
            'file_count': len(file_rows),
            'logical_bytes': logical_bytes,
            'manifest_sha256': manifest_sha256(source_before),
        }
    finally:
        if not published and (staging.exists() or staging.is_symlink()):
            shutil.rmtree(staging)
            if staging.exists() or staging.is_symlink():
                raise RuntimeError('cross-volume evidence staging cleanup failed')


def verify_freeze(freeze: dict[str, object]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, expected in dict(freeze['sha256']).items():
        path = Path(name)
        actual = sha256_file(path)
        observed[name] = actual
        if actual != expected:
            raise RuntimeError(f'frozen source changed: {name}')
    return observed


def check_volume(fd: int, identity: os.stat_result) -> dict[str, object]:
    mount_text = subprocess.check_output(['/sbin/mount'], text=True, timeout=8)
    mount_match = None
    for line in mount_text.splitlines():
        match = re.fullmatch(r'(/dev/\S+) on /Volumes/VibeCode \(([^)]*)\)', line)
        if match:
            mount_match = match
            break
    if mount_match is None:
        raise RuntimeError('VibeCode mount identity unavailable')
    device_path, mount_options = mount_match.groups()
    bsd_name = Path(device_path).name
    ioreg_text = subprocess.check_output(
        ['/usr/sbin/ioreg', '-r', '-c', 'AppleAPFSVolume', '-l'],
        text=True,
        timeout=12,
    )
    blocks = re.split(r'(?m)^\s*\+-o ', ioreg_text)
    matching = [block for block in blocks if f'"BSD Name" = "{bsd_name}"' in block]
    if len(matching) != 1:
        raise RuntimeError('APFS volume identity is ambiguous')
    block = matching[0]
    uuid_match = re.search(r'"UUID" = "([0-9A-F-]+)"', block)
    name_match = re.search(r'"FullName" = "([^"]+)"', block)
    if uuid_match is None or uuid_match.group(1) != EXPECTED_VOLUME_UUID:
        raise RuntimeError('unexpected volume UUID')
    if name_match is None or name_match.group(1) != 'VibeCode':
        raise RuntimeError('unexpected APFS volume name')
    current = os.stat(VOLUME, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
        raise RuntimeError('volume identity changed')
    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
        raise RuntimeError('opened volume identity changed')
    return {
        'volume_uuid': uuid_match.group(1),
        'device': identity.st_dev,
        'inode': identity.st_ino,
        'mount_point': str(VOLUME),
        'mount_device': device_path,
        'mount_options': mount_options,
        'filesystem': 'apfs',
        'identity_source': 'mount+ioreg+open-fd',
    }


def swap_used() -> int:
    raw = subprocess.check_output(
        ['/usr/sbin/sysctl', '-n', 'vm.swapusage'], text=True, timeout=5
    )
    match = re.search(r'used = ([0-9.]+)([KMGT])', raw)
    if not match:
        raise RuntimeError('unknown swap observation')
    scale = {'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
    return int(float(match.group(1)) * scale[match.group(2)])


def rss_tree(pid: int) -> int:
    raw = subprocess.check_output(
        ['/bin/ps', '-axo', 'pid=,ppid=,rss='], text=True, timeout=5
    )
    rows = [tuple(map(int, line.split())) for line in raw.splitlines() if line.split()]
    owned = {pid}
    for _ in range(12):
        expanded = owned | {child for child, parent, _ in rows if parent in owned}
        if expanded == owned:
            break
        owned = expanded
    return sum(rss * 1024 for child, _, rss in rows if child in owned)


def scan_root(root: Path | None) -> dict[str, object]:
    if root is None or not root.exists():
        return {'exists': False, 'bytes': 0, 'allocated_bytes': 0, 'files': 0, 'symlinks': []}
    total = allocated = files = 0
    symlinks: list[str] = []
    for path in root.rglob('*'):
        if path.is_symlink():
            symlinks.append(str(path.relative_to(root)))
            continue
        if path.is_file():
            info = path.stat()
            total += info.st_size
            allocated += info.st_blocks * 512
            files += 1
    return {
        'exists': True,
        'bytes': total,
        'allocated_bytes': allocated,
        'files': files,
        'symlinks': symlinks,
    }


def repo_status(excluded_prefix: str) -> list[str]:
    raw = subprocess.check_output(
        ['git', 'status', '--porcelain=v1', '--untracked-files=all'],
        cwd=PROJECT,
        text=True,
    )
    return sorted(
        line for line in raw.splitlines()
        if line and excluded_prefix not in line
    )


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--cycle', type=int, choices=(1, 2), required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()

    freeze = load_json(args.freeze)
    source_commit = str(freeze['source_commit'])
    evidence_dir = args.evidence_dir.resolve(strict=False)
    evidence_relative = str(evidence_dir.relative_to(PROJECT))
    if evidence_dir.exists() or evidence_dir.is_symlink():
        raise SystemExit('evidence destination already exists')

    limits = {'max_bytes': 64 * 1024**2, 'max_file_count': 250, 'ttl_seconds': 300}
    observation_limits = {
        'rss_tree_bytes': 768 * 1024**2,
        'swap_growth_bytes': 64 * 1024**2,
        'elapsed_seconds': 330,
        'sample_interval_seconds': 0.25,
    }
    events: list[dict[str, object]] = []
    root_holder: dict[str, Path | None] = {'root': None}
    marker_holder: dict[str, Path | None] = {'path': None}
    stop_reason: list[str] = []
    resource_samples: list[dict[str, object]] = []
    source_before = verify_freeze(freeze)
    repo_before = repo_status(evidence_relative)

    volume_fd = os.open(VOLUME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    volume_identity = os.fstat(volume_fd)
    if volume_identity.st_dev == os.stat('/').st_dev:
        raise SystemExit('external volume missing')
    volume_before = check_volume(volume_fd, volume_identity)

    lifecycle.tempfile.tempdir = str(VOLUME)
    capacity_before = lifecycle.assert_projected_capacity(limits)
    managed_before = lifecycle.assert_managed_tmp_admission(limits)
    internal_capacity = lifecycle.measure_host_capacity(Path('/private/tmp'))
    swap_before = swap_used()
    started = time.monotonic()
    monitor_active = threading.Event()
    monitor_stop = threading.Event()

    def emit(role: str, **payload: object) -> None:
        event = {'role': role, 'elapsed_seconds': time.monotonic() - started, **payload}
        events.append(event)
        print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)

    def monitor() -> None:
        next_volume_check = 0.0
        while not monitor_stop.wait(observation_limits['sample_interval_seconds']):
            if not monitor_active.is_set():
                continue
            elapsed = time.monotonic() - started
            try:
                rss = rss_tree(os.getpid())
                swap = swap_used()
                if elapsed >= next_volume_check:
                    check_volume(volume_fd, volume_identity)
                    next_volume_check = elapsed + 2.0
                sample = {'elapsed_seconds': elapsed, 'rss_tree_bytes': rss, 'swap_bytes': swap}
                resource_samples.append(sample)
                reason = None
                if rss > observation_limits['rss_tree_bytes']:
                    reason = 'rss observation bound exceeded'
                elif swap - swap_before > observation_limits['swap_growth_bytes']:
                    reason = 'swap growth observation bound exceeded'
                elif elapsed > observation_limits['elapsed_seconds']:
                    reason = 'elapsed observation bound exceeded'
                if reason and not stop_reason:
                    stop_reason.append(reason)
                    emit('observer_stop', reason=reason, sample=sample)
                    os.kill(os.getpid(), signal.SIGTERM)
            except Exception as error:  # fail closed and let SignalController stop the leaf
                if not stop_reason:
                    stop_reason.append(f'observer unknown: {type(error).__name__}: {error}')
                    emit('observer_stop', reason=stop_reason[0])
                    os.kill(os.getpid(), signal.SIGTERM)
                return

    monitor_thread = threading.Thread(target=monitor, name='top10-fog-observer', daemon=True)
    monitor_thread.start()

    original_create = lifecycle.create_root
    original_anchor = lifecycle.process_group_anchor
    original_proof = lifecycle.ChildExitObserver.require_no_forks
    original_run = lifecycle.run_child
    original_update = lifecycle.update_isolation_marker
    original_cleanup = lifecycle.cleanup
    original_preserve_unknown = lifecycle.preserve_unknown_isolation
    step_index = {'value': 0}

    def create(*values: object, **kwargs: object) -> Path:
        root = original_create(*values, **kwargs)
        root_holder['root'] = root
        monitor_active.set()
        info = os.stat(root)
        emit('root_created', root=str(root), device=info.st_dev, inode=info.st_ino)
        return root

    def anchor(process: subprocess.Popen[bytes], observer: object) -> object:
        result = original_anchor(process, observer)
        emit(
            'anchor',
            pid=result.pid,
            pgid=result.process_group,
            sid=result.session,
            start=result.start_time,
        )
        return result

    def proof(observer: object) -> None:
        original_proof(observer)
        emit('native_nofork_proof', pid=observer.pid)

    def run(*values: object, **kwargs: object) -> int:
        command = list(values[0])
        step_index['value'] += 1
        phase = command[3] if len(command) > 3 else 'unknown'
        emit('step_started', step=step_index['value'], phase=phase, command=command)
        try:
            result = original_run(*values, **kwargs)
        except Exception as error:
            emit(
                'step_error',
                step=step_index['value'],
                phase=phase,
                error=f'{type(error).__name__}: {error}',
                root_usage=scan_root(root_holder['root']),
            )
            raise
        emit(
            'step_stopped',
            step=step_index['value'],
            phase=phase,
            exit=result,
            deadline=kwargs.get('absolute_deadline'),
            root_usage=scan_root(root_holder['root']),
        )
        return result

    def update(isolation: dict[str, object], root: Path | None, status: str) -> None:
        marker_holder['path'] = Path(isolation['path'])
        original_update(isolation, root, status)
        emit('marker', status=status, root=None if root is None else str(root), path=str(isolation['path']))

    def preserve_unknown(isolation: dict[str, object], root: Path | None) -> None:
        marker_holder['path'] = Path(isolation['path'])
        original_preserve_unknown(isolation, root)
        emit('marker_unknown', root=None if root is None else str(root), path=str(isolation['path']))

    def cleanup(*values: object, **kwargs: object) -> bool:
        emit('finalize_started', root=str(values[0]), root_usage=scan_root(root_holder['root']))
        if len(values) != 4 or kwargs:
            raise RuntimeError('unexpected lifecycle cleanup call shape')
        export = publish_cross_volume_evidence(
            root=Path(str(values[0])),
            destination=Path(str(values[2])),
            paths=list(values[3]),
            repo_root=Path(values[1]),
            limits=limits,
        )
        emit('evidence_published', **export)
        result = original_cleanup(values[0], values[1], None, [])
        emit(
            'finalize_stopped',
            result=result,
            root_exists=bool(root_holder['root'] and root_holder['root'].exists()),
            evidence_dir=str(evidence_dir),
            evidence_exists=evidence_dir.exists(),
        )
        return result

    python_bin = str(PROJECT / '.venv/bin/python')
    leaf = str(PROJECT / 'scripts/run_fog_nofork_leaf.py')
    common = ('--source-root', str(PROJECT), '--source-commit', source_commit)
    commands = (
        (python_bin, '-B', leaf, 'prepare', *common),
        (python_bin, '-B', leaf, 'execute', *common),
    )
    lifecycle_args = SimpleNamespace(
        policy=str(AI_CORE / 'config/tmp_artifact_policy.json'),
        repo_root=str(PROJECT),
        purpose=f'top10-fog-nofork-c{args.cycle}',
        command=[],
        require_complete_stop_proof=True,
        max_bytes=limits['max_bytes'],
        max_file_count=limits['max_file_count'],
        ttl_seconds=limits['ttl_seconds'],
        pycache=False,
        evidence_dir=str(evidence_dir),
        preserve=[PRESERVE_PATH],
        mode=None,
    )

    os.environ['TOP10_STORAGE_VALIDATION_MODE'] = '1'
    os.environ['TOP10_VALIDATION_SOURCE_COMMIT'] = source_commit
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['PYTHONHASHSEED'] = '0'

    lifecycle_exit = 2
    lifecycle_error = None
    try:
        with patch.object(lifecycle, 'create_root', create), \
                patch.object(lifecycle, 'process_group_anchor', anchor), \
                patch.object(lifecycle.ChildExitObserver, 'require_no_forks', proof), \
                patch.object(lifecycle, 'run_child', run), \
                patch.object(lifecycle, 'update_isolation_marker', update), \
                patch.object(lifecycle, 'preserve_unknown_isolation', preserve_unknown), \
                patch.object(lifecycle, 'cleanup', cleanup):
            lifecycle_exit = lifecycle.command_run(lifecycle_args, commands=commands)
    except Exception as error:
        lifecycle_error = f'{type(error).__name__}: {error}'
        emit('driver_error', error=lifecycle_error)
    finally:
        monitor_stop.set()
        monitor_thread.join(timeout=5)

    elapsed = time.monotonic() - started
    swap_after = swap_used()
    volume_after = check_volume(volume_fd, volume_identity)
    capacity_after = lifecycle.assert_projected_capacity(limits)
    managed_after = lifecycle.assert_managed_tmp_admission(limits)
    source_after = verify_freeze(freeze)
    repo_after = repo_status(evidence_relative)
    os.close(volume_fd)

    root = root_holder['root']
    marker = marker_holder['path']
    preserved_root = evidence_dir / PRESERVE_PATH
    validation_output = preserved_root / 'fog_representative_validation_2026-08-31.json'
    verification_output = preserved_root / 'fog_representative_batch_verification_2026-08-31.json'
    validation_payload = load_json(validation_output) if validation_output.exists() else None
    verification_payload = load_json(verification_output) if verification_output.exists() else None
    nofork_events = [event for event in events if event['role'] == 'native_nofork_proof']
    stopped_events = [event for event in events if event['role'] == 'step_stopped']
    pass_conditions = {
        'lifecycle_exit_zero': lifecycle_exit == 0,
        'lifecycle_error_absent': lifecycle_error is None,
        'observer_stop_absent': not stop_reason,
        'two_nofork_proofs': len(nofork_events) == 2,
        'two_zero_exit_steps': len(stopped_events) == 2 and all(event.get('exit') == 0 for event in stopped_events),
        'root_absent_after': root is not None and not root.exists() and not root.is_symlink(),
        'marker_absent_after': marker is not None and not marker.exists() and not marker.is_symlink(),
        'evidence_bundle_present': evidence_dir.is_dir(),
        'validation_pass': isinstance(validation_payload, dict) and validation_payload.get('status') == 'PASS',
        'verification_pass': isinstance(verification_payload, dict) and verification_payload.get('status') == 'PASS',
        'source_hashes_unchanged': source_before == source_after,
        'git_visible_source_status_unchanged': repo_before == repo_after,
        'volume_identity_unchanged': volume_before == volume_after,
    }
    status = 'PASS' if all(pass_conditions.values()) else 'BLOCKED_WITH_EVIDENCE'
    receipt = {
        'schema_version': 'top10-fog-nofork-native-cycle.v1',
        'status': status,
        'cycle': args.cycle,
        'source_commit': source_commit,
        'freeze_path': str(args.freeze),
        'source_sha256': source_after,
        'lifecycle_exit': lifecycle_exit,
        'lifecycle_error': lifecycle_error,
        'pass_conditions': pass_conditions,
        'events': events,
        'root': None if root is None else str(root),
        'root_remaining': scan_root(root),
        'marker': None if marker is None else str(marker),
        'marker_exists_after': bool(marker and (marker.exists() or marker.is_symlink())),
        'evidence_dir': str(evidence_dir),
        'preserved_root_usage': scan_root(preserved_root),
        'validation_output': str(validation_output),
        'validation_payload_summary': None if not isinstance(validation_payload, dict) else {
            'status': validation_payload.get('status'),
            'fixture_date': validation_payload.get('fixture_date'),
            'batch_id': validation_payload.get('batch_id'),
            'batch_intent_id': validation_payload.get('batch_intent_id'),
            'topic_run_count': len(validation_payload.get('topic_runs') or []),
            'production_promotion_allowed': validation_payload.get('production_promotion_allowed'),
        },
        'verification_output': str(verification_output),
        'verification_payload_status': verification_payload.get('status') if isinstance(verification_payload, dict) else None,
        'limits': limits,
        'observation_limits': observation_limits,
        'fresh_capacity_before': asdict(capacity_before),
        'fresh_capacity_after': asdict(capacity_after),
        'internal_capacity_observation': asdict(internal_capacity),
        'managed_preflight_before': managed_before,
        'managed_preflight_after': managed_after,
        'volume_before': volume_before,
        'volume_after': volume_after,
        'elapsed_seconds': elapsed,
        'swap_before_bytes': swap_before,
        'swap_after_bytes': swap_after,
        'swap_sampled_growth_peak_bytes': max(
            [0, swap_after - swap_before]
            + [int(sample['swap_bytes']) - swap_before for sample in resource_samples]
        ),
        'rss_sampled_peak_bytes': max(
            [0] + [int(sample['rss_tree_bytes']) for sample in resource_samples]
        ),
        'resource_sample_count': len(resource_samples),
        'resource_samples': resource_samples,
        'stop_reason': stop_reason[0] if stop_reason else None,
        'repo_status_before_excluding_evidence': repo_before,
        'repo_status_after_excluding_evidence': repo_after,
        'unknown_write_scope': 'git-visible project source checked; host-wide writes outside managed root were not traced',
        'production_promotion_allowed': False,
        'formal_fog_restart_allowed': False,
    }
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': status,
        'cycle': args.cycle,
        'lifecycle_exit': lifecycle_exit,
        'pass_conditions': pass_conditions,
        'elapsed_seconds': elapsed,
        'rss_sampled_peak_bytes': receipt['rss_sampled_peak_bytes'],
        'swap_sampled_growth_peak_bytes': receipt['swap_sampled_growth_peak_bytes'],
        'receipt': str(args.receipt),
    }, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
