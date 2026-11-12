"""Conservative CI routing and first-party script discovery."""
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys

GROUPS = 'rust tmux fonts windows powershell shell python workflow'.split()


def select(paths):
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
        raise ValueError('Expected JSON array of paths')
    chosen = set()
    unknown = []
    for p in paths:
        name = Path(p).name
        if p.endswith('.md') or any(fnmatch.fnmatchcase(name, pattern) for pattern in ('LICENSE', 'LICENSE.*', '*-LICENSE', '*-LICENSE.*')) or name.endswith('-OFL.txt'):
            continue
        if p.startswith('doc/assets/') and Path(p).suffix in {'.gif', '.png', '.svg', '.jpg', '.jpeg', '.webp'}:
            continue
        owned = False
        if p.startswith('.github/') or p == 'codecov.yml':
            chosen.update(GROUPS)
            owned = True
        if p.startswith(('src/', '.cargo/')) or p in {'Cargo.toml', 'Cargo.lock', 'build.rs', 'fonts/pet-cats/animations.tsv'} or p.startswith('rust-toolchain'):
            chosen.update(['rust', 'tmux'])
            owned = True
        if p.startswith('fonts/'):
            chosen.update(['windows', 'powershell'] if p.endswith(('.ps1', '.psm1', '.psd1')) else ['fonts'])
            if p == 'fonts/font-family.txt':
                chosen.add('windows')
            owned = True
        if p.startswith('tests/') or p == 'runcat.tmux':
            chosen.add('tmux')
            owned = True
        if p == '.coveragerc':
            chosen.add('fonts')
            owned = True
        if p.endswith('.py'):
            chosen.add('python')
        if p.endswith('.sh') or p == 'runcat.tmux':
            chosen.add('shell')
        if p.endswith(('.ps1', '.psm1', '.psd1')):
            chosen.add('powershell')
        if not owned:
            unknown.append(p)
            chosen.update(GROUPS)
    result = {g: g in chosen for g in GROUPS}
    result['linux'] = any(result[g] for g in ('rust', 'shell', 'python', 'workflow'))
    return result, unknown


def inventory(kind):
    paths = subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\0')
    result = []
    for p in paths:
        if not p or p.startswith('fonts/vendor/') or not Path(p).is_file():
            continue
        first = Path(p).read_bytes().split(b'\n', 1)[0]
        shebang = first.decode(errors='replace') if first.startswith(b'#!') else ''
        if kind == 'shell' and (p.endswith('.sh') or any(x in shebang for x in ('/bash', '/sh', ' bash', ' sh'))):
            result.append(p)
        if kind == 'python' and (p.endswith('.py') or 'python' in shebang):
            result.append(p)
    return sorted(result)


if __name__ == '__main__':
    if sys.argv[1] == 'select':
        result, unknown = select(json.loads(os.environ.get('CHANGED_FILES', '[]')))
        if os.environ.get('MANUAL') == 'true':
            result = dict.fromkeys(result, True)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key, value in result.items():
                print(f'{key}={str(value).lower()}', file=output)
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            print('Selected checks: ' + json.dumps(result) + '\n\nFallback paths: ' + json.dumps(unknown), file=output)
    else:
        files = inventory(sys.argv[1])
        if files and sys.argv[1] == 'python':
            subprocess.run(['ruff', 'check', '--select', 'E9,F', '--target-version', 'py311', *files], check=True)
        elif files:
            for path in files:
                subprocess.run(['bash', '-n', path], check=True)
            subprocess.run(['shellcheck', *files], check=True)
