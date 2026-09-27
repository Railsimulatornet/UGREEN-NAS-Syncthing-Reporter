"""Offline tests for tag selection and fail-closed release detection."""
import json
import subprocess
import unittest
from unittest.mock import patch
from release_metadata import IMAGE, REPOSITORY, has_remote_tag, is_release, make_metadata


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


if __name__ == '__main__':
    unittest.main()
