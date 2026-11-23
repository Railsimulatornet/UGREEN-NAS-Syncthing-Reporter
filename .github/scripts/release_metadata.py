"""Generate readable image tags; fixed release tags are never used for rebuilds."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

REPOSITORY = 'Railsimulatornet/UGREEN-NAS-Syncthing-Reporter'
IMAGE = 'ghcr.io/railsimulatornet/ugreen-nas-syncthing-reporter'
VERSION_RE = r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)'
COMMIT_RE = r'[0-9a-f]{40}'


def publishable_path(path):
    """Only shipped runtime/configuration changes and versions publish images."""
    if path.endswith(('.md', '.rst')):
        return False
    return (path == 'VERSION'
            or path == 'syncthing/.env.example'
            or path.startswith('syncthing/syncthing_reporter_py/')
            or (path.startswith('syncthing/scripts/') and path.endswith('.sh'))
            or (path.startswith('syncthing/docker-compose')
                and path.endswith(('.yaml', '.yml'))))


def changed_files(before, after, expected_head, *, cwd=None):
    """Read the complete push diff; missing history fails instead of publishing."""
    if (not isinstance(before, str) or not re.fullmatch(COMMIT_RE, before)
            or not isinstance(after, str) or not re.fullmatch(COMMIT_RE, after)
            or after != expected_head):
        raise ValueError('Push commit IDs must be valid and match GITHUB_SHA')
    if before == '0' * 40:
        command = ['git', 'ls-tree', '-r', '--name-only', '-z', after]
    else:
        # Include both sides of renames so a removed runtime file still counts.
        command = ['git', 'diff', '--no-renames', '--name-only', '-z', before, after, '--']
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True,
                            text=True, timeout=30)
    return [path for path in result.stdout.split('\0') if path]


def should_publish(repository, ref, event, paths=None):
    if repository != REPOSITORY:
        return False
    if ref != 'refs/heads/main' and not ref.startswith('refs/tags/v'):
        return False
    if event in ('schedule', 'workflow_dispatch'):
        return True
    if event != 'push':
        return False
    if ref.startswith('refs/tags/v'):
        return True  # is_release additionally checks the tag against VERSION.
    if paths is None:
        raise ValueError('A main push requires its complete changed-file list')
    return any(publishable_path(path) for path in paths)


def validate_version(value):
    if not re.fullmatch(VERSION_RE, value):
        raise ValueError('VERSION must contain a stable major.minor.patch version')
    return value


def is_release(version, ref, event, repository, tag_exists):
    validate_version(version)
    if repository != REPOSITORY or event != 'push':
        return False
    if ref.startswith('refs/tags/'):
        if ref != 'refs/tags/v' + version:
            raise ValueError('Git tag does not match VERSION')
        return True
    return ref == 'refs/heads/main' and not tag_exists


def make_metadata(version, day, run, attempt, release):
    validate_version(version)
    datetime.strptime(day, '%Y-%m-%d')
    for number in (run, attempt):
        if not re.fullmatch(r'[1-9][0-9]*', str(number)):
            raise ValueError('Build run and attempt must be positive integers')
    build = f'{version}-build.{day.replace("-", "")}.{run}.{attempt}'
    major, minor, _ = version.split('.')
    # Immutable/full version first; latest remains available for existing users.
    suffixes = [version, f'{major}.{minor}', major, 'latest'] if release else [build, 'latest']
    return {
        'version': version,
        'build_version': version if release else build,
        'build_date': day,
        'release': 'true' if release else 'false',
        'tags': '\n'.join(IMAGE + ':' + suffix for suffix in suffixes),
    }


def has_remote_tag(version, repository):
    # Read-only lookup. Authentication/network/API errors must not mean "absent".
    validate_version(version)
    if repository != REPOSITORY:
        raise ValueError('Unexpected release repository')
    result = subprocess.run(
        ['gh', 'api', f'repos/{repository}/git/matching-refs/tags/v{version}'],
        check=True, capture_output=True, text=True, timeout=30,
    )
    refs = json.loads(result.stdout)
    if not isinstance(refs, list) or any(not isinstance(item, dict) or 'ref' not in item for item in refs):
        raise ValueError('Unexpected Git ref response')
    return any(item['ref'] == 'refs/tags/v' + version for item in refs)


def main():
    version = validate_version(Path('VERSION').read_text(encoding='utf-8').strip())
    ref = os.environ['GITHUB_REF']
    event = os.environ['GITHUB_EVENT_NAME']
    repository = os.environ['GITHUB_REPOSITORY']
    paths = None
    if repository == REPOSITORY and event == 'push' and ref == 'refs/heads/main':
        payload = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
        paths = changed_files(payload['before'], payload['after'], os.environ['GITHUB_SHA'])
    publish = should_publish(repository, ref, event, paths)
    exists = True
    if publish and event == 'push' and ref == 'refs/heads/main':
        exists = has_remote_tag(version, repository)
    release = publish and is_release(version, ref, event, repository, exists)
    metadata = make_metadata(version, datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                             os.environ['GITHUB_RUN_NUMBER'],
                             os.environ['GITHUB_RUN_ATTEMPT'], release)
    metadata['publish'] = 'true' if publish else 'false'
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for key, value in metadata.items():
            # All values are generated locally from validated version/build data.
            output.write(f'{key}<<REPORTER_METADATA_EOF\n{value}\nREPORTER_METADATA_EOF\n')
    print('Image build: ' + metadata['build_version'])
    print('Image publication: ' + metadata['publish'])
    print('Release publication: ' + metadata['release'])
    print(metadata['tags'])


if __name__ == '__main__':
    main()
