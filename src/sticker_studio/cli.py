"""Agent-facing commands; end users interact with Codex in natural language."""
import argparse
import json
import logging
import platform
import sys
from datetime import date
from pathlib import Path

from . import artifacts, project, runtime, vectorcraft

LOG = logging.getLogger(__name__)


def parser():
    result = argparse.ArgumentParser(description="Codex-led LINE sticker production")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    setup = commands.add_parser("setup")
    setup.add_argument("--vectorcraft", type=Path)
    setup.add_argument("--tools-dir", type=Path)
    setup.add_argument("--from-source", action="store_true")
    setup.add_argument("--no-download", action="store_true")
    new = commands.add_parser("new")
    new.add_argument("--project", type=Path, required=True)
    new.add_argument("--name", required=True)
    new.add_argument("--phrases", type=Path, required=True, help="UTF-8 JSON array of approved phrases")
    new.add_argument("--review-batch-size", type=int, default=4)
    for name in ("status", "reference-add", "artwork-add", "native-register", "launch", "native", "screenshot",
                 "review-open", "review-complete", "export", "visual-record", "verify", "package", "tags", "spec-confirm"):
        child = commands.add_parser(name)
        child.add_argument("--project", type=Path, required=True)
        if name in ("reference-add", "artwork-add", "native-register"):
            child.add_argument("--file", type=Path, required=True)
        if name in ("artwork-add", "native-register"):
            child.add_argument("--id", required=True)
        if name in ("review-open", "review-complete", "export", "visual-record"):
            child.add_argument("--ids", nargs="+", required=True)
        if name == "review-complete":
            child.add_argument("--human-message", required=True)
        if name == "launch":
            child.add_argument("--vectorcraft", type=Path)
            child.add_argument("--port", type=int)
        if name == "native":
            child.add_argument("--method", default="engine.execute")
            child.add_argument("--params", type=Path, required=True, help="UTF-8 JSON parameters")
        if name == "screenshot":
            child.add_argument("--file", default="review/vectorcraft-ui.png")
        if name == "visual-record":
            child.add_argument("--note", required=True)
            child.add_argument("--backgrounds", nargs="+", choices=("light", "dark"), required=True)
    return result


def run(args):
    if args.command == "doctor":
        return {"python":sys.version, "platform":platform.platform(), "machine":platform.machine(),
                "vectorcraft_setup":project.read_json(runtime.SETUP_FILE) if runtime.SETUP_FILE.exists() else "not configured",
                "image_generation":"Codex must verify its tool availability; the CLI cannot provision it",
                "linux_runtime_libraries":runtime.linux_libraries(),
                "portable_asset":runtime.target()}
    if args.command == "setup":
        return runtime.setup(args.vectorcraft, args.tools_dir, args.from_source, args.no_download)
    if args.command == "new":
        return {"project":str(project.init_project(args.project, args.name, project.read_json(args.phrases), args.review_batch_size))}
    root = args.project.resolve()
    with project.lock(root):
        if args.command == "status":
            root, manifest, state = project.load(root)
            return {"project":str(root), "name":manifest["name"], "references":manifest["references"],
                    "items":[{"id":item["id"], "phrase":item["phrase"], **state["items"].get(item["id"], {})} for item in manifest["items"]]}
        if args.command == "reference-add":
            project.add_image(root, args.file)
        elif args.command == "artwork-add":
            project.add_image(root, args.file, args.id)
        elif args.command == "native-register":
            project.register_native(root, args.id, args.file)
        elif args.command == "launch":
            return vectorcraft.launch(root, args.vectorcraft, args.port)
        elif args.command == "native":
            return vectorcraft.Client(root).call(args.method, project.read_json(args.params))
        elif args.command == "screenshot":
            path = project.inside(root, args.file)
            path.parent.mkdir(parents=True, exist_ok=True)
            return vectorcraft.Client(root).call("ui.screenshot", {"path":str(path), "data":False})
        elif args.command == "review-open":
            return vectorcraft.review_open(root, args.ids)
        elif args.command == "review-complete":
            vectorcraft.review_complete(root, args.ids, args.human_message)
        elif args.command == "export":
            return artifacts.export_reviewed(root, args.ids)
        elif args.command == "visual-record":
            artifacts.record_visual(root, args.ids, args.note, args.backgrounds)
        elif args.command == "verify":
            return artifacts.validate_project(root)
        elif args.command == "package":
            return artifacts.package(root)
        elif args.command == "tags":
            return {"tags":str(artifacts.write_tags(root))}
        elif args.command == "spec-confirm":
            root, manifest, state = project.load(root)
            manifest["specification"] = {"source":artifacts.GUIDELINE, "confirmed_on":date.today().isoformat()}
            project.write_json(root / "project.json", manifest)
            project.event(root, state, "official_specification_checked")
        return {"ok":True}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    args = parser().parse_args()
    if getattr(args, "project", None) and args.project.exists():
        log_directory = args.project / "logs"
        log_directory.mkdir(exist_ok=True)
        logging.getLogger().addHandler(logging.FileHandler(log_directory / "studio.log", encoding="utf-8"))
    LOG.info("START %s", args.command)
    try:
        result = run(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        LOG.info("END %s", args.command)
    except Exception as error:
        LOG.exception("ERROR %s: %s", args.command, error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
