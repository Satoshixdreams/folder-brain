#!/usr/bin/env python3
"""Weekly Brain health check. Prints problems; exit code 1 if any were found."""
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BRAIN / "mcp"))
from guard import SECRET, find_trap  # noqa: E402
SKIP_DIRS = {".git", "templates", "mcp", "tools", "skill"}
ROOT_FILES = {"INDEX.md", "AGENTS.md", "CLAUDE.md", "core.md", "README.md", "LICENSE", "SHARED-STATE.md"}
MAX_LINES = 200

problems = []
titles = defaultdict(list)

for f in sorted(BRAIN.rglob("*.md")):
    rel = f.relative_to(BRAIN)
    if rel.parts[0] in SKIP_DIRS or (len(rel.parts) == 1 and f.name in ROOT_FILES):
        continue
    if f.name == "INDEX.md":
        for name in re.findall(r"`([^`/]+\.md)`", f.read_text()):
            if not list(f.parent.glob(f"*/{name}")):
                problems.append(f"INDEX points to missing file: {rel} -> {name}")
        continue
    try:
        text = f.read_text(errors="ignore")
    except FileNotFoundError:  # renamed by another assistant while we were checking
        continue
    if SECRET.search(text):
        problems.append(f"POSSIBLE SECRET (remove it!): {rel}")
    trap = find_trap(text)
    parent = rel.parts[-2] if len(rel.parts) >= 2 else ""
    if parent in ("memory", "cards") and len(text.split("\n")) > MAX_LINES + 20:
        problems.append(f"memory/card longer than {MAX_LINES} lines — split it: {rel}")
    if re.search(r"^---\n(?:.*\n)*?(title|summary|type|topic):.*\n(?:.*\n)*?\1:", text[:1500]):
        problems.append(f"header has a field twice (forged header?): {rel}")
    if trap and parent in ("memory", "cards"):
        problems.append(f"BOOBY-TRAPPED MEMORY ({trap}) — check and remove: {rel}")
    elif trap and "flags: suspicious-text" not in text:
        problems.append(f"conversation with suspicious text not flagged ({trap}): {rel}")
    if parent == "memory" and re.search(r"(?i)\b(pending|not usable yet|not built yet)\b", text):
        upd = re.search(r"^updated:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
        if upd and upd.group(1) < __import__("datetime").date.fromordinal(__import__("datetime").date.today().toordinal() - 7).isoformat():
            problems.append(f"memory says 'pending' and was not updated for 7+ days — still true?: {rel}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_[a-z0-9_-]+\.md", f.name):
        problems.append(f"bad file name (want YYYY-MM-DD_english-title.md): {rel}")
    if not re.search(r"^summary:\s*\S", text, re.M):
        problems.append(f"missing header/summary: {rel}")
    lines = len(text.split("\n"))
    if parent == "memory" and lines > MAX_LINES:
        problems.append(f"memory file too long ({lines} lines > {MAX_LINES}), split it: {rel}")
    idx = f.parent.parent / "INDEX.md"
    if not idx.exists() or f"`{f.name}`" not in idx.read_text():
        problems.append(f"file not listed in its INDEX.md: {rel}")
    m = re.search(r"^title:\s*(.+)$", text, re.M)
    if m:
        titles[(rel.parts[0], m.group(1).strip().lower())].append(str(rel))

root_index = (BRAIN / "INDEX.md").read_text()
for d in sorted(p for p in BRAIN.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")):
    if f"`{d.name}/`" not in root_index:
        problems.append(f"topic folder not in root INDEX.md: {d.name}/")
    if not (d / "INDEX.md").exists():
        problems.append(f"topic folder has no INDEX.md: {d.name}/")

for (topic, title), files in titles.items():
    kinds = {Path(f).parts[-2] for f in files}
    if len(files) > 1 and len(kinds) == 1 and kinds != {"conversations"}:  # daily tasks share titles
        problems.append(f"possible duplicate '{title}' in {topic}: " + ", ".join(files))

# topics that have conversations but no (or an old) memory summary: something was not learned
for d in sorted(p for p in BRAIN.iterdir() if (p / "conversations").is_dir()):
    if d.name in ("customer-chats", "general"):
        continue
    convs = [f for f in (d / "conversations").glob("*.md")]
    mems = [f for f in (d / "memory").glob("*.md")] if (d / "memory").is_dir() else []
    if not convs:
        continue
    newest_conv = max(f.name[:10] for f in convs)
    newest_mem = max((re.search(r"^updated:\s*(\S+)", f.read_text(errors="ignore"), re.M) or [None, f.name[:10]])[1] for f in mems) if mems else ""
    if not mems:
        problems.append(f"topic has conversations but NO memory summary — read its archive and write one: {d.name}/")
    elif newest_conv > newest_mem and (__import__("datetime").date.fromisoformat(newest_conv) - __import__("datetime").date.fromisoformat(newest_mem)).days > 7:
        problems.append(f"conversations newer than the memory by 7+ days (newest conversation {newest_conv}, memory {newest_mem}) — summarise what is new: {d.name}/")
general = BRAIN / "general" / "conversations"
if general.is_dir() and len(list(general.glob("*.md"))) >= 5:
    print(f"[info] general/ holds {len(list(general.glob('*.md')))} conversations — maybe a new topic is needed")

# rule files change rarely and only by the owner: show every change of the last 7 days
for f in ("core.md", "AGENTS.md", "CLAUDE.md", "mcp/brain_mcp.py", "mcp/guard.py", ".gitignore"):
    log = subprocess.run(["git", "log", "--since=7 days ago", "--format=%ad %an: %s", "--date=short", "--", f],
                         cwd=BRAIN, capture_output=True, text=True).stdout.strip()
    if log:
        print(f"[info] {f} changed in the last 7 days:\n  " + log.replace("\n", "\n  "))
for f in ("core.md", "AGENTS.md"):
    trap = find_trap((BRAIN / f).read_text(), strict=False)  # rule files describe attacks
    if trap:
        problems.append(f"BOOBY-TRAPPED RULE FILE ({trap}): {f}")

if problems:
    print(f"{len(problems)} problem(s):")
    print("\n".join(f"- {p}" for p in problems))
    sys.exit(1)
print("Brain OK: no problems found.")
