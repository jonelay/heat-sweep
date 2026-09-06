"""Local FastAPI server: result query API, device listing, synchronous
model runs, WebSocket job events. Built on the shared view-sweep-server
toolkit, which owns the generic layer (WebSocket connection manager,
local-only Host/Origin guard, logging, static mounts).

Requires the `server` extra: uv sync --extra server
"""
