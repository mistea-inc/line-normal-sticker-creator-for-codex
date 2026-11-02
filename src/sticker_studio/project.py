"""Project files, provenance, review state, and portable path handling."""
import hashlib
import json
import logging
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger(__name__)
ALLOWED_COUNTS = (8, 16, 24, 32, 40)
KINDS = ("main", "tab")


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"Path must stay inside the project: {relative}")
    return path


@contextmanager
def lock(root):
    """The OS releases this lock even if a command crashes."""
    path = Path(root) / ".studio.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if __import__("os").name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if __import__("os").name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def init_project(root, name, phrases, review_batch_size=4):
    root = Path(root).resolve()
    if not isinstance(phrases, list) or len(phrases) not in ALLOWED_COUNTS:
        raise ValueError(f"Select a supported sticker count: {ALLOWED_COUNTS}")
    if not name.strip() or any(not isinstance(p, str) or not p.strip() for p in phrases):
        raise ValueError("Project name and every phrase must be nonempty")
    if review_batch_size < 1:
        raise ValueError("Review batch size must be positive")
    if (root / "project.json").exists():
        raise FileExistsError("Project already exists; resume it instead")
    for directory in ("references", "artwork", "designs", "production", "review", "output", "logs"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    items = [{"id":f"{i:02}", "phrase":phrase, "emotion":None, "pose":None,
              "composition":None, "tags":[]} for i, phrase in enumerate(phrases, 1)]
    items.extend({"id":kind, "phrase":None, "tags":[]} for kind in KINDS)
    write_json(root / "project.json", {
        "schema_version":1, "name":name, "created_at":now(),
        "title":{}, "description":{}, "character":{}, "design_direction":{},
        "review_batch_size":review_batch_size, "references":[], "items":items,
        "specification":{"source":"https://creator.line.me/ja/guideline/sticker/",
                         "confirmed_on":None},
        "image_generation":{"provider":"Codex built-in tool", "availability_checked":False},
    })
    write_json(root / "state.json", {"schema_version":1, "items":{}, "review_batches":[], "events":[]})
    LOG.info("Initialized %s with %d stickers", root, len(phrases))
    return root


def load(root):
    root = Path(root).resolve()
    manifest = read_json(root / "project.json")
    stickers = [item for item in manifest["items"] if item["id"] not in KINDS]
    expected = [f"{i:02}" for i in range(1, len(stickers)+1)] + list(KINDS)
    if len(stickers) not in ALLOWED_COUNTS or [item["id"] for item in manifest["items"]] != expected:
        raise ValueError("Keep consecutive sticker IDs followed by main and tab, with a supported count")
    if any(not isinstance(item.get("phrase"), str) or not item["phrase"].strip() for item in stickers):
        raise ValueError("Every sticker must have its agreed phrase")
    return root, manifest, read_json(root / "state.json")


def plan_digest(manifest, item_id):
    item = get_item(manifest, item_id)
    rendered_intent = {"item":{key:item.get(key) for key in ("id", "phrase", "emotion", "pose", "composition")},
                       "character":manifest["character"], "references":manifest["references"],
                       "direction":manifest["design_direction"]}
    return hashlib.sha256(json.dumps(rendered_intent, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def get_item(manifest, item_id):
    return next(item for item in manifest["items"] if item["id"] == item_id)


def event(root, state, action, **details):
    state["events"].append({"at":now(), "action":action, **details})
    write_json(Path(root) / "state.json", state)
    LOG.info("%s %s", action, details)


def add_image(root, source, item_id=None):
    from PIL import Image
    root, manifest, state = load(root)
    source = Path(source).resolve()
    with Image.open(source) as image:
        image.verify()
    if source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Use PNG, JPEG or WebP reference images; generated artwork must be PNG")
    if item_id is None:
        target = root / "references" / f"{digest(source)[:12]}{source.suffix.lower()}"
        if target.exists():
            if digest(target) != digest(source):
                raise RuntimeError("Reference filename collision")
        else:
            shutil.copy2(source, target)
        entry = {"path":target.relative_to(root).as_posix(), "sha256":digest(target)}
        if entry not in manifest["references"]:
            manifest["references"].append(entry)
            write_json(root / "project.json", manifest)
        event(root, state, "reference_added", path=entry["path"])
    else:
        get_item(manifest, item_id)
        with Image.open(source) as image:
            if image.format != "PNG" or image.mode != "RGBA" or image.getchannel("A").getextrema()[0] != 0:
                raise ValueError("Artwork must be a PNG with RGB colors and a transparent alpha channel")
        # Revisions are preserved; replacing artwork invalidates downstream approvals.
        target = root / "artwork" / f"{item_id}-{digest(source)[:12]}.png"
        if target.exists() and digest(target) != digest(source):
            raise ValueError("A registered artwork revision was modified; preserve and inspect it")
        if not target.exists():
            shutil.copy2(source, target)
        old = state["items"].get(item_id, {})
        if old.get("artwork_sha256") == digest(source) and old.get("artwork") == target.relative_to(root).as_posix():
            LOG.info("Artwork %s is already registered; preserving its review state", item_id)
            return
        state["items"][item_id] = {"id":item_id, "artwork":target.relative_to(root).as_posix(),
                                   "artwork_sha256":digest(target),
                                   "superseded_native":old.get("native"), "updated_at":now()}
        event(root, state, "artwork_added", item_id=item_id, path=str(target.relative_to(root)))


def register_native(root, item_id, native):
    root, manifest, state = load(root)
    get_item(manifest, item_id)
    native = Path(native).resolve()
    if not native.is_relative_to(root) or native.suffix != ".vectorcraft":
        raise ValueError("Native design must be a .vectorcraft file inside this project")
    current = state["items"].setdefault(item_id, {})
    if current.get("native") == native.relative_to(root).as_posix() and current.get("native_sha256") == digest(native):
        LOG.info("Native design %s is unchanged; preserving its review state", item_id)
        return
    current.update({"id":item_id, "native":native.relative_to(root).as_posix(), "native_sha256":digest(native)})
    for key in ("review", "export", "visual"):
        current.pop(key, None)
    event(root, state, "native_registered", item_id=item_id)


def approve_review(root, item_ids, human_message):
    root, manifest, state = load(root)
    if not human_message.strip():
        raise ValueError("Record the actual user message approving the review")
    for item_id in item_ids:
        get_item(manifest, item_id)
        current = state["items"][item_id]
        native = inside(root, current["native"])
        current["native_sha256"] = digest(native)
        current["review"] = {"at":now(), "human_message":human_message,
                              "native_sha256":digest(native), "plan_sha256":plan_digest(manifest, item_id)}
        current.pop("export", None)
        current.pop("visual", None)
    state["review_batches"].append({"ids":item_ids, "message":human_message, "at":now()})
    event(root, state, "human_review_complete", ids=item_ids)


def require_review(root, current):
    if not current.get("native"):
        raise ValueError("Create and register the native design before review or export")
    native = inside(root, current["native"])
    if current.get("review", {}).get("native_sha256") != digest(native):
        raise ValueError(f"Review is missing or the native file changed: {native.name}")
    manifest = read_json(Path(root) / "project.json")
    if current["review"].get("plan_sha256") != plan_digest(manifest, current["id"]):
        raise ValueError("The phrase, reference or design direction changed after review")
    return native
