"""Logged native control client and editable lettering helpers."""
import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path

from .project import event, inside, load, now, read_json, write_json
from .runtime import SETUP_FILE

LOG = logging.getLogger(__name__)


class Client:
    def __init__(self, project, port=None):
        self.project = Path(project).resolve()
        state = read_json(self.project / "state.json")
        self.port = port or state.get("vectorcraft", {}).get("port")
        if not self.port:
            raise ValueError("Launch this project's VectorCraft instance first")
        self.sequence = 0

    def call(self, method, params=None):
        self.sequence += 1
        request = {"id":self.sequence, "method":method, "params":params or {}}
        LOG.debug("VectorCraft %s", method)
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=10) as connection:
                connection.settimeout(120)
                connection.sendall((json.dumps(request, ensure_ascii=False)+"\n").encode())
                line = connection.makefile("rb").readline(64 * 1024 * 1024)
                response = json.loads(line)
        except OSError as error:
            raise ConnectionError("VectorCraft is not reachable. Preserve files and relaunch this project instance.") from error
        log = self.project / "logs" / "vectorcraft-commands.jsonl"
        with log.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"at":now(), "request":request, "response":response}, ensure_ascii=False)+"\n")
        if not response.get("ok"):
            raise RuntimeError(response.get("error", response))
        return response["result"]

    def execute(self, command, **params):
        return self.call("engine.execute", {"command":command, "params":params})

    def open(self, path):
        """Reuse an open tab, including its unsaved edits."""
        path = Path(path).resolve()
        ui = self.call("ui.inspect")
        for index in range(len(ui["documents"])):
            self.execute("document.activate", index=index)
            document = self.execute("document.inspect")
            if document.get("path") and Path(document["path"]).resolve() == path:
                return {"index":index, "document":document}
        opened = self.execute("document.open", path=str(path))
        if opened.get("warnings") or opened.get("missingLinks"):
            raise RuntimeError(f"Resolve import warnings before continuing: {opened}")
        return {"index":opened["index"], "document":self.execute("document.inspect")}

    def save(self, path):
        result = self.execute("document.save", path=str(Path(path).resolve()), compress=False, preview=True)
        if result.get("warnings"):
            raise RuntimeError(result["warnings"])
        return result

    def export(self, path, background="transparent", ppi=72):
        result = self.execute("document.export", path=str(Path(path).resolve()), format="png",
                              artboard=0, ppi=ppi, background=background, embedIcc=True)
        if result.get("warnings"):
            raise RuntimeError(result["warnings"])
        return result

    def fonts(self):
        fonts = self.execute("text.fonts")
        if any(f.get("status") != "exact" or f.get("missing") or f.get("missingGlyphs") for f in fonts):
            raise ValueError(f"Font substitution or missing glyphs must be resolved: {fonts}")
        return fonts

    def phrase(self, text, *, x, y, size, font, fill, inner="#493327", outer="#FFFFFF",
               inner_width=2.8, outer_width=7.4, style="Regular", angle=0, bend=0, vertical=False):
        """Build one movable phrase with editable face and outline text objects."""
        ids = []
        for name, color, weight in (("外側のフチ",outer,outer_width), ("内側のフチ",inner,inner_width), ("文字",fill,0)):
            oid = self.execute("text.create", x=x, y=y, text=text, size=size, font=font,
                               style=style, color=color, justify="center", vertical=vertical,
                               leadingModel="romanBaseline", charAlign="romanBaseline")["id"]
            self.execute("object.setProps", id=oid, name=name)
            self.execute("paint.setStroke", id=oid, **({"color":color} if weight else {"none":True}))
            if weight:
                self.execute("stroke.set", id=oid, weight=weight, join="round", cap="round", align="center")
            if bend:
                self.execute("effect.apply", ids=[oid], effect="path.outlineObject", params={})
                self.execute("effect.apply", ids=[oid], effect="warp.arc", params={
                    "bend":bend, "orientation":"vertical" if vertical else "horizontal", "horizontal":0, "vertical":0})
            if angle:
                self.execute("object.rotate", ids=[oid], angle=angle, origin=[x,y])
            ids.append(oid)
        group = self.execute("object.group", ids=ids)["id"]
        self.execute("object.setProps", id=group, name=text)
        return group


def launch(project, executable=None, port=None):
    root, manifest, state = load(project)
    previous = state.get("vectorcraft", {}).get("port")
    if previous:
        try:
            ui = Client(root, previous).call("ui.inspect")
            LOG.info("Reusing the project's running VectorCraft instance")
            return {"port":previous, "running":True, "documents":len(ui["documents"])}
        except ConnectionError:
            LOG.info("Previous instance is closed; starting a new one")
    executable = Path(executable or read_json(SETUP_FILE)["vectorcraft"]).expanduser().resolve()
    if port is None:
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
    environment = os.environ.copy()
    environment["VECTORCRAFT_CONFIG_DIR"] = str(root / "production" / "vectorcraft-profile")
    if __import__("platform").system() == "Linux" and "microsoft" in __import__("platform").release().lower():
        # XWayland keeps the WSLg desktop workflow consistent with manual file opening.
        environment["WAYLAND_DISPLAY"] = ""
    arguments = [str(executable), "--control", str(port), "--automation-read-root", str(root),
                 "--automation-write-root", str(root)]
    with (root / "logs" / "vectorcraft-process.log").open("ab") as output:
        child = subprocess.Popen(arguments, env=environment, stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=os.name != "nt",
                                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    state["vectorcraft"] = {"port":port, "pid":child.pid, "executable":str(executable), "started_at":now()}
    write_json(root / "state.json", state)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f"VectorCraft exited; inspect {root / 'logs/vectorcraft-process.log'}")
        try:
            Client(root, port).call("ui.inspect")
            event(root, state, "vectorcraft_started", port=port)
            return {"port":port, "pid":child.pid, "running":True}
        except ConnectionError:
            time.sleep(0.2)
    raise TimeoutError("VectorCraft did not become ready. Inspect its process log and desktop display.")


def review_open(project, item_ids):
    root, manifest, state = load(project)
    client = Client(root)
    result = []
    for item_id in item_ids:
        path = inside(root, state["items"][item_id]["native"])
        opened = client.open(path)
        client.execute("view.fitArtboard")
        result.append({"id":item_id, "tab":opened["index"], "path":str(path)})
    client.call("ui.focus")
    return result


def review_complete(project, item_ids, human_message):
    from .project import approve_review
    root, manifest, state = load(project)
    client = Client(root)
    for item_id in item_ids:
        path = inside(root, state["items"][item_id]["native"])
        opened = client.open(path)
        client.fonts()
        if opened["document"]["dirty"]:
            LOG.info("Saving the user's edits for %s", item_id)
            client.save(path)
    approve_review(root, item_ids, human_message)
