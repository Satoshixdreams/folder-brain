#!/usr/bin/env python3
"""Conversation archive: split long conversations into parts whose FILE NAME says what is inside.

Used by sync-conversations.py (and runnable on its own to split files already in the Brain):
    python3 tools/archive.py            # split every long conversation file in the Brain

Rules (they live here, not in any AI model, so every assistant archives the same way):
- A conversation over ~300 lines is cut into parts at turn boundaries: a new day, a pause of
  more than an hour, or ~300 lines. Short conversations stay one file. Every word is kept.
- Each part is its own file: YYYY-MM-DD_<agent>-session_<what-it-is-about>.md, with
  `session:` and `part: n/N` in the header, so the whole conversation can be put back together.
- The name is first made from the part's key words (title_status: auto, free, no model needed).
  Any assistant can later give a better title with the brain tool `brain_set_title`
  (title_status: named); the Brain itself writes the file name, so the format never changes.
"""
import collections
import datetime
import re
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BRAIN / "mcp"))
from brain_mcp import SYN, STOP, find_trap, index_row, locked, norm  # noqa: E402

PART_LINES = 300
MIN_PART_LINES = 40
GAP_MINUTES = 60
TURN = re.compile(r"^### (\S+) · (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*$", re.M)
ENGLISH = {}
for word, group in SYN.items():  # every synonym → its English word (first ASCII word of the group)
    ascii_words = sorted((w for w in group if re.fullmatch(r"[a-z0-9]+", w)), key=lambda w: (len(w) > 9, w))
    if ascii_words:
        ENGLISH[word] = ascii_words[0]
NOISE = set("tool session claude codex hermes owner bash read write edit description file path users sami desktop "
            "brain md json true false none null http https www com the and for with this that you your from have "
            "will can not are was what when ich und der die das mit nicht ist ein eine auch".split())


def when(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M")


def parse(text):
    """Split a conversation file into (header_dict, turns[(who, ts, body)])."""
    head = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                head[k.strip()] = v.strip()
    sess = re.search(r"^session: (\S+)", text, re.M)
    if sess:
        head["session"] = sess.group(1)
    marks = list(TURN.finditer(text))
    turns = []
    for i, mk in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        turns.append((mk.group(1), mk.group(2), text[mk.end():end].strip("\n")))
    return head, turns


def split(turns):
    parts, cur, lines, last = [], [], 0, None
    for who, ts, body in turns:
        n = body.count("\n") + 3
        gap = last and ((when(ts) - when(last)).total_seconds() / 60 > GAP_MINUTES or ts[:10] != last[:10])
        if cur and who == "Owner" and (lines + n > PART_LINES or (gap and lines >= MIN_PART_LINES)):
            parts.append(cur)
            cur, lines = [], 0
        cur.append((who, ts, body))
        lines += n
        last = ts
    if cur:
        parts.append(cur)
    return parts


def key_title(part, fallback):
    """Free title from the part's key words (owner words count double)."""
    count = collections.Counter()
    for who, _, body in part:
        if body.startswith("_[tool:"):
            continue
        for w in re.findall(r"\w+", norm(body)):
            if w in STOP or w in NOISE or w.isdigit() and len(w) > 4:
                continue
            word = ENGLISH.get(w) or (w if re.fullmatch(r"[a-z][a-z0-9]{2,}", w) else None)
            if word and word not in NOISE:
                count[word] += 2 if who == "Owner" else 1
    words = [w for w, _ in count.most_common(6)]
    return "-".join(words)[:60].strip("-") or fallback


def first_owner_line(part):
    for who, _, body in part:
        if who == "Owner" and body.strip():
            return re.sub(r"\s+", " ", body.strip())[:140].replace("|", "/")
    return ""


def render(head, part, n, total, title, status):
    body = "\n\n".join(f"### {w} · {ts}\n{t}" for w, ts, t in part)
    date = part[0][1][:10]
    summary = head.get("part_summary") or (
        f"Part {n}/{total} of {head.get('agent', '').capitalize()} conversation '{head.get('conv_title', '')}': "
        f"{first_owner_line(part)}").replace("|", "/")
    flag = "flags: suspicious-text\n" if find_trap(body) else ""
    return (f"---\ntitle: {title}\nsummary: {summary}\ncreated: {date}\ntopic: {head['topic']}\ntype: conversation\n"
            f"agent: {head.get('agent', '')}\npart: {n}/{total}\ntitle_status: {status}\n{flag}---\n\n"
            f"session: {head['session']}\n\n{body}\n"), summary


def existing_parts(folder):
    """(session, part) → path for the parts already in this topic, plus unsplit files per session."""
    found = {}
    for f in (folder / "conversations").glob("*.md"):
        t = f.read_text(errors="ignore")[:1500]
        s = re.search(r"^session: (\S+)", t, re.M)
        if s:
            p = re.search(r"^part: (\d+)/\d+", t, re.M)
            st = re.search(r"^title_status: (\S+)", t, re.M)
            ti = re.search(r"^title: (.*)$", t, re.M)
            su = re.search(r"^summary: (.*)$", t, re.M)
            found[(s.group(1), int(p.group(1)) if p else 0)] = (f, st.group(1) if st else "auto", ti.group(1) if ti else "",
                                                               su.group(1) if su else "")
    return found


def unique(path):
    n = 2
    base = path
    while path.exists():
        path = base.with_name(base.stem + f"-{n}.md")
        n += 1
    return path


def write_conversation(folder, agent, session, conv_title, turns, known=None):
    """Write one conversation as one file (short) or as titled parts (long). Returns files changed."""
    known = existing_parts(folder) if known is None else known
    total_lines = sum(b.count("\n") + 3 for _, _, b in turns)
    parts = split(turns) if total_lines > PART_LINES else [turns]
    head = {"topic": folder.name, "agent": agent, "session": session, "conv_title": conv_title}
    changed = 0
    with locked():
        for n, part in enumerate(parts, 1):
            old = known.get((session, n)) or (known.get((session, 0)) if n == 1 else None)
            keep_summary = ""
            if old and old[1] == "named":  # a model titled it: keep its name, title AND summary
                path, title, status, keep_summary = old[0], old[2], "named", old[3]
            elif len(parts) == 1 and old:  # short conversation: keep its file and title
                path, title, status = old[0], conv_title or old[2], old[1]
            else:
                status = "auto"
                conv_slug = re.sub(r"[^a-z0-9]+", "-", (conv_title or "").lower()).strip("-")[:55].rstrip("-")
                # one-part conversation: its own title is the best name; long ones: each part by its key words
                kt = conv_slug if len(parts) == 1 and len(conv_slug) >= 8 else key_title(part, conv_slug or "conversation")
                title = kt.replace("-", " ")
                name = f"{part[0][1][:10]}_{agent}-session_{kt}.md"
                path = old[0] if old and old[0].name == name else unique(folder / "conversations" / name)
            text, summary = render(dict(head, part_summary=keep_summary), part, n, len(parts), title, status)
            if old and old[0] != path:  # name changed (e.g. unsplit file became part 1)
                old[0].unlink()
                drop_index_row(folder, old[0].name)
            if not path.exists() or path.read_text() != text:
                path.write_text(text)
                index_row(folder, "conversations", path.name, summary)
                changed += 1
            known[(session, n)] = (path, status, title, summary)
        # remove parts that no longer exist (conversation got shorter after a re-split)
        for (s, n), (path, *_rest) in list(known.items()):
            if s == session and n > len(parts) and path.exists():
                path.unlink()
                drop_index_row(folder, path.name)
                del known[(s, n)]
        if (session, 0) in known and len(parts) >= 1:
            path = known.pop((session, 0))[0]
            if path.exists() and not re.search(r"^part: ", path.read_text(errors="ignore")[:800], re.M):
                path.unlink()
                drop_index_row(folder, path.name)
    return changed


def drop_index_row(folder, name):
    idx = folder / "INDEX.md"
    if idx.exists():
        idx.write_text("\n".join(l for l in idx.read_text().split("\n") if f"`{name}`" not in l).rstrip("\n") + "\n")


def main():
    """Split conversation files that are already in the Brain (no access to the original apps needed)."""
    changed = 0
    for folder in sorted(p for p in BRAIN.iterdir() if (p / "conversations").is_dir() and p.name != "customer-chats"):
        known = existing_parts(folder)
        for f in sorted((folder / "conversations").glob("*.md")):
            if not f.exists():
                continue
            text = f.read_text(errors="ignore")
            head, turns = parse(text)
            if "session" not in head or not turns or "part" in head:
                continue
            if sum(b.count("\n") + 3 for _, _, b in turns) <= PART_LINES:
                continue
            agent = head.get("agent", "chat")
            changed += write_conversation(folder, agent, head["session"], head.get("title", ""), turns, known)
    print(f"{changed} archive files written")
    return changed


if __name__ == "__main__":
    main()
