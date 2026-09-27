"""Offline compatibility checks against the built image, using synthetic data."""
import html
import importlib.util
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

root = Path('/app')
for source in root.glob('*.py'):
    compile(source.read_bytes(), str(source), 'exec')
for name in ('entry.sh', 'scheduler.sh'):
    subprocess.run(['/bin/sh', '-n', str(root / name)], check=True)

# Never use deployment credentials, state or remote APIs in this test.
os.environ.update(STATE_DIR='/tmp/reporter-smoke', SMTP_HOST='', ST_API_KEY='',
                  APPRISE_ENABLED='0', TZ='Europe/Berlin')
spec = importlib.util.spec_from_file_location('reporter_smoke', root / 'report.py')
module = importlib.util.module_from_spec(spec)
with patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected network access')):
    spec.loader.exec_module(module)
    label = 'Folder A & B'
    rows = [{'id': 'fixture', 'display': label, 'state': 'idle',
             'globalFiles': 1, 'globalDirectories': 1, 'globalBytes': 1024,
             'needBytes': 0}]
    rendered = module.render_html('test-host', rows, [], {}, {}, 24)
    assert module.tr('section_status') in rendered
    assert html.escape(label) in rendered
    assert label not in rendered
    assert '</table>' in rendered
    errors = [{'folder': label, 'id': 'fixture', 'error': 'Unavailable & retry'}]
    rendered = module.render_html('test-host', rows, errors, {}, {}, 24)
    assert module.tr('section_api_errors') in rendered
    assert 'Unavailable &amp; retry' in rendered
    module.session.close()
print('Reporter syntax, imports and HTML rendering: OK (' + module.REPORT_LANG + ')')
