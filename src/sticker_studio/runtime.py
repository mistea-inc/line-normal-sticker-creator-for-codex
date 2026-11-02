"""Find or install official portable VectorCraft builds on desktop platforms."""
import hashlib
import ctypes
import logging
import os
import platform
import plistlib
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .project import read_json, write_json

LOG = logging.getLogger(__name__)
REPOSITORY = "storytold/vectorcraft"
VERSION = "0.19.0"
REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_FILE = REPO_ROOT / ".runtime" / "setup.json"


def target(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    arch = {"amd64":"x86_64", "x64":"x86_64", "arm64":"aarch64"}.get(machine, machine)
    if system == "Windows" and arch in ("x86_64", "aarch64"):
        name = "x64" if arch == "x86_64" else "arm64"
        return f"vectorcraft-{VERSION}-windows-{name}-portable.zip"
    if system == "Darwin" and arch in ("x86_64", "aarch64"):
        return f"vectorcraft-{VERSION}-macos-universal.dmg"
    if system == "Linux" and arch in ("x86_64", "aarch64"):
        return f"vectorcraft-{VERSION}-linux-{arch}.tar.gz"
    raise ValueError(f"No supported portable build for {system}/{machine}")


def fetch(url, destination):
    if not url.startswith("https://"):
        raise ValueError("Downloads must use HTTPS")
    LOG.info("Downloading %s", url)
    request = urllib.request.Request(url, headers={"User-Agent":"line-sticker-studio/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response, Path(destination).open("wb") as output:
        if not response.url.startswith("https://"):
            raise ValueError("Refusing a non-HTTPS redirect")
        shutil.copyfileobj(response, output)


def safe_extract(archive, destination):
    """Portable release archives must not write outside their staging directory."""
    destination = Path(destination).resolve()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                relative = member.filename.replace("\\", "/")
                path = (destination / relative).resolve()
                if not path.is_relative_to(destination) or ":" in relative:
                    raise ValueError("Unsafe archive member")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Archive symlinks are not supported")
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                path = (destination / member.name).resolve()
                if not path.is_relative_to(destination) or not (member.isfile() or member.isdir()):
                    raise ValueError("Unsafe archive member")
            # Members have been checked individually; preserve executable permissions.
            if hasattr(tarfile, "data_filter"):
                bundle.extractall(destination, filter="data")
            else:
                bundle.extractall(destination)


def find_binary(root):
    root = Path(root)
    names = ("vectorcraft.exe", "vectorcraft", "VectorCraft")
    candidates = [p for p in root.rglob("*") if p.is_file() and p.name in names]
    if not candidates:
        raise FileNotFoundError(f"VectorCraft executable not found in {root}")
    # Prefer the app over any helper executable inside an archive.
    return min(candidates, key=lambda p:len(p.parts)).resolve()


def checksum_for(text, filename):
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == filename and len(fields[0]) == 64:
            return fields[0].lower()
    raise ValueError(f"Official checksum is missing for {filename}")


def install(tools_dir, from_source=False):
    tools_dir = Path(tools_dir).expanduser().resolve()
    tools_dir.mkdir(parents=True, exist_ok=True)
    asset = target()
    destination = tools_dir / f"vectorcraft-{VERSION}" / asset.replace(".tar.gz", "").replace(".zip", "").replace(".dmg", "")
    if from_source:
        source = tools_dir / f"vectorcraft-source-{VERSION}"
        if source.exists():
            raise FileExistsError(f"Reuse or inspect the existing checkout: {source}")
        for tool in ("git", "cargo"):
            if not shutil.which(tool):
                raise FileNotFoundError(f"Source installation requires {tool}; see upstream build documentation")
        subprocess.run(["git", "clone", "--depth", "1", "--branch", f"v{VERSION}",
                        f"https://github.com/{REPOSITORY}", str(source)], check=True)
        subprocess.run(["cargo", "build", "--release", "--locked", "-p", "vectorcraft"], cwd=source, check=True)
        return find_binary(source / "target" / "release")
    if (destination / "installed.json").exists():
        return find_binary(destination)
    if destination.exists():
        raise FileExistsError(f"An incomplete installation exists; inspect it before retrying: {destination}")
    base = f"https://github.com/{REPOSITORY}/releases/download/v{VERSION}"
    with tempfile.TemporaryDirectory(prefix="sticker-vectorcraft-", dir=tools_dir) as temporary:
        stage = Path(temporary)
        checksums = stage / "SHA256SUMS.txt"
        fetch(f"{base}/SHA256SUMS.txt", checksums)
        expected = checksum_for(checksums.read_text(encoding="utf-8"), asset)
        download = stage / asset
        fetch(f"{base}/{asset}", download)
        with download.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("VectorCraft archive checksum mismatch; installation stopped")
        unpacked = stage / "unpacked"
        unpacked.mkdir()
        if asset.endswith(".dmg"):
            # hdiutil is built into macOS; installing a private copy needs no administrator.
            mounted = subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(download)],
                                     check=True, capture_output=True)
            entities = plistlib.loads(mounted.stdout)["system-entities"]
            mounts = [Path(e["mount-point"]) for e in entities if e.get("mount-point")]
            if not mounts:
                raise RuntimeError("The official disk image did not mount")
            try:
                apps = [p for mount in mounts for p in mount.glob("*.app")]
                if len(apps) != 1:
                    raise RuntimeError("Expected exactly one app in the official disk image")
                subprocess.run(["ditto", str(apps[0]), str(unpacked / apps[0].name)], check=True)
            finally:
                for mount in reversed(mounts):
                    subprocess.run(["hdiutil", "detach", str(mount)], check=True)
        else:
            safe_extract(download, unpacked)
        find_binary(unpacked)
        write_json(unpacked / "installed.json", {"repository":REPOSITORY, "version":VERSION,
                                                  "asset":asset, "sha256":actual})
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(unpacked), str(destination))
    return find_binary(destination)


def setup(vectorcraft=None, tools_dir=None, from_source=False, no_download=False):
    tools_dir = Path(tools_dir or os.environ.get("LINE_STICKER_TOOLS_DIR") or Path.home()/"ai-base"/"tools"/"line-sticker-studio")
    if vectorcraft and from_source:
        raise ValueError("Select either an existing executable or a source build")
    existing = None if from_source else vectorcraft or os.environ.get("VECTORCRAFT_BIN") or shutil.which("vectorcraft")
    if not existing and not from_source and SETUP_FILE.exists():
        previous = read_json(SETUP_FILE).get("vectorcraft")
        if previous and Path(previous).is_file():
            existing = previous
    if existing:
        executable = Path(existing).expanduser().resolve()
        if not executable.is_file():
            raise FileNotFoundError(executable)
        LOG.info("Reusing VectorCraft: %s", executable)
    elif no_download:
        raise FileNotFoundError("VectorCraft not found. Provide --vectorcraft or allow an official download")
    else:
        executable = install(tools_dir, from_source=from_source)
    data = {"vectorcraft":str(executable), "tools_dir":str(tools_dir.resolve()),
            "platform":platform.platform(), "pinned_release":VERSION,
            "linux_runtime_libraries":linux_libraries(),
            "note":"Confirm the desktop display, save, reopen and PNG export before production"}
    write_json(SETUP_FILE, data)
    return data


def linux_libraries():
    if platform.system() != "Linux":
        return {}
    result = {}
    for name in ("libxkbcommon.so.0", "libxkbcommon-x11.so.0", "libX11.so.6", "libEGL.so.1"):
        try:
            ctypes.CDLL(name)
            result[name] = "available"
        except OSError:
            result[name] = "missing; check OS packages or the selected launcher environment"
    return result
