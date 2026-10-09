"""Render the full portable application with generic defaults for CodeQL.

Reads config.example.json only. Never imports an operator config, initializes a
database, starts a service, contacts a provider or connects to a radio.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / 'codeql-generated'
MARKER = 'meshcrap-codeql-render-v1'


def prepare():
    # Refuse to recursively replace an unexpected or redirected directory.
    if GENERATED.is_symlink() or GENERATED.resolve().parent != ROOT.resolve():
        raise ValueError('Analysis output must stay inside this checkout')
    marker = GENERATED / '.generated-by'
    if GENERATED.exists() and (not marker.is_file() or marker.read_text(encoding='utf-8') != MARKER):
        raise ValueError('Analysis output already exists without this tool\'s ownership marker')
    GENERATED.mkdir(exist_ok=True)
    marker.write_text(MARKER, encoding='utf-8')
    for name in ('staging', 'runtime', 'installation'):
        child = GENERATED / name
        if child.is_symlink() or child.resolve().parent != GENERATED.resolve():
            raise ValueError('Analysis child must stay inside the generated directory')
        if child.exists():
            shutil.rmtree(child)

    spec = importlib.util.spec_from_file_location('meshcrap_codeql_cli', ROOT / 'meshcrap.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    config = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
    # Validate the published example, never a user's config.json.
    config_path = GENERATED / 'example.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    settings, _ = cli.load_config(config_path)
    staging = GENERATED / 'staging'
    rendered = cli.render(settings, staging)
    runtime = GENERATED / 'runtime'
    shutil.copytree(rendered, runtime, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
    shutil.rmtree(staging)
    source_map = []
    installation = GENERATED / 'installation'
    installation.mkdir()
    # The Python extractor's paths entries must be directories, not root files.
    for name in ('meshcrap.py', 'setup_wizard.py'):
        source = ROOT / name
        target = installation / name
        shutil.copyfile(source, target)
        ast.parse(target.read_text(encoding='utf-8'), filename=target.relative_to(ROOT).as_posix())
        source_map.append({'generated': target.relative_to(ROOT).as_posix(),
                           'source': name,
                           'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    count = 0
    for path in sorted(runtime.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(runtime)
        source = ROOT / 'source' / relative
        if source.is_file():
            source_map.append({'generated': path.relative_to(ROOT).as_posix(),
                               'source': source.relative_to(ROOT).as_posix(),
                               'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=path.relative_to(ROOT).as_posix())
            count += 1
    expected = sum(1 for path in (ROOT / 'source').rglob('*.py') if '__pycache__' not in path.parts)
    if count != expected:
        raise ValueError('Rendered analysis does not cover every application Python module')
    (GENERATED / 'source-map.json').write_text(json.dumps(source_map, indent=2), encoding='utf-8')
    print(f'Prepared all {count} application Python modules and rendered dashboard assets for CodeQL')


if __name__ == '__main__':
    try:
        prepare()
    except (ValueError, OSError) as error:
        print('Analysis preparation failed: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
