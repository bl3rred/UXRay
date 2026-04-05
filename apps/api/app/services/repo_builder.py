from __future__ import annotations

import io
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import httpx


ProgressReporter = Callable[[str], None]
WINDOWS_VITE_REALPATH_SHIM = (Path(__file__).resolve().parent / "vite_windows_realpath_shim.cjs").resolve()
INSTALL_TIMEOUT_SECONDS = 60
NON_NPM_INSTALL_INACTIVITY_TIMEOUT_SECONDS = 20
PREVIEW_STARTUP_TIMEOUT_SECONDS = 45
NPM_INSTALL_BASE_ARGS = ("install", "--no-audit", "--no-fund")
VITE_PREVIEW_ERROR_MARKERS = (
    "plugin: vite:esbuild",
    "pre-transform error",
    "internal server error",
    "error while updating dependencies:",
    "spawn EPERM",
)


@dataclass(slots=True)
class RepoPreviewResult:
    preview_url: str
    log_path: str
    repo_path: str
    framework: str


@dataclass(slots=True)
class RunningPreview:
    project_id: str
    repo_url: str
    preview_url: str
    process: subprocess.Popen[str]
    log_path: Path


class LocalRepoBuilder:
    def __init__(
        self,
        *,
        enabled: bool,
        build_root: Path,
    ) -> None:
        self.enabled = enabled
        self.build_root = build_root.resolve()
        self._ensure_writable_directory(self.build_root, "Local repo build root")
        self._previews: dict[str, RunningPreview] = {}

    def close(self) -> None:
        for preview in self._previews.values():
            self._stop_process(preview.process)
        self._previews.clear()

    def ensure_preview(
        self,
        *,
        project_id: str,
        repo_url: str,
        progress: ProgressReporter | None = None,
    ) -> RepoPreviewResult:
        if not self.enabled:
            raise RuntimeError("Local repository builds are disabled.")

        normalized_repo_url = self._normalize_repo_url(repo_url)
        existing = self._previews.get(project_id)
        project_root = self._project_root(project_id)
        if existing and existing.repo_url == normalized_repo_url and self._is_preview_healthy(existing.preview_url, existing.process):
            package_json_path = project_root / "repo" / "package.json"
            framework = "static"
            if package_json_path.exists():
                package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
                framework = self._detect_framework(package_json)
            return RepoPreviewResult(
                preview_url=existing.preview_url,
                log_path=str(existing.log_path),
                repo_path=str((project_root / "repo").resolve()),
                framework=framework,
            )

        progress = progress or (lambda message: None)
        self._ensure_writable_directory(project_root, f"Local repo build directory for project {project_id}")
        repo_dir = project_root / "repo"
        logs_dir = project_root / "logs"
        self._ensure_writable_directory(logs_dir, f"Local repo log directory for project {project_id}")
        build_log_path = logs_dir / "repo-preview.log"

        if repo_dir.exists():
            progress("Refreshing public repository clone.")
            if (repo_dir / ".git").exists():
                self._run_command(["git", "pull", "--ff-only"], cwd=repo_dir, log_path=build_log_path)
            else:
                shutil.rmtree(repo_dir)
                self._download_github_archive(normalized_repo_url, repo_dir, build_log_path)
        else:
            progress("Cloning public repository locally.")
            repo_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._run_command(
                    ["git", "clone", normalized_repo_url, str(repo_dir.resolve())],
                    cwd=self.build_root,
                    log_path=build_log_path,
                )
            except RuntimeError:
                self._download_github_archive(normalized_repo_url, repo_dir, build_log_path)

        package_json_path = repo_dir / "package.json"
        package_json: dict | None = None
        if package_json_path.exists():
            package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
            framework = self._detect_framework(package_json)
            package_manager = self._detect_package_manager(repo_dir, package_json)
            if not (repo_dir / "node_modules").exists():
                progress(f"Installing dependencies with {package_manager}.")
                self._install_dependencies(
                    package_manager=package_manager,
                    repo_dir=repo_dir,
                    log_path=build_log_path,
                )
        elif (repo_dir / "index.html").exists():
            framework = "static"
            package_manager = "python"
        else:
            raise RuntimeError(
                "Public repo build supports frontend repos with a root package.json or a static root index.html."
            )

        progress(f"Starting local {framework} preview.")
        port = self._find_open_port()
        preview_url = f"http://127.0.0.1:{port}"

        if existing:
            self._stop_process(existing.process)

        process = self._start_dev_server(
            framework=framework,
            package_manager=package_manager,
            repo_dir=repo_dir,
            port=port,
            log_path=build_log_path,
        )
        self._wait_for_preview(preview_url, process, build_log_path, framework)
        self._previews[project_id] = RunningPreview(
            project_id=project_id,
            repo_url=normalized_repo_url,
            preview_url=preview_url,
            process=process,
            log_path=build_log_path,
        )
        return RepoPreviewResult(
            preview_url=preview_url,
            log_path=str(build_log_path),
            repo_path=str(repo_dir.resolve()),
            framework=framework,
        )

    def _normalize_repo_url(self, repo_url: str) -> str:
        parsed = urlparse(repo_url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
            raise RuntimeError("Local repo builds currently support public GitHub repos only.")
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 2:
            raise RuntimeError("Repository URL must point to a public GitHub owner/repo.")
        owner, repo = segments[:2]
        return f"https://github.com/{owner}/{repo}.git"

    def _detect_framework(self, package_json: dict) -> str:
        dependencies = {
            **(package_json.get("dependencies") or {}),
            **(package_json.get("devDependencies") or {}),
        }
        scripts = package_json.get("scripts") or {}
        dev_script = str(scripts.get("dev") or "")
        if "next" in dependencies or "next" in dev_script:
            return "next"
        if "vite" in dependencies or "vite" in dev_script:
            return "vite"
        raise RuntimeError("Local repo builds currently support Next.js and Vite repos only.")

    def _detect_package_manager(self, repo_dir: Path, package_json: dict) -> str:
        package_manager = str(package_json.get("packageManager") or "")
        if package_manager.startswith("pnpm") or (repo_dir / "pnpm-lock.yaml").exists():
            return "pnpm"
        if package_manager.startswith("yarn") or (repo_dir / "yarn.lock").exists():
            return "yarn"
        return "npm"

    def _install_command(self, package_manager: str) -> list[str]:
        if package_manager == "pnpm":
            return [self._resolve_executable("pnpm"), "--ignore-workspace", "install"]
        if package_manager == "yarn":
            return [self._resolve_executable("yarn"), "install"]
        return [self._resolve_executable("npm"), *NPM_INSTALL_BASE_ARGS]

    def _install_dependencies(
        self,
        *,
        package_manager: str,
        repo_dir: Path,
        log_path: Path,
    ) -> None:
        env = self._command_env(repo_dir)
        command = self._install_command(package_manager)
        inactivity_timeout_seconds = (
            None if package_manager == "npm" else NON_NPM_INSTALL_INACTIVITY_TIMEOUT_SECONDS
        )
        try:
            self._run_command(
                command,
                cwd=repo_dir,
                log_path=log_path,
                env=env,
                timeout_seconds=INSTALL_TIMEOUT_SECONDS,
                inactivity_timeout_seconds=inactivity_timeout_seconds,
            )
        except RuntimeError as exc:
            if package_manager != "npm" or not self._is_npm_retryable_install_error(exc):
                raise
            self._cleanup_failed_install(repo_dir)
            retry_command = [
                self._resolve_executable("npm"),
                *NPM_INSTALL_BASE_ARGS,
                "--ignore-scripts",
            ]
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\n\n[uxray] npm install hit a Windows-specific failure, retrying once with "
                    "--ignore-scripts.\n"
                )
            try:
                self._run_command(
                    retry_command,
                    cwd=repo_dir,
                    log_path=log_path,
                    env=env,
                    timeout_seconds=INSTALL_TIMEOUT_SECONDS,
                    inactivity_timeout_seconds=None,
                )
            except RuntimeError as retry_exc:
                if self._latest_npm_debug_log_indicates_success(repo_dir):
                    with log_path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            "\n\n[uxray] npm fallback command looked failed from process output, "
                            "but npm debug log ended with exit 0/info ok. Treating install as successful.\n"
                        )
                    return
                raise self._enrich_npm_install_error(retry_exc, repo_dir) from retry_exc

    def _start_dev_server(
        self,
        *,
        framework: str,
        package_manager: str,
        repo_dir: Path,
        port: int,
        log_path: Path,
    ) -> subprocess.Popen[str]:
        executable = self._resolve_executable(package_manager)
        if framework == "static":
            command = [
                sys.executable,
                "-m",
                "http.server",
                str(port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(repo_dir),
            ]
        elif framework == "next":
            base_command = [executable]
            if package_manager == "pnpm":
                base_command.append("--ignore-workspace")
            command = [*base_command, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(port)]
        else:
            base_command = [executable]
            if package_manager == "pnpm":
                base_command.append("--ignore-workspace")
            config_loader = "native" if os.name == "nt" else "runner"
            command = [
                *base_command,
                "run",
                "dev",
                "--",
                "--configLoader",
                config_loader,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--strictPort",
            ]

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n\n[uxray] starting preview command: {' '.join(command)}\n")

        log_handle = log_path.open("a", encoding="utf-8")
        creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        preview_env = {**self._command_env(repo_dir), "BROWSER": "none"}
        if framework == "vite" and os.name == "nt":
            preview_env["NODE_OPTIONS"] = self._with_node_option(
                preview_env.get("NODE_OPTIONS"),
                f"--require={WINDOWS_VITE_REALPATH_SHIM}",
            )
        try:
            return subprocess.Popen(
                command,
                cwd=repo_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=preview_env,
                creationflags=creation_flags,
            )
        except OSError as exc:
            raise RuntimeError(
                f"Local repo preview failed to start ({exc}). See {log_path} for details."
            ) from exc

    def _run_command(
        self,
        command: list[str],
        *,
        cwd: Path,
        log_path: Path,
        env: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
        inactivity_timeout_seconds: float | None = None,
    ) -> None:
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
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"\n\n[uxray] running: {' '.join(command)}\n")
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    bufsize=1,
                )
                reader = threading.Thread(
                    target=reader_worker,
                    args=(process.stdout,),
                    name="uxray-repo-build-log-reader",
                    daemon=True,
                )
                reader.start()
                start_time = time.time()
                last_output_at = start_time
                reader_finished = False

                while True:
                    try:
                        item = output_queue.get(timeout=0.5)
                        if item is None:
                            reader_finished = True
                        else:
                            handle.write(item)
                            handle.flush()
                            last_output_at = time.time()
                    except queue.Empty:
                        pass

                    if timeout_seconds is not None and (time.time() - start_time) > timeout_seconds:
                        self._stop_process(process)
                        raise RuntimeError(
                            f"Local repo build command timed out after {int(timeout_seconds)} seconds: "
                            f"{' '.join(command)}. See {log_path} for details."
                        )
                    if (
                        inactivity_timeout_seconds is not None
                        and process.poll() is None
                        and (time.time() - last_output_at) > inactivity_timeout_seconds
                    ):
                        self._stop_process(process)
                        raise RuntimeError(
                            f"Local repo build command stalled with no output for "
                            f"{int(inactivity_timeout_seconds)} seconds: {' '.join(command)}. "
                            f"See {log_path} for details."
                        )
                    if process.poll() is not None and reader_finished and output_queue.empty():
                        break

                completed_returncode = process.wait(timeout=5)
        except OSError as exc:
            raise RuntimeError(
                f"Local repo build command could not start: {' '.join(command)} ({exc}). "
                f"See {log_path} for details."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Local repo build command timed out after {int(timeout_seconds or 0)} seconds: "
                f"{' '.join(command)}. See {log_path} for details."
            ) from exc
        if completed_returncode != 0:
            raise RuntimeError(
                f"Local repo build command failed: {' '.join(command)}. See {log_path} for details."
            )

    def _download_github_archive(self, repo_url: str, target_dir: Path, log_path: Path) -> None:
        owner, repo = self._extract_owner_repo(repo_url)
        repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = httpx.get(
            repo_api_url,
            timeout=20.0,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "uxray-local-builder"},
        )
        response.raise_for_status()
        default_branch = response.json().get("default_branch")
        if not default_branch:
            raise RuntimeError("Could not resolve the default branch for the public GitHub repo.")

        archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{default_branch}"
        archive_response = httpx.get(archive_url, timeout=60.0, follow_redirects=True)
        archive_response.raise_for_status()

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
            archive.extractall(target_dir.parent)
            extracted_root = target_dir.parent / f"{repo}-{default_branch}"
            if not extracted_root.exists():
                extracted_candidates = [path for path in target_dir.parent.iterdir() if path.is_dir() and path.name.startswith(f"{repo}-")]
                if not extracted_candidates:
                    raise RuntimeError("Downloaded GitHub archive did not contain an extractable repo root.")
                extracted_root = extracted_candidates[0]
            extracted_root.rename(target_dir)

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n\n[uxray] git clone failed on this machine, downloaded GitHub archive instead.\n"
            )

    def _wait_for_preview(
        self,
        preview_url: str,
        process: subprocess.Popen[str],
        log_path: Path,
        framework: str,
    ) -> None:
        deadline = time.time() + PREVIEW_STARTUP_TIMEOUT_SECONDS
        while time.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"Local repo preview exited before becoming ready. See {log_path} for details."
                )
            if self._preview_has_integrity_errors(log_path):
                self._stop_process(process)
                raise RuntimeError(
                    f"Local repo preview served a broken app because client assets failed to compile. "
                    f"See {log_path} for details."
                )
            if self._preview_is_usable(preview_url, process, framework):
                return
            time.sleep(1.0)
        self._stop_process(process)
        raise RuntimeError(
            f"Timed out waiting for local repo preview after {PREVIEW_STARTUP_TIMEOUT_SECONDS} seconds at "
            f"{preview_url}. See {log_path} for details."
        )

    def _is_preview_healthy(self, preview_url: str, process: subprocess.Popen[str]) -> bool:
        if process.poll() is not None:
            return False
        try:
            response = httpx.get(preview_url, timeout=2.0, follow_redirects=True)
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    def _preview_is_usable(self, preview_url: str, process: subprocess.Popen[str], framework: str) -> bool:
        if process.poll() is not None:
            return False
        try:
            response = httpx.get(preview_url, timeout=2.0, follow_redirects=True)
        except httpx.HTTPError:
            return False
        if response.status_code >= 500:
            return False
        if framework == "static":
            return response.status_code < 400

        asset_paths = self._extract_same_origin_asset_paths(response.text, preview_url)
        if not asset_paths:
            return response.status_code < 400

        for asset_path in asset_paths:
            try:
                asset_response = httpx.get(asset_path, timeout=2.0, follow_redirects=True)
            except httpx.HTTPError:
                return False
            if asset_response.status_code >= 400:
                return False
        return True

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    def _find_open_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return int(sock.getsockname()[1])

    def _resolve_executable(self, name: str) -> str:
        candidates = [f"{name}.cmd", f"{name}.exe", name]
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        raise RuntimeError(f"Required executable '{name}' is not available on PATH.")

    def _extract_owner_repo(self, repo_url: str) -> tuple[str, str]:
        parsed = urlparse(repo_url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        owner, repo = segments[:2]
        repo_name = repo.removesuffix(".git")
        return owner, repo_name

    def _project_root(self, project_id: str) -> Path:
        return self.build_root / f"p-{project_id[-12:]}"

    def _cleanup_failed_install(self, repo_dir: Path) -> None:
        for relative in ("node_modules", ".cache"):
            candidate = repo_dir / relative
            if candidate.exists():
                shutil.rmtree(candidate, ignore_errors=True)

    def _is_npm_retryable_install_error(self, error: RuntimeError) -> bool:
        message = str(error)
        if "npm.cmd" not in message:
            return False
        debug_log = self._read_latest_npm_debug_log_text_from_error(message)
        if "command c:\\windows\\system32\\cmd.exe /d /s /c husky" in debug_log.lower():
            return True
        if "spawn EPERM" in self._read_log_tail_from_error(message):
            return True
        return "timed out" in message.lower() or "stalled with no output" in message.lower()

    def _enrich_npm_install_error(self, error: RuntimeError, repo_dir: Path) -> RuntimeError:
        message = str(error)
        debug_log = self._read_latest_npm_debug_log_text(repo_dir)
        if not debug_log:
            return error
        lowered = debug_log.lower()
        if "command c:\\windows\\system32\\cmd.exe /d /s /c husky" in lowered:
            return RuntimeError(
                f"{message} npm install failed because the repo prepare script runs husky. "
                "UXRay already retried with --ignore-scripts."
            )
        if "spawn eperm" in lowered:
            return RuntimeError(f"{message} npm reported spawn EPERM in its debug log.")
        return error

    def _latest_npm_debug_log_indicates_success(self, repo_dir: Path) -> bool:
        debug_log = self._read_latest_npm_debug_log_text(repo_dir)
        lowered = debug_log.lower()
        return "verbose exit 0" in lowered and "info ok" in lowered

    def _read_latest_npm_debug_log_text_from_error(self, error_message: str) -> str:
        match = re.search(r"See (.+) for details\.$", error_message)
        if not match:
            return ""
        log_path = Path(match.group(1))
        repo_dir = log_path.parent.parent / "repo"
        return self._read_latest_npm_debug_log_text(repo_dir)

    def _read_latest_npm_debug_log_text(self, repo_dir: Path) -> str:
        logs_dir = repo_dir.parent / ".cache" / "npm" / "_logs"
        if not logs_dir.exists():
            return ""
        try:
            candidates = sorted(logs_dir.glob("*-debug-0.log"), key=lambda path: path.stat().st_mtime)
        except OSError:
            return ""
        if not candidates:
            return ""
        try:
            return candidates[-1].read_text(encoding="utf-8")
        except OSError:
            return ""

    def _read_log_tail_from_error(self, error_message: str) -> str:
        match = re.search(r"See (.+) for details\.$", error_message)
        if not match:
            return ""
        log_path = Path(match.group(1))
        if not log_path.exists():
            return ""
        try:
            with log_path.open("r", encoding="utf-8") as handle:
                return handle.read()[-4000:]
        except OSError:
            return ""

    def _preview_has_integrity_errors(self, log_path: Path) -> bool:
        if not log_path.exists():
            return False
        try:
            log_tail = log_path.read_text(encoding="utf-8")[-12000:].lower()
        except OSError:
            return False
        return any(marker in log_tail for marker in VITE_PREVIEW_ERROR_MARKERS)

    def _extract_same_origin_asset_paths(self, html: str, preview_url: str) -> list[str]:
        candidates = re.findall(r"""(?:src|href)=["']([^"']+)["']""", html, re.IGNORECASE)
        asset_paths: list[str] = []
        for candidate in candidates:
            if not candidate:
                continue
            if candidate.startswith(("http://", "https://", "//", "data:", "mailto:", "#")):
                continue
            if candidate.endswith((".css", ".js", ".mjs", ".ts", ".tsx", ".jsx")) or candidate.startswith("/src/"):
                asset_paths.append(str(httpx.URL(preview_url).join(candidate)))
        deduped: list[str] = []
        for asset_path in asset_paths:
            if asset_path not in deduped:
                deduped.append(asset_path)
        return deduped

    def _command_env(self, repo_dir: Path) -> dict[str, str]:
        repo_dir = repo_dir.resolve()
        cache_root = (repo_dir.parent / ".cache").resolve()
        npm_cache = cache_root / "npm"
        yarn_cache = cache_root / "yarn"
        pnpm_store = cache_root / "pnpm-store"
        pnpm_home = cache_root / "pnpm-home"
        npm_prefix = cache_root / "npm-prefix"
        temp_root = cache_root / "tmp"
        npm_cache.mkdir(parents=True, exist_ok=True)
        yarn_cache.mkdir(parents=True, exist_ok=True)
        pnpm_store.mkdir(parents=True, exist_ok=True)
        pnpm_home.mkdir(parents=True, exist_ok=True)
        npm_prefix.mkdir(parents=True, exist_ok=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        return {
            **os.environ,
            "CI": "true",
            "NPM_CONFIG_CACHE": str(npm_cache),
            "npm_config_cache": str(npm_cache),
            "PNPM_CONFIG_CONFIRM_MODULES_PURGE": "false",
            "PNPM_CONFIG_IGNORE_WORKSPACE": "true",
            "YARN_CACHE_FOLDER": str(yarn_cache),
            "PNPM_HOME": str(pnpm_home),
            "PNPM_STORE_DIR": str(pnpm_store),
            "npm_config_prefix": str(npm_prefix),
            "TEMP": str(temp_root),
            "TMP": str(temp_root),
        }

    def _ensure_writable_directory(self, path: Path, label: str) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".uxray-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise RuntimeError(f"{label} is not writable: {path} ({exc})") from exc

    def _with_node_option(self, existing: str | None, addition: str) -> str:
        if not existing:
            return addition
        if addition in existing:
            return existing
        return f"{existing} {addition}"
