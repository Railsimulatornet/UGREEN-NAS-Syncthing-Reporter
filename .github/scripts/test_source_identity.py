"""Verify that PR source, image revision and uploaded scans name one commit."""
import os
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
HEAD_EXPR = '${{ github.event.pull_request.head.sha || github.sha }}'
REF_EXPR = "${{ github.event_name == 'pull_request' && format('refs/pull/{0}/head', github.event.pull_request.number) || github.ref }}"


def verification_script(workflow):
    match = re.search(
        r'^      - name: Verify checked-out source revision\n'
        r'        shell: bash\n        run: \|\n((?:          [^\n]*\n)+)',
        workflow, re.M)
    if match is None:
        raise AssertionError('Missing executable source revision check')
    return ''.join(line[10:] for line in match.group(1).splitlines(keepends=True))


class SourceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = (ROOT / '.github/workflows/docker-publish.yml').read_text()
        cls.codeql = (ROOT / '.github/workflows/codeql.yml').read_text()

    def test_build_and_codeql_check_out_exact_pr_head(self):
        for workflow in (self.build, self.codeql):
            with self.subTest(workflow=workflow.splitlines()[0]):
                self.assertIn('          ref: ' + HEAD_EXPR, workflow)
                self.assertIn('  SOURCE_SHA: ' + HEAD_EXPR, workflow)
                self.assertIn('  SOURCE_REF: ' + REF_EXPR, workflow)
                self.assertIn('          persist-credentials: false', workflow)

    def test_actual_workflow_checks_reject_wrong_or_missing_revision(self):
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
        wrong = ('0' if head[0] != '0' else '1') + head[1:]
        for workflow in (self.build, self.codeql):
            script = verification_script(workflow)
            for sha, expected in ((head, 0), (wrong, 1), ('', 1), ('not-a-sha', 1)):
                with self.subTest(workflow=workflow.splitlines()[0], sha=sha):
                    env = dict(os.environ, SOURCE_SHA=sha)
                    result = subprocess.run(['bash', '-c', script], cwd=ROOT, env=env,
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    if expected == 0:
                        self.assertIn('Verified source revision: ' + head, result.stdout)

    def test_image_label_and_all_scans_use_verified_source(self):
        self.assertIn('org.opencontainers.image.revision=${{ env.SOURCE_SHA }}', self.build)
        self.assertIn('[[ "$revision" == "$SOURCE_SHA" ]]', self.build)
        for workflow, count in ((self.build, 2), (self.codeql, 1)):
            self.assertEqual(workflow.count('          sha: ${{ env.SOURCE_SHA }}'), count)
            self.assertEqual(workflow.count('          ref: ${{ env.SOURCE_REF }}'), count)

    def test_push_identity_and_release_target_are_preserved(self):
        metadata = (ROOT / '.github/scripts/release_metadata.py').read_text()
        self.assertIn("changed_files(payload['before'], payload['after'], os.environ['GITHUB_SHA'])", metadata)
        self.assertIn('--target "$GITHUB_SHA"', self.build)
        self.assertNotRegex(self.build + self.codeql, re.compile(r'^\s+GITHUB_SHA:', re.M))


if __name__ == '__main__':
    unittest.main()
