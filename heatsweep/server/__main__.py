"""uvicorn entry point: `uv run heatsweep-server` or `python -m heatsweep.server`."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="heat-sweep local server (single-user, localhost)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address. The Host/Origin guard stays local-only: this flag "
                             "whitelists only the literal string given here, so LAN clients "
                             "(which send 'Host: <ip>') are still rejected")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--devices-dir", type=Path, default=Path("devices"),
                        help="device TOML catalogue (flat or <name>/<name>.toml)")
    parser.add_argument("--output-dir", type=Path, default=Path("results"),
                        help="result store directory (results.jsonl + index.json)")
    parser.add_argument("--log-json", action="store_true",
                        help="JSON log output (default: colored console)")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        raise ImportError(
            "heatsweep-server requires the server extra: pip install heatsweep[server]"
        ) from None

    from heatsweep.server.app import ServerSettings, create_app

    app = create_app(ServerSettings(
        devices_dir=args.devices_dir,
        output_dir=args.output_dir,
        log_json=args.log_json,
        extra_allowed_hosts=(args.host,),
    ))
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
