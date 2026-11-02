"""Source distribution is separate from a character's upload package."""
import hashlib
import json
import logging
import zipfile
from pathlib import Path, PurePosixPath

ROOT_FOLDER = "line-normal-sticker-creator-for-codex"
ROOT_FILES = {"README.md", "AGENTS.md", "LICENSE", "pyproject.toml", "requirements.txt", ".gitignore", "source-files.json"}
USER_DOCS = {"setup.md", "commands.md", "vectorcraft.md", "workflow.md", "workflow.html", "registration.md", "registration.html"}
USER_SCRIPTS = {"bootstrap.py", "studio.py", "build_source_zip.py"}


def public_manifest(root):
    data = json.loads((root/'source-files.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or data.get('root_folder') != ROOT_FOLDER:
        raise ValueError('Invalid public source manifest')
    names = data['files']
    if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
        raise ValueError('Public source paths must be strings')
    if len(names) != len(set(names)) or 'source-files.json' not in names:
        raise ValueError('Keep a unique public file list including its own manifest')
    for name in names:
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
            raise ValueError('Public source paths must stay inside the repository')
        parts = relative.parts
        allowed = (name in ROOT_FILES
                   or name in {'input/references/.gitkeep', 'input/references/README.md',
                               '.agents/skills/line-sticker-production/SKILL.md'}
                   or len(parts) == 3 and parts[:2] == ('src', 'sticker_studio') and relative.suffix == '.py'
                   or len(parts) == 2 and parts[0] == 'scripts' and parts[1] in USER_SCRIPTS
                   or len(parts) == 2 and parts[0] == 'docs' and parts[1] in USER_DOCS
                   or len(parts) == 4 and parts[:3] == ('docs', 'assets', 'registration') and relative.suffix == '.png'
                   or parts[:3] == ('docs', 'assets', 'workflow'))
        if not allowed:
            raise ValueError(f'File is not public product source: {name}')
    return names


def workflow_assets(root):
    """Only package the finished media explicitly recorded in the public manifest."""
    base = root/'docs/assets/workflow'
    manifest = base/'manifest.json'
    if not manifest.is_file():
        return set()
    allowed = {'docs/assets/workflow/manifest.json'}
    for item in json.loads(manifest.read_text(encoding='utf-8'))['clips']:
        for key, hash_key in (('gif', 'sha256'), ('poster', 'poster_sha256')):
            relative = PurePosixPath(item[key])
            correct_name = (len(relative.parts) == 1 and relative.name.startswith(item['id']+'_')
                            and relative.suffix == '.gif') if key == 'gif' else (
                            relative.parts == ('posters', item['id']+'.jpg'))
            if not correct_name or relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Workflow media path is invalid')
            path = base/relative
            if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
                raise ValueError('Workflow media must stay inside its asset folder')
            with path.open('rb') as handle:
                actual = hashlib.file_digest(handle, 'sha256').hexdigest()
            if actual != item[hash_key]:
                raise ValueError(f'Workflow media modified: {relative}')
            allowed.add(path.relative_to(root).as_posix())
    return allowed


def source_files(root):
    root = Path(root).resolve()
    names = public_manifest(root)
    finished_workflow = workflow_assets(root)
    if not finished_workflow.issubset(set(names)):
        raise ValueError('Public source list is missing workflow media')
    result = []
    for name in names:
        relative = PurePosixPath(name)
        path = root/relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Public source file missing or outside the repository: {name}')
        if relative.parts[:3] == ('docs', 'assets', 'workflow') and name not in finished_workflow:
            raise ValueError(f'Unlisted workflow media: {name}')
        result.append(path)
    return result


def build(root, output):
    logging.info('START source archive build')
    root, output = Path(root).resolve(), Path(output).resolve()
    files = source_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=ROOT_FOLDER+"/"+path.relative_to(root).as_posix())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(files):
            raise ValueError("Source archive verification failed")
        for path, entry in zip(files, archive.namelist()):
            if archive.read(entry) != path.read_bytes():
                raise ValueError("Source archive bytes differ")
    logging.info('END source archive verified with %d files', len(files))
    return output
