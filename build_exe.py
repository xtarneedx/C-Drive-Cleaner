"""Build the localized Windows executable using the current Windows Python."""
import argparse
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent


def build_exe(dist_dir=None, work_dir=None):
    if sys.platform != 'win32':
        raise RuntimeError('Use Windows Python to build a Windows EXE (native Windows or Wine).')
    dist = Path(dist_dir or ROOT / 'dist').resolve()
    work = Path(work_dir or ROOT / 'build').resolve()
    dist.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, '-m', 'PyInstaller',
        '--name=CDriveCleaner', '--windowed', '--onefile',
        '--icon=' + str(ROOT / 'icons' / 'cleaner.ico'),
        '--add-data=' + str(ROOT / 'icons') + ';icons',
        '--add-data=' + str(ROOT / 'locales') + ';locales',
        '--distpath=' + str(dist), '--workpath=' + str(work),
        '--specpath=' + str(work), '--noconfirm', '--clean',
        str(ROOT / 'main.py'),
    ]
    subprocess.run(command, cwd=str(ROOT), check=True)
    executable = dist / 'CDriveCleaner.exe'
    if not executable.is_file() or executable.stat().st_size == 0:
        raise RuntimeError('PyInstaller did not produce the expected executable')
    archive = dist / 'CDriveCleaner-Windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(executable, executable.name)
        bundle.write(ROOT / 'START_HERE_AR.txt', 'START_HERE_AR.txt')
        bundle.write(ROOT / 'README_AR.md', 'README_AR.md')
        bundle.write(ROOT / 'I18N.md', 'I18N.md')
        bundle.write(ROOT / 'LICENSE', 'LICENSE')
    print('Executable:', executable)
    print('Portable ZIP:', archive)
    return executable


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir')
    parser.add_argument('--work-dir')
    args = parser.parse_args()
    build_exe(args.dist_dir, args.work_dir)
