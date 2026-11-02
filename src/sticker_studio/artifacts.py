"""Export reviewed documents and verify upload artifacts without raster editing."""
import hashlib
import io
import logging
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image

from .project import digest, event, inside, load, now, require_review, write_json
from .vectorcraft import Client

LOG = logging.getLogger(__name__)
GUIDELINE = "https://creator.line.me/ja/guideline/sticker/"
TAG_GUIDE = "https://note.com/line_cm/n/n846009d35f27"
SNAPSHOT_DATE = "2026-10-31"


def inspect_png(data, item_id):
    """Mechanical checks supplement the required rendered visual inspection."""
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        width, height = image.size
        alpha = image.getchannel("A") if image.mode == "RGBA" else None
        dpi = image.info.get("dpi")
        edges = [(0,0,width,10), (0,height-10,width,height),
                 (0,0,10,height), (width-10,0,width,height)]
        required = {"main":(240,240), "tab":(96,74)}.get(item_id)
        checks = {
            "png":image.format == "PNG",
            "rgb_with_alpha":image.mode == "RGBA",
            "dimensions":image.size == required if required else 0 < width <= 370 and 0 < height <= 320,
            "even_dimensions":width % 2 == 0 and height % 2 == 0,
            "under_1mb":len(data) <= 1_000_000,
            "dpi_at_least_72":bool(dpi) and min(dpi) >= 71.99,
            "transparent_background":alpha is not None and alpha.getextrema()[0] == 0,
            "transparent_10px_margin":alpha is not None and all(alpha.crop(edge).getextrema() == (0,0) for edge in edges),
            "nonempty_content":alpha is not None and alpha.getbbox() is not None,
        }
        return {"size":[width,height], "bytes":len(data),
                "sha256":hashlib.sha256(data).hexdigest(), "checks":checks,
                "alpha_bounds":alpha.getbbox() if alpha else None, "dpi":dpi}


def ensure_active(client, native):
    document = client.execute("document.inspect")
    if not document.get("path") or Path(document["path"]).resolve() != native.resolve() or document["dirty"]:
        raise ValueError("The active document changed or has unsaved edits. Save and review before exporting")


def export_reviewed(project, item_ids):
    root, manifest, state = load(project)
    client = Client(root)
    results = []
    for item_id in item_ids:
        current = state["items"][item_id]
        native = require_review(root, current)
        before = digest(native)
        client.open(native)
        ensure_active(client, native)
        client.fonts()
        output = root / "output" / f"{item_id}.png"
        client.export(output)
        for suffix, background in (("light","white"), ("dark","#243448")):
            ensure_active(client, native)
            client.export(root / "review" / f"{item_id}-{suffix}.png", background)
        ensure_active(client, native)
        if digest(native) != before:
            raise ValueError("Reviewed native file changed during export")
        technical = inspect_png(output.read_bytes(), item_id)
        current["export"] = {"at":now(), "native_sha256":before, "sha256":technical["sha256"],
                              "path":output.relative_to(root).as_posix(), "technical":technical}
        current.pop("visual", None)
        event(root, state, "png_exported", item_id=item_id, checks=technical["checks"])
        results.append({"id":item_id, **technical})
    return results


def record_visual(project, item_ids, note, backgrounds):
    root, manifest, state = load(project)
    if not note.strip() or not {"light","dark"}.issubset(backgrounds):
        raise ValueError("Record the actual visual findings after checking light and dark backgrounds")
    for item_id in item_ids:
        current = state["items"][item_id]
        require_review(root, current)
        output = inside(root, current["export"]["path"])
        if digest(output) != current["export"]["sha256"]:
            raise ValueError("PNG changed after export; repeat export and inspection")
        current["visual"] = {"sha256":digest(output), "at":now(), "note":note, "backgrounds":backgrounds}
    event(root, state, "visual_inspection_recorded", ids=item_ids)


def validate_project(root):
    root, manifest, state = load(root)
    for reference in manifest["references"]:
        if digest(inside(root, reference["path"])) != reference["sha256"]:
            raise ValueError("A character reference was modified; resolve provenance before delivery")
    if not manifest["references"]:
        raise ValueError("Register and inspect at least one character reference")
    if not manifest["character"] or not manifest["design_direction"]:
        raise ValueError("Record the character invariants and agreed design direction")
    if not manifest.get("image_generation", {}).get("availability_checked"):
        raise ValueError("Record the availability of the Codex image-generation tool")
    confirmation = manifest.get("specification", {}).get("confirmed_on")
    if not confirmation or date.fromisoformat(confirmation) > date.today():
        raise ValueError("Codex must check the current official LINE specification and record its confirmation date")
    if manifest["specification"].get("source") != GUIDELINE:
        raise ValueError("Keep the official LINE guideline as the specification source")
    results = []
    for item in manifest["items"]:
        item_id = item["id"]
        current = state["items"].get(item_id, {})
        native = require_review(root, current)
        if current.get("artwork") and digest(inside(root, current["artwork"])) != current["artwork_sha256"]:
            raise ValueError(f"Registered artwork changed: {item_id}")
        exported = current.get("export", {})
        if exported.get("native_sha256") != digest(native):
            raise ValueError(f"Export does not match the reviewed native file: {item_id}")
        output = inside(root, exported["path"])
        technical = inspect_png(output.read_bytes(), item_id)
        if technical["sha256"] != exported.get("sha256"):
            raise ValueError(f"PNG modified after export: {item_id}")
        if not all(technical["checks"].values()):
            raise ValueError(f"PNG specifications failed for {item_id}: {technical['checks']}")
        if output.stat().st_mtime_ns < native.stat().st_mtime_ns:
            raise ValueError(f"Native file is newer than PNG: {item_id}")
        visual = current.get("visual", {})
        if visual.get("sha256") != technical["sha256"] or not {"light","dark"}.issubset(visual.get("backgrounds", [])):
            raise ValueError(f"Inspect the final rendered PNG on light and dark backgrounds: {item_id}")
        if item_id.isdigit():
            if any(not item.get(key) for key in ("emotion", "pose", "composition")):
                raise ValueError(f"Complete the per-sticker design plan: {item_id}")
            tags = item.get("tags", [])
            if not 1 <= len(tags) <= 9 or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
                raise ValueError(f"Prepare 1–9 relevant tag search candidates for {item_id}")
        results.append({"id":item_id, "phrase":item["phrase"], **technical})
    return results


def write_tags(project):
    root, manifest, state = load(project)
    lines = [manifest["name"], "スタンプごとのタグ検索候補", "",
             "登録画面のタグ候補から、意味が合うものを選んでください。",
             "候補一覧との一致は未確認です。タグは1点につき最大9個です。",
             "このテキストは設定用の手元資料です。画像ZIPへ含めて自動登録する形式ではありません。", ""]
    for item in manifest["items"]:
        if not item["id"].isdigit():
            continue
        lines.extend([f"{item['id']}.png　{item['phrase']}", " / ".join(item.get("tags", [])) or "未設定", ""])
    lines.extend(["設定方法の確認元", TAG_GUIDE, ""])
    path = root / "output" / "tags.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    LOG.info("Tag search text written: %s", path)
    return path


def package(project):
    root, manifest, state = load(project)
    images = validate_project(root)
    expected = [f"{item['id']}.png" for item in manifest["items"]]
    archive = root / "output" / "upload.zip"
    temporary = archive.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for filename in expected:
                bundle.write(root / "output" / filename, arcname=filename)
        with zipfile.ZipFile(temporary) as bundle:
            if bundle.namelist() != expected or bundle.testzip() is not None:
                raise ValueError("Archive filename or CRC check failed")
            for image in images:
                data = bundle.read(f"{image['id']}.png")
                if hashlib.sha256(data).hexdigest() != image["sha256"]:
                    raise ValueError("Archive contents differ from the verified PNGs")
        if temporary.stat().st_size > 60_000_000:
            raise ValueError("Upload ZIP exceeds 60 MB")
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    tags = write_tags(root)
    report = {"at":now(), "official_specification":manifest["specification"],
              "implementation_specification_snapshot":SNAPSHOT_DATE,
              "images":images, "zip":{"path":"output/upload.zip", "bytes":archive.stat().st_size,
                                       "sha256":digest(archive), "entries":expected},
              "tags":{"path":"output/tags.txt", "catalog_match":"unverified search candidates"},
              "external_upload":"not performed"}
    write_json(root / "production" / "verification.json", report)
    event(root, state, "upload_package_created", sha256=digest(archive))
    return {"zip":str(archive), "tags":str(tags), "files":len(images), "bytes":archive.stat().st_size}
