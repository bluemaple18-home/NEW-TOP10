"""只抽取純函式做離線邊界測試；不 import host 或建立環境。"""
import ast
import hashlib
import json
from pathlib import Path
import re
import shlex
import unittest
from unittest.mock import patch
import os
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def functions(filename, names, namespace):
    source = ast.parse((ROOT / 'scripts' / filename).read_text())
    nodes = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), namespace)
    return namespace


class PureContract(unittest.TestCase):
    def test_prompt_reuses_existing_strict_contract_and_packet_bytes(self):
        ns = functions('external_review_mcp_adapter.py', {'build_prompt'},
                       {'re': re, 'json': json, 'hashlib': hashlib})
        data = json.dumps({'packet_date': '2026-11-23', 'market': 'TW', 'recommendations': []}).encode()
        contract = (ROOT / 'docs/architecture/EXTERNAL_REVIEW_CONTRACT.md').read_text()
        prompt = ns['build_prompt'](contract, data, 'chatgpt', 'test-marker')
        boundary = re.search(r'## Reviewer Prompt\b.*?```text\s+(.*?)\s+```', contract, flags=re.S)[1].strip()
        self.assertTrue(prompt.startswith(boundary + '\n'))
        self.assertIn('packet_sha256=' + hashlib.sha256(data).hexdigest(), prompt)
        self.assertIn('request_marker=test-marker', prompt)
        self.assertIn('grounding_proof', prompt)
        self.assertNotIn('欄位名稱可以自然命名', prompt)

    def test_renderer_keeps_spaces_as_one_packet_argument(self):
        ns = functions('run_external_review_host_runner.py', {'render_command'}, {'shlex': shlex, 'Path': Path})
        result = ns['render_command']('bash review.sh --date {date} --packet {packet}',
                                      '2026-11-23', Path('/external root/a packet.json'))
        self.assertEqual(result[-1], '/external root/a packet.json')

    def test_packet_identity_does_not_drop_generated_at(self):
        ns = functions('run_external_review_host_runner.py', {'packet_identity', 'file_sha256'},
                       {'Path': Path, 'hashlib': hashlib})
        with TemporaryDirectory() as temp:
            packet = Path(temp) / 'packet.json'
            packet.write_bytes(b'{"generated_at":"one"}')
            before = ns['packet_identity'](packet)
            packet.write_bytes(b'{"generated_at":"two"}')
            self.assertNotEqual(before, ns['packet_identity'](packet))




class SingleSessionHostTests(unittest.TestCase):
    def _run_native(self, command_template=None, fail_send=False, reject_preflight=False):
        from types import SimpleNamespace
        from typing import Any
        with TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / 'packet.json'
            packet.write_text('{}')
            date = '2026-11-23'
            review = root / 'external_review' / date
            review.mkdir(parents=True)
            calls, checked = [], []

            def preflight(**kwargs):
                calls.append(['probe'])
                return {'status': 'FAILED' if reject_preflight else 'OK', 'reason': 'fixture_preflight'}

            def command(parts):
                calls.append(parts)
                # 原故障：probe 關閉後另建 client，需要第二次授權，不能借用第一次。
                if fail_send or any(row == ['probe'] for row in calls):
                    return SimpleNamespace(exit_code=1, stdout='new_connection_needs_approval', stderr='')
                (review / ('gemini_raw_' + date + '.txt')).write_text('fixture raw')
                (review / ('gemini_collect_status_' + date + '.json')).write_text('{"ok":true}')
                return SimpleNamespace(exit_code=0, stdout='{"ok":true}', stderr='')

            ns = functions('run_external_review_host_runner.py', {'run_provider', 'render_command'}, {
                'Any': Any, 'Path': Path, 'shlex': shlex,
                'provider_defaults': lambda *args, **kwargs: {'status': 'PENDING', 'notes': []},
                'packet_identity': lambda path: hashlib.sha256(path.read_bytes()).hexdigest(),
                'file_sha256': lambda path: hashlib.sha256(path.read_bytes()).hexdigest(),
                'python_bin': lambda: 'python', 'repo_relative': str, 'mask_command': lambda command: command,
                'run_provider_preflight': preflight, 'run_command': command,
                'provider_artifact_errors': lambda **kwargs: [],
                'provider_artifact_identity': lambda *args: {'verified': 'fixture'},
                'run_checked': lambda parts: checked.append(parts),
            })
            state = ns['run_provider']('gemini', date, packet, root, False, 'browser', False,
                command_template or 'bash scripts/review_gemini_chrome.sh --date {date} --packet {packet}')
            return state, calls, checked

    def test_native_send_uses_one_approved_session_without_separate_probe(self):
        state, calls, checked = self._run_native()
        self.assertEqual(state['status'], 'OK', state)
        self.assertEqual(len(calls), 1)
        self.assertNotIn(['probe'], calls)
        self.assertEqual(state['preflight']['mode'], 'native_adapter_same_session')
        self.assertEqual(len(checked), 2)  # 原 normalizer／contract 仍須執行。

    def test_native_failure_does_not_create_another_session_or_retry(self):
        state, calls, checked = self._run_native(fail_send=True)
        self.assertEqual(state['status'], 'FAILED')
        self.assertEqual(len(calls), 1)
        self.assertEqual(checked, [])
        self.assertNotEqual(state['preflight']['status'], 'OK')

    def test_custom_command_keeps_external_preflight_and_stops_on_failure(self):
        state, calls, checked = self._run_native(
            command_template='bash scripts/custom_review.sh --date {date} --packet {packet}',
            reject_preflight=True)
        self.assertEqual(state['status'], 'FAILED')
        self.assertEqual(calls, [['probe']])
        self.assertEqual(checked, [])

class AccountGuardContractTests(unittest.TestCase):
    def test_both_providers_require_explicit_account_before_runtime(self):
        ns = functions('external_review_mcp_adapter.py', {'account_guards'}, {'os': os})
        for provider in ('chatgpt', 'gemini'):
            with self.subTest(provider=provider), patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'EXPECTED_ACCOUNT required'):
                    ns['account_guards'](provider)

    def test_both_providers_pass_their_own_complete_guard(self):
        ns = functions('external_review_mcp_adapter.py', {'account_guards'}, {'os': os})
        with patch.dict(os.environ, {'TOP10_CHATGPT_EXPECTED_ACCOUNT': 'Fixture User Plus',
                'TOP10_GEMINI_EXPECTED_ACCOUNT': 'fixture@example.invalid',
                'TOP10_CHATGPT_EXPECTED_TITLE': 'Fixture Conversation'}, clear=True):
            self.assertEqual(ns['account_guards']('chatgpt')['account'], 'Fixture User Plus')
            self.assertEqual(ns['account_guards']('chatgpt')['title'], 'Fixture Conversation')
            self.assertEqual(ns['account_guards']('gemini')['account'], 'fixture@example.invalid')


if __name__ == '__main__':
    unittest.main()
