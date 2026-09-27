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
    exists = True
    if repository == REPOSITORY and event == 'push' and ref == 'refs/heads/main':
        exists = has_remote_tag(version, repository)
    release = is_release(version, ref, event, repository, exists)
    metadata = make_metadata(version, datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                             os.environ['GITHUB_RUN_NUMBER'],
                             os.environ['GITHUB_RUN_ATTEMPT'], release)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for key, value in metadata.items():
            # All values are generated locally from validated version/build data.
            output.write(f'{key}<<REPORTER_METADATA_EOF\n{value}\nREPORTER_METADATA_EOF\n')
    print('Image build: ' + metadata['build_version'])
    print('Release publication: ' + metadata['release'])
    print(metadata['tags'])


if __name__ == '__main__':
    main()
