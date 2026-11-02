"""Package public source with an allowlist, excluding every user's work folder."""
import argparse
import logging
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sticker_studio.source_package import build


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output or root / "dist" / "line-normal-sticker-creator-for-codex-source.zip"
    logging.info("START Build public source archive")
    result = build(root, output)
    with zipfile.ZipFile(result) as archive:
        count = len(archive.namelist())
    logging.info("END %s, %d source files", result, count)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("ERROR Source packaging failed")
        raise
