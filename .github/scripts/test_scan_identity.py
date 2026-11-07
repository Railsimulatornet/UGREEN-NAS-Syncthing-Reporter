"""Keep real Trivy results attached to both existing scan configurations."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def job(text, name):
    match = re.search(r'^  ' + re.escape(name) + r':\n(.*?)(?=^  [\w-]+:|\Z)', text, re.M | re.S)
    if match is None:
        raise AssertionError('Missing job: ' + name)
    return match.group(1)


class ScanIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / '.github/workflows/docker-publish.yml').read_text()
        cls.compat = job(cls.workflow, 'build-scan-publish')
        cls.gate = (ROOT / '.github/workflows/dependabot-automerge.yml').read_text()

    def test_existing_scan_job_remains(self):
        current = job(self.workflow, 'build-scan')
        self.assertIn('bash .github/scripts/scan-image.sh', current)
        self.assertIn('syncthing_reporter_trivy.sarif', current)

    def test_legacy_identity_uses_same_run_artifact(self):
        self.assertIn('needs: build-scan', self.compat)
        self.assertIn('name: syncthing-reporter-trivy-results', self.compat)
        self.assertIn('sarif_file: trivy-results/syncthing_reporter_trivy.sarif', self.compat)
        self.assertNotIn('run-id:', self.compat)
        self.assertNotIn('repository:', self.compat)
        self.assertNotIn('continue-on-error', self.compat)
        self.assertNotIn('docker build', self.compat)

    def test_no_history_deletion_or_privileged_publication(self):
        self.assertIn('security-events: write', self.compat)
        self.assertIn('contents: read', self.compat)
        for forbidden in ('contents: write', 'packages: write', 'DELETE', 'gh api', 'secrets.'):
            self.assertNotIn(forbidden, self.compat)

    def test_publication_requires_both_reports(self):
        self.assertIn('needs: [build-scan, build-scan-publish]', job(self.workflow, 'publish'))
        self.assertIn('needs: [build-scan, build-scan-publish, publish]', job(self.workflow, 'release'))

    def test_target_event_tests_only_trusted_base(self):
        target = job(self.gate, 'test')
        self.assertIn("github.event_name == 'pull_request_target'", target)
        self.assertIn('github.event.pull_request.base.sha', target)
        self.assertNotIn('github.event.pull_request.head.sha', target)
        self.assertIn('contents: read', target)
        self.assertNotIn('contents: write', target)


if __name__ == '__main__':
    unittest.main()
