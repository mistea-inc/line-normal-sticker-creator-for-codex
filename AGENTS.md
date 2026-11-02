# LINE Normal Sticker Creator for Codex

This repository creates ordinary static LINE sticker sets from the user's own references. End users give natural-language requests; Codex runs setup and production commands.

- For starting or resuming production, read `.agents/skills/line-sticker-production/SKILL.md`, `README.md`, and the linked guide needed for the current phase. All required project instructions are included here; do not depend on a private development repository.
- Check the actual OS, Python 3.11+, desktop display and image-generation tool availability before promising setup or generation. A Python script cannot provision Codex image generation. Do not switch to a paid external API without user authorization.
- Start setup or production when the user requests it. Opening this folder or connecting GitHub does not itself run installation. Do not launch VectorCraft merely to edit documentation.
- Ask for missing creative decisions, actual review feedback, unavailable permissions or required authentication. Run ordinary CLI commands yourself.
- Read references before designing the character. Keep original images and human edits. Use `input/references/` for incoming images and `projects/<name>/` for private work and progress records. Resume existing work instead of recreating it.
- Use the current session's image-generation tool for text-free, transparent artwork. Use VectorCraft for editable compositing, lettering and PNG export. Use Pillow for inspection, not to replace the agreed editing workflow.
- Keep one editable `.vectorcraft` file per sticker. A sample establishes direction, not a fixed layout for the set. Fonts, colors and composition may vary per design.
- Open the agreed review batch in individual tabs. Save the user's changes and record the actual completion message. Never invent approval or mark visual inspection automatically. Preserve unrelated open documents and unsaved edits.
- Retain PNG and ZIP checks, source/reference correspondence, approval hashes, final visual findings, environment diagnosis and resume state. Technical checks supplement visual judgment.
- Check the current LINE specification before export. Include Main and Tab in review, and distinguish upload preparation from actual registration and review submission.
- Do not change global Codex settings or register global MCP servers. VectorCraft uses a project-scoped native loopback control channel. Keep operations portable across Windows, macOS and Linux, and log starts, ends, errors and important decisions.
- Keep references, artwork, designs, upload packages, logs, runtime settings and secrets out of this public source repository. Documentation media must be edited outside the repository; copy only finished, visually checked media into `docs/assets/`.
- `source-files.json` is the public source allowlist used by `scripts/build_source_zip.py`. Keep it aligned with the repository's distributable files and the tracking allowlist in `.gitignore`. Do not add development tests, private records, source media, local environments or secrets to it.
