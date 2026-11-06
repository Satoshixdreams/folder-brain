---
title: Weekly cleanup prompt
summary: Prompt for the weekly scheduled task "brain-weekly-cleanup" (Sunday 20:17) that checks and cleans the Brain.
created: 2026-11-01
type: tool
---
Weekly cleanup of the owner's shared AI memory "Brain" at ~/Desktop/Brain (rules: ~/Desktop/Brain/AGENTS.md — read it first).

1. Run `python3 ~/Desktop/Brain/tools/check.py`.
2. Fix simple issues per AGENTS.md: missing INDEX lines, missing headers/summaries, memory files over 200 lines (split into a new dated file + INDEX), bad file names (English, YYYY-MM-DD_title.md).
3. Look for duplicates or contradictions inside each topic's memory/. Merge duplicates; for contradictions keep the newer fact and apply the upgrade rule. If unsure, do not change it — list it for the owner.
4. If check.py reports a POSSIBLE SECRET: do not print it; tell the owner the file name only.
5. Run check.py again, then `git add -A && git commit -m "Weekly cleanup YYYY-MM-DD"` and `git push` if a remote exists.
6. Topics flagged 'NO memory summary' or 'conversations newer than the memory': read the newest archive files of that topic (brain_search with include_conversations or brain_read) and save the decisions/facts/lessons as memory (brain_save kind=memory). If general/ holds many conversations about one subject, create a topic for it (with topic_keywords in English, German and Arabic) — the next sync moves them there.
7. Archive titles: call brain_titles_todo and give up to 20 archive files a real title with brain_set_title (3–10 English words that say what the part is about).
8. Never delete files in conversations/. Never publish anything or run paid generations.

Report to the owner in short Levantine Arabic: what was fixed, what needs his decision, files per topic.
