from __future__ import annotations

import queue
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass

import httpx


TRYCLOUDFLARE_URL_RE = re.compile(r"https://[a-z0-9.-]+\.trycloudflare\.com", re.IGNORECASE)


@dataclass(slots=True)
class PreviewTunnel:
    local_url: str
    public_url: str
    process: subprocess.Popen[str]


class CloudflaredTunnelManager:
    def __init__(
        self,
        *,
        enabled: bool,
        binary: str,
        startup_timeout_seconds: float = 20.0,
    ) -> None:
        self.enabled = enabled
        self.binary = binary
        self.startup_timeout_seconds = startup_timeout_seconds
        self._tunnels: dict[str, PreviewTunnel] = {}

    def close(self) -> None:
        for tunnel in list(self._tunnels.values()):
            self._stop_process(tunnel.process)
        self._tunnels.clear()

    def expose(self, local_url: str) -> str:
        if not self.enabled:
            return local_url
        existing = self._tunnels.get(local_url)
        if existing and existing.process.poll() is None and self._is_healthy(existing.public_url):
            return existing.public_url

        executable = shutil.which(self.binary)
        if not executable:
            raise RuntimeError(
                f"Repo preview tunnel requires '{self.binary}' on PATH. Install cloudflared to audit repo previews remotely."
            )

        command = [executable, "tunnel", "--url", local_url]
        output_queue: queue.Queue[str | None] = queue.Queue()

        def reader_worker(stream) -> None:
            try:
                if stream is None:
                    return
                for line in iter(stream.readline, ""):
                    output_queue.put(line)
            finally:
                output_queue.put(None)

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise RuntimeError(
                f"Repo preview tunnel failed to start via {self.binary}: {exc}"
            ) from exc

        reader = threading.Thread(
            target=reader_worker,
            args=(process.stdout,),
            name="uxray-preview-tunnel-reader",
            daemon=True,
        )
        reader.start()

        deadline = time.time() + self.startup_timeout_seconds
        lines: list[str] = []
        public_url: str | None = None
        reader_finished = False

        while time.time() < deadline:
            try:
                item = output_queue.get(timeout=0.5)
                if item is None:
                    reader_finished = True
                else:
                    lines.append(item)
                    match = TRYCLOUDFLARE_URL_RE.search(item)
                    if match:
                        public_url = match.group(0)
                        break
            except queue.Empty:
                pass

            if process.poll() is not None and reader_finished and output_queue.empty():
                break

        if public_url is None:
            self._stop_process(process)
            joined_output = "".join(lines)[-4000:]
            raise RuntimeError(
                "Repo preview tunnel did not produce a public URL. "
                f"cloudflared output: {joined_output or 'no output'}"
            )

        if not self._is_healthy(public_url):
            self._stop_process(process)
            raise RuntimeError(
                f"Repo preview tunnel started but {public_url} did not become reachable."
            )

        self._tunnels[local_url] = PreviewTunnel(
            local_url=local_url,
            public_url=public_url,
            process=process,
        )
        return public_url

    def _is_healthy(self, public_url: str) -> bool:
        try:
            response = httpx.get(public_url, timeout=5.0, follow_redirects=True)
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
