"""Build .exe using PyInstaller."""
import subprocess
import sys
from pathlib import Path


def build():
    root = Path(__file__).resolve().parent
    main_py = root / "main.py"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--strip",
        "--name", "free-vpn-checker",
        "--distpath", str(root / "dist"),
        "--workpath", str(root / "build"),
        "--specpath", str(root),
        "--hidden-import", "maxminddb",
        "--hidden-import", "maxminddb.reader",
        "--hidden-import", "config",
        "--hidden-import", "downloader",
        "--hidden-import", "tester",
        "--hidden-import", "renamer",
        "--exclude-module", "tkinter",
        "--exclude-module", "unittest",
        "--exclude-module", "test",
        "--exclude-module", "xml",
        "--exclude-module", "html",
        "--exclude-module", "http.server",
        "--exclude-module", "pydoc",
        "--exclude-module", "doctest",
        "--exclude-module", "pdb",
        "--exclude-module", "profile",
        "--exclude-module", "cProfile",
        "--exclude-module", "lib2to3",
        str(main_py),
    ]

    print(f"Building: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(root))
    if result.returncode == 0:
        exe = root / "dist" / "free-vpn-checker.exe"
        size_mb = exe.stat().st_size / (1024 * 1024) if exe.exists() else 0
        print(f"\nBuild successful!")
        print(f"  Output: {exe}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print(f"\nBuild failed with code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    build()
