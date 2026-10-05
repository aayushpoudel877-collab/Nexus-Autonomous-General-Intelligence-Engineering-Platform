"""Entry point for isolated secret broker subprocess."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import signal

from .broker import SecretBroker, SecretGrantSpec


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--config", required=True)
    return parser.parse_args()


async def _run() -> None:
    args = _args()
    token = Path(args.token_file).read_text(encoding="ascii").strip()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    grants = [
        SecretGrantSpec(
            grant_id=item["grant_id"],
            secret_ref=item["secret_ref"],
        )
        for item in config["grants"]
    ]
    broker = SecretBroker(
        grants=grants,
        token=token,
        socket_path=args.socket,
    )
    await broker.start()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _stop() -> None:
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _stop)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await stop_event.wait()
    finally:
        await broker.stop()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
