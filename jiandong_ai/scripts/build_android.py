"""Build with D: caches, concrete exclusions and native hooks after Flet refresh."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tomllib
import subprocess
import hashlib


def packaging_exclusions(root: Path, patterns: list[str]) -> list[str]:
    # serious_python treats --exclude values as paths, not wildcard patterns.
    paths = []
    for pattern in patterns:
        matches = list(root.glob(pattern)) if any(c in pattern for c in '*?[') else []
        paths.extend(str(p.relative_to(root)) for p in matches)
        if not matches and not any(c in pattern for c in '*?['):
            paths.append(pattern)
    return list(dict.fromkeys(paths))


def sanitize_staging(root: Path, exclusions: list[str]) -> None:
    stage = (root / 'build/python-app').resolve()
    if not (stage / 'main.pyc').exists():
        raise RuntimeError('No previously packaged application is available.')
    for relative in exclusions:
        target = (stage / relative).resolve()
        if not target.is_relative_to(stage) or target == stage:
            raise ValueError(f'Unsafe staging exclusion: {relative}')
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def main() -> None:
    # Windows redirected output otherwise keeps the startup GBK codec even
    # after PYTHONIOENCODING is set for child processes below.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    root = Path(__file__).resolve().parents[2]
    if root.drive.upper() != 'D:':
        raise RuntimeError('This project must be built on D: as requested.')
    cache = root / '.speech-cache'
    old_pub = Path(os.environ.get('LOCALAPPDATA', 'C:/Users/26429/AppData/Local')) / 'Pub/Cache'
    pub = cache / 'pub'
    for part in ('hosted', 'hosted-hashes'):
        source, target = old_pub / part, pub / part
        if source.exists() and not target.exists():
            shutil.copytree(source, target)
    for key, value in {
        'TEMP': cache / 'tmp', 'TMP': cache / 'tmp',
        'APPDATA': cache / 'appdata', 'LOCALAPPDATA': cache / 'localappdata',
        'PUB_CACHE': pub, 'PIP_CACHE_DIR': cache / 'pip',
        'FLET_CACHE_DIR': Path('D:/dev/.flet/cache'),
        'GRADLE_USER_HOME': Path('D:/dev/.gradle'),
        'JAVA_HOME': Path('D:/dev/java/17.0.13+11'),
        'ANDROID_HOME': Path('D:/Android/Sdk'),
    }.items():
        value.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(value)
    os.environ['FLUTTER_SUPPRESS_ANALYTICS'] = 'true'
    os.environ['DART_SUPPRESS_ANALYTICS'] = 'true'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PIP_INDEX_URL'] = 'https://pypi.org/simple'
    os.environ['PIP_NO_CACHE_DIR'] = '1'
    os.environ['PATH'] = 'D:/dev/flutter/3.44.8/bin;' + os.environ['PATH']
    os.chdir(root)
    config = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    exclusions = packaging_exclusions(root, config['tool']['flet']['app']['exclude'])

    if '--native-only' in sys.argv:
        # Reuse a successfully packaged app and its ABI dependencies when only
        # native assets or staging exclusions changed; do not redownload wheels.
        for abi in ('arm64-v8a', 'armeabi-v7a', 'x86_64'):
            if not list((root / 'build/site-packages' / abi).glob('numpy-*.dist-info')):
                raise RuntimeError(f'Missing packaged dependencies for {abi}')
        sanitize_staging(root, exclusions)
        from jiandong_ai.scripts.prepare_android_bridge import main as prepare
        prepare()
        os.environ['SERIOUS_PYTHON_VERSION'] = (root / 'build/.python-version').read_text().strip()
        os.environ['SERIOUS_PYTHON_SITE_PACKAGES'] = str(root / 'build/site-packages')
        os.environ['SERIOUS_PYTHON_APP'] = str(root / 'build/python-app')
        subprocess.run(['D:/dev/flutter/3.44.8/bin/flutter.bat', 'build', 'apk',
                        '--release', '--no-pub', '--suppress-analytics'],
                       cwd=root / 'build/flutter', check=True)
        final_apk = root / 'build/apk/jiandong-ai.apk'
        shutil.copy2(root / 'build/flutter/build/app/outputs/flutter-apk/app-release.apk', final_apk)
        with final_apk.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha1').hexdigest()
        final_apk.with_suffix('.apk.sha1').write_text(digest, encoding='ascii')
        return

    import flet_cli.utils.flutter as flutter_utils
    import flet_cli.commands.flutter_base as flutter_base
    from flet_cli.commands.build_base import BaseBuildCommand

    def sdk_directory(version):
        path = Path('D:/dev/flutter') / str(version)
        if not (path / 'bin/flutter.bat').is_file():
            raise RuntimeError(f'Missing D: Flutter SDK: {path}')
        return str(path)

    flutter_utils.get_flutter_dir = sdk_directory
    flutter_base.get_flutter_dir = sdk_directory
    original_command = BaseBuildCommand._run_flutter_command

    def build_with_native_bridge(command):
        from jiandong_ai.scripts.prepare_android_bridge import main as prepare
        prepare()
        sanitize_staging(root, exclusions)
        return original_command(command)

    BaseBuildCommand._run_flutter_command = build_with_native_bridge
    sys.argv = ['flet', 'build', 'apk', '-v', '--permissions', 'camera',
                '--skip-flutter-doctor', '--yes', '--no-rich-output',
                '--exclude', *exclusions]
    from flet_cli.cli import main as flet_main
    flet_main()


if __name__ == '__main__':
    main()
