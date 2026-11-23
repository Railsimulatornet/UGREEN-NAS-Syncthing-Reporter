"""Offline tests for tag selection and fail-closed release detection."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from release_metadata import (IMAGE, REPOSITORY, changed_files, has_remote_tag,
                              is_release, main, make_metadata, should_publish)


class MetadataTests(unittest.TestCase):
    def test_release_tags(self):
        result = make_metadata('2.2.2', '2026-09-27', '26', '1', True)
        self.assertEqual(result['tags'].splitlines(), [IMAGE + ':' + tag for tag in ('2.2.2', '2.2', '2', 'latest')])
        self.assertEqual(result['build_version'], '2.2.2')

    def test_rebuild_has_no_fixed_tags(self):
        result = make_metadata('2.2.2', '2026-09-27', '26', '1', False)
        self.assertEqual(result['tags'].splitlines(), [IMAGE + ':2.2.2-build.20260927.26.1', IMAGE + ':latest'])
        self.assertNotIn('sha-', result['tags'])

    def test_repeat_build_is_unique(self):
        a = make_metadata('2.2.2', '2026-09-27', '26', '1', False)
        b = make_metadata('2.2.2', '2026-09-27', '26', '2', False)
        self.assertNotEqual(a['build_version'], b['build_version'])

    def test_new_main_version_releases(self):
        self.assertTrue(is_release('2.2.2', 'refs/heads/main', 'push', REPOSITORY, False))
        self.assertFalse(is_release('2.2.2', 'refs/heads/main', 'push', REPOSITORY, True))

    def test_schedule_and_manual_runs_never_release(self):
        for event in ('schedule', 'workflow_dispatch', 'pull_request'):
            self.assertFalse(is_release('2.2.2', 'refs/heads/main', event, REPOSITORY, False))

    def test_other_branches_and_forks_never_release(self):
        self.assertFalse(is_release('2.2.2', 'refs/heads/test', 'push', REPOSITORY, False))
        self.assertFalse(is_release('2.2.2', 'refs/heads/main', 'push', 'example/fork', False))

    def test_tag_must_match_version(self):
        self.assertTrue(is_release('2.2.2', 'refs/tags/v2.2.2', 'push', REPOSITORY, True))
        with self.assertRaises(ValueError):
            is_release('2.2.2', 'refs/tags/v2.2.1', 'push', REPOSITORY, True)

    def test_invalid_metadata_rejected(self):
        for version in ('', '2.2', '02.2.2', '2.2.2\nlatest', '2.2.2;false', '2.2.2-rc1'):
            with self.assertRaises(ValueError):
                make_metadata(version, '2026-09-27', '26', '1', False)
        for number in ('0', '-1', 'a', '26\nlatest'):
            with self.assertRaises(ValueError):
                make_metadata('2.2.2', '2026-09-27', number, '1', False)

    @patch('release_metadata.subprocess.run')
    def test_remote_ref_requires_exact_match(self, run):
        run.return_value.stdout = json.dumps([{'ref': 'refs/tags/v2.2.20'}])
        self.assertFalse(has_remote_tag('2.2.2', REPOSITORY))
        run.return_value.stdout = json.dumps([{'ref': 'refs/tags/v2.2.2'}])
        self.assertTrue(has_remote_tag('2.2.2', REPOSITORY))

    @patch('release_metadata.subprocess.run')
    def test_api_error_does_not_create_release(self, run):
        run.side_effect = subprocess.CalledProcessError(1, ['gh', 'api'])
        with self.assertRaises(subprocess.CalledProcessError):
            has_remote_tag('2.2.2', REPOSITORY)

    @patch('release_metadata.subprocess.run')
    def test_invalid_api_response_rejected(self, run):
        for response in ('{}', 'null', '[{}]', 'not json'):
            run.return_value.stdout = response
            with self.assertRaises(ValueError):
                has_remote_tag('2.2.2', REPOSITORY)

    def test_ci_and_documentation_pushes_do_not_publish(self):
        paths = ['README.md', 'CHANGELOG.md', 'LICENSE', 'Screens/report.png',
                 'UGREEN_Syncthing_Reporter_Handbuch_DE-EN.pdf',
                 '.github/release-notes.md', '.github/release-title.txt',
                 '.github/scripts/integration-reporter.py',
                 '.github/scripts/release_metadata.py',
                 '.github/workflows/docker-publish.yml',
                 'syncthing/syncthing_reporter_py/README.md']
        self.assertFalse(should_publish(REPOSITORY, 'refs/heads/main', 'push', paths))
        self.assertFalse(should_publish(REPOSITORY, 'refs/heads/main', 'push', []))

    def test_runtime_and_package_changes_publish(self):
        for path in ('VERSION', 'syncthing/.env.example',
                     'syncthing/docker-compose.yaml',
                     'syncthing/docker-compose.local-build.yaml',
                     'syncthing/scripts/rebuild_reporter_local.sh',
                     'syncthing/syncthing_reporter_py/Dockerfile',
                     'syncthing/syncthing_reporter_py/.dockerignore',
                     'syncthing/syncthing_reporter_py/report.py',
                     'syncthing/syncthing_reporter_py/requirements.txt'):
            with self.subTest(path=path):
                self.assertTrue(should_publish(REPOSITORY, 'refs/heads/main', 'push', [path]))

    def test_prs_forks_and_other_branches_never_publish(self):
        self.assertFalse(should_publish(REPOSITORY, 'refs/pull/22/merge', 'pull_request', ['VERSION']))
        self.assertFalse(should_publish(REPOSITORY, 'refs/heads/main', 'pull_request', ['VERSION']))
        self.assertFalse(should_publish('example/fork', 'refs/heads/main', 'schedule'))
        self.assertFalse(should_publish(REPOSITORY, 'refs/heads/test', 'workflow_dispatch'))

    def test_scheduled_manual_and_tag_publication_is_preserved(self):
        for event in ('schedule', 'workflow_dispatch'):
            self.assertTrue(should_publish(REPOSITORY, 'refs/heads/main', event))
        self.assertTrue(should_publish(REPOSITORY, 'refs/tags/v2.2.3', 'push'))

    def test_unknown_push_diff_blocks_publication(self):
        with self.assertRaises(ValueError):
            should_publish(REPOSITORY, 'refs/heads/main', 'push')


class PushDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='reporter-publish-gate-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        (self.root / 'VERSION').write_text('2.2.3\n')
        runtime = self.root / 'syncthing/syncthing_reporter_py'
        runtime.mkdir(parents=True)
        (runtime / 'Dockerfile').write_text('FROM python:3.14-alpine\n')
        self.before = self.commit('initial runtime')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=Fixture',
                               '-c', 'user.email=fixture@example.invalid', *args],
                              cwd=self.root, check=True, capture_output=True,
                              text=True, timeout=10).stdout.strip()

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def test_real_complete_diff_detects_runtime_removal_and_initial_push(self):
        (self.root / 'README.md').write_text('Documentation only\n')
        docs = self.commit('documentation')
        paths = changed_files(self.before, docs, docs, cwd=self.root)
        self.assertFalse(should_publish(REPOSITORY, 'refs/heads/main', 'push', paths))
        self.git('mv', 'syncthing/syncthing_reporter_py/Dockerfile', 'removed-runtime.txt')
        after = self.commit('remove runtime path')
        paths = changed_files(self.before, after, after, cwd=self.root)
        self.assertIn('README.md', paths)
        self.assertIn('syncthing/syncthing_reporter_py/Dockerfile', paths)
        self.assertTrue(should_publish(REPOSITORY, 'refs/heads/main', 'push', paths))
        initial = changed_files('0' * 40, self.before, self.before, cwd=self.root)
        self.assertIn('VERSION', initial)

    def test_invalid_commit_missing_history_and_head_mismatch_fail(self):
        with self.assertRaises(ValueError):
            changed_files('--all', self.before, self.before, cwd=self.root)
        with self.assertRaises(ValueError):
            changed_files(self.before, self.before, 'a' * 40, cwd=self.root)
        with self.assertRaises(subprocess.CalledProcessError):
            changed_files('a' * 40, self.before, self.before, cwd=self.root)

    def test_main_ci_only_build_has_no_publication_or_release(self):
        ci = self.root / '.github/scripts'
        ci.mkdir(parents=True)
        (ci / 'integration-reporter.py').write_text('# CI only\n')
        after = self.commit('add integration test')
        payload = self.root / 'push-event.json'
        payload.write_text(json.dumps({'before': self.before, 'after': after}))
        output = self.root / 'metadata-output.txt'
        env = {'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'push',
               'GITHUB_REPOSITORY': REPOSITORY, 'GITHUB_SHA': after,
               'GITHUB_EVENT_PATH': str(payload), 'GITHUB_OUTPUT': str(output),
               'GITHUB_RUN_NUMBER': '42', 'GITHUB_RUN_ATTEMPT': '1'}
        old_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with patch.dict(os.environ, env), patch('release_metadata.has_remote_tag') as lookup:
                main()
                lookup.assert_not_called()
        finally:
            os.chdir(old_cwd)
        result = output.read_text()
        self.assertIn('publish<<REPORTER_METADATA_EOF\nfalse\n', result)
        self.assertIn('release<<REPORTER_METADATA_EOF\nfalse\n', result)


if __name__ == '__main__':
    unittest.main()
