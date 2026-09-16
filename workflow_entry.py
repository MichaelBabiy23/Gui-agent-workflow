"""Start the Electron editor and its Python workflow runtime."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    desktop = Path(__file__).resolve().parent / "desktop"
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        print("Node.js and npm are required to launch GUI Workflow.", file=sys.stderr)
        return 1

    electron = (
        desktop
        / "node_modules"
        / "electron"
        / "dist"
        / ("electron.exe" if os.name == "nt" else "electron")
    )
    if not electron.exists():
        print("Installing desktop dependencies...")
        result = subprocess.run([npm, "install"], cwd=desktop, check=False)
        if result.returncode:
            return result.returncode

    built_index = desktop / "dist" / "index.html"
    source_files = [
        desktop / "index.html",
        desktop / "package.json",
        desktop / "vite.config.js",
    ]
    source_files.extend(path for path in (desktop / "src").rglob("*") if path.is_file())
    needs_build = not built_index.exists() or any(
        source.stat().st_mtime > built_index.stat().st_mtime for source in source_files
    )
    if needs_build:
        print("Building desktop editor...")
        result = subprocess.run([npm, "run", "build"], cwd=desktop, check=False)
        if result.returncode:
            return result.returncode

    env = os.environ.copy()
    env["GUI_WORKFLOW_PYTHON"] = sys.executable
    return subprocess.run([npm, "start"], cwd=desktop, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
