"""Check the local update command flow without contacting Docker or a NAS."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'syncthing/scripts/rebuild_reporter_local.sh'


class LocalRebuildTests(unittest.TestCase):
    def run_rebuild(self, version=None, fail_build=False, project_only=False):
        with tempfile.TemporaryDirectory(prefix='local-rebuild-test-') as directory:
            temporary = Path(directory)
            script = SCRIPT
            if project_only:
                shutil.copytree(ROOT / 'syncthing', temporary / 'syncthing')
                script = temporary / 'syncthing/scripts/rebuild_reporter_local.sh'
                self.assertFalse((temporary / 'VERSION').exists())
            fake_docker = temporary / 'docker'
            fake_docker.write_text(f'''#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
with open(os.environ['TEST_DOCKER_LOG'], 'a') as log:
    log.write(json.dumps({{'args': args, 'metadata': {{name: os.environ.get(name) for name in ('REPORTER_VERSION', 'REPORTER_BUILD_VERSION', 'REPORTER_BUILD_DATE')}}}}) + '\\n')
if 'build' in args and os.environ.get('TEST_FAIL_BUILD') == '1':
    sys.exit(42)
''')
            fake_docker.chmod(0o755)
            environment = {
                'PATH': str(temporary) + os.pathsep + os.defpath,
                'TEST_DOCKER_LOG': str(temporary / 'docker.jsonl'),
                'TEST_FAIL_BUILD': '1' if fail_build else '0',
                'REPORTER_BUILD_DATE': '2026-10-17',
            }
            arguments = ['sh', str(script)]
            if version is not None:
                arguments.append(version)
            result = subprocess.run(arguments, env=environment, capture_output=True,
                                    text=True, timeout=10, check=False)
            log = temporary / 'docker.jsonl'
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, calls

    def test_success_builds_before_recreating_only_reporter(self):
        result, calls = self.run_rebuild('2.2.2-local.1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0]['args'], ['compose', 'version'])
        self.assertEqual(calls[1]['args'][-4:], ['build', '--pull', '--no-cache', 'syncthing_reporter_py'])
        self.assertEqual(calls[2]['args'][-5:], ['up', '-d', '--no-deps', '--force-recreate', 'syncthing_reporter_py'])
        self.assertEqual(calls[3]['args'][-2:], ['ps', 'syncthing_reporter_py'])
        for call in calls:
            self.assertNotIn('stop', call['args'])
            self.assertNotIn('rmi', call['args'])
            self.assertEqual(call['metadata']['REPORTER_VERSION'], 'V' + (ROOT / 'VERSION').read_text().strip())
            self.assertEqual(call['metadata']['REPORTER_BUILD_VERSION'], '2.2.2-local.1')
            self.assertEqual(call['metadata']['REPORTER_BUILD_DATE'], '2026-10-17')

    def test_failed_build_preserves_running_service_and_images(self):
        result, calls = self.run_rebuild('2.2.2-local.1', fail_build=True)
        self.assertEqual(result.returncode, 42)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertFalse({'stop', 'rmi', 'up'} & set(call['args']))
        self.assertNotIn('[done]', result.stdout)

    def test_default_version_comes_from_release_file(self):
        result, calls = self.run_rebuild()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[1]['metadata']['REPORTER_BUILD_VERSION'], (ROOT / 'VERSION').read_text().strip())

    def test_documented_project_folder_installation(self):
        release = (ROOT / 'VERSION').read_text().strip()
        for version in (None, release + '-local.1'):
            with self.subTest(version=version):
                result, calls = self.run_rebuild(version, project_only=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(calls), 4)
                self.assertEqual(calls[1]['metadata']['REPORTER_VERSION'], 'V' + release)
                self.assertEqual(calls[1]['metadata']['REPORTER_BUILD_VERSION'], version or release)
                self.assertEqual(calls[1]['args'][-4:], ['build', '--pull', '--no-cache', 'syncthing_reporter_py'])
                self.assertEqual(calls[2]['args'][-5:], ['up', '-d', '--no-deps', '--force-recreate', 'syncthing_reporter_py'])

    def test_invalid_tag_fails_before_any_docker_command(self):
        for value in ('-bad', '.bad', 'bad tag', 'bad/tag', 'a' * 129):
            with self.subTest(value=value):
                result, calls = self.run_rebuild(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
