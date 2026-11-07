#!/bin/bash
# Folder Brain — one-click installer for macOS.
# Double-click this file. It checks Python, tests the Brain, and offers to
# register the MCP server in Claude Desktop. Nothing is published, nothing is paid.

set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
say() { printf '%s\n' "$*"; }
pause() { printf '\nPress Enter to close…'; read -r _; }

say "Folder Brain — installer"
say "========================"
say ""

# 1. Python
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  say "✗ python3 not found. Install it from https://www.python.org/downloads/ and run this again."
  pause; exit 1
fi
say "✓ python3: $($PY -V 2>&1)"

# 2. Where should the Brain live?
DEFAULT="$HOME/brain"
printf 'Where should your Brain folder live? [%s]: ' "$DEFAULT"
read -r DEST
DEST="${DEST:-$DEFAULT}"
DEST="${DEST/#\~/$HOME}"

if [ "$DEST" != "$SRC" ]; then
  if [ -d "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    say "✗ $DEST already exists and is not empty. Pick another path or move it away."
    pause; exit 1
  fi
  mkdir -p "$DEST"
  (cd "$SRC" && tar --exclude='.git' --exclude='__pycache__' -cf - .) | (cd "$DEST" && tar -xf -)
  say "✓ copied to $DEST"
else
  say "✓ using this folder: $DEST"
fi

# 3. Health check
if ! (cd "$DEST" && "$PY" tools/check.py); then
  say ""
  say "! The check reported problems (see above). The Brain still works, but read them."
fi

# 4. Optional: register in Claude Desktop
CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
printf '\nAdd the Brain to Claude Desktop now? [y/N]: '
read -r ADD
if [ "${ADD:-n}" = "y" ] || [ "${ADD:-n}" = "Y" ]; then
  mkdir -p "$(dirname "$CFG")"
  [ -f "$CFG" ] && cp "$CFG" "$CFG.bak.$(date +%Y%m%d-%H%M%S)" && say "✓ backup of the old config made"
  "$PY" - "$CFG" "$DEST" "$PY" <<'PY'
import json, os, sys
cfg_path, brain, pybin = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(cfg_path):
    try:
        data = json.load(open(cfg_path))
    except Exception:
        print("! existing config is not valid JSON — left untouched"); raise SystemExit(0)
servers = data.setdefault("mcpServers", {})
servers["brain"] = {"command": pybin,
                    "args": [os.path.join(brain, "mcp", "brain_mcp.py")],
                    "env": {"BRAIN_DIR": brain}}
json.dump(data, open(cfg_path, "w"), indent=2)
print("✓ Claude Desktop config updated:", cfg_path)
PY
  say "→ Quit and reopen Claude Desktop to load the Brain."
fi

# 5. Done
say ""
say "Done. Your Brain: $DEST"
say "Next: open core.md and replace every <...> with your own facts."
open "$DEST/core.md" 2>/dev/null || true
pause
