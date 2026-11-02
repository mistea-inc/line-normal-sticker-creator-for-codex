"""Create a local Python environment; Codex runs this on the user's behalf."""
import argparse
import logging
import os
import subprocess
import sys
import venv
from pathlib import Path


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tools", action="store_true", help="Only prepare Python")
    parser.add_argument("--vectorcraft", type=Path, help="Reuse an existing executable")
    parser.add_argument("--tools-dir", type=Path)
    args = parser.parse_args()
    logging.info("START Bootstrap LINE Normal Sticker Creator for Codex")
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required. Codex must select a compatible Python first.")
    root = Path(__file__).resolve().parents[1]
    (root / "input" / "references").mkdir(parents=True, exist_ok=True)
    environment = root / ".venv"
    executable = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not executable.exists():
        logging.info("Creating isolated Python environment")
        venv.EnvBuilder(with_pip=True).create(environment)
    environment_variables = os.environ.copy()
    environment_variables.setdefault("PIP_CACHE_DIR", str(root / ".runtime" / "pip-cache"))
    environment_variables["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    subprocess.run([str(executable), "-m", "pip", "install", "-r", str(root / "requirements.txt")],
                   env=environment_variables, check=True)
    if not args.skip_tools:
        command = [str(executable), str(root / "scripts/studio.py"), "setup"]
        if args.vectorcraft:
            command.extend(["--vectorcraft", str(args.vectorcraft)])
        if args.tools_dir:
            command.extend(["--tools-dir", str(args.tools_dir)])
        subprocess.run(command, check=True)
    logging.info("END Bootstrap complete; interpreter: %s", executable)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("ERROR Bootstrap failed")
        raise
