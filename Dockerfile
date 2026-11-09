# Folder Brain — MCP server (stdio). Small, no build step, no dependencies.
# Used by directory checks (Glama) and by anyone who wants to run it in a container.
FROM python:3.12-slim

WORKDIR /app

# Only the server code — the Brain data stays on the host and is mounted at /brain.
COPY mcp/ /app/mcp/
COPY core.md AGENTS.md INDEX.md /app/

ENV BRAIN_DIR=/app
# Optional: mount your own Brain instead of the bundled template
# docker run -v /path/to/brain:/brain -e BRAIN_DIR=/brain ...

# stdio transport: no port, the client talks to the process.
ENTRYPOINT ["python3", "/app/mcp/brain_mcp.py"]
