import asyncio
import signal
from typing import Any

from apps.api.config import settings


class WorkerDaemon:
    def __init__(self) -> None:
        self.running = False
        self.grace_period = settings.RV_SHUTDOWN_GRACE_SECONDS
        self._stop_event: asyncio.Event | None = None

    def handle_signal(self, signum: int, frame: Any) -> None:
        print(
            f"[Worker] Received signal {signum}. Initiating graceful shutdown (grace period: {self.grace_period}s)..."
        )
        self.running = False
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()

    async def run(self) -> None:
        self.running = True
        self._stop_event = asyncio.Event()
        print(
            f"[Worker] Starting RekanVault worker daemon (version={settings.RV_RELEASE_VERSION}, env={settings.RV_ENV})..."
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):

            def make_handler(s: int) -> Any:
                return lambda: self.handle_signal(s, None)

            try:
                loop.add_signal_handler(sig, make_handler(sig))
            except NotImplementedError:
                signal.signal(sig, self.handle_signal)

        while self.running:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break

        print("[Worker] Graceful shutdown complete. Exiting clean.")


def main() -> None:
    worker = WorkerDaemon()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("[Worker] KeyboardInterrupt caught. Exiting.")


if __name__ == "__main__":
    main()
