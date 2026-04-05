from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import httpx


ProgressReporter = Callable[[str], None]


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
        self.build_root = build_root
        self.build_root.mkdir(parents=True, exist_ok=True)
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
        if existing and existing.repo_url == normalized_repo_url and self._is_preview_healthy(existing.preview_url, existing.process):
            package_json = json.loads((self.build_root / project_id / "repo" / "package.json").read_text(encoding="utf-8"))
            return RepoPreviewResult(
                preview_url=existing.preview_url,
                log_path=str(existing.log_path),
                repo_path=str((self.build_root / project_id / "repo").resolve()),
                framework=self._detect_framework(package_json),
            )

        progress = progress or (lambda message: None)
        repo_dir = self.build_root / project_id / "repo"
        logs_dir = self.build_root / project_id / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
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
        if not package_json_path.exists():
            raise RuntimeError("Public repo build only supports frontend repos with a root package.json.")

        package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
        framework = self._detect_framework(package_json)
        package_manager = self._detect_package_manager(repo_dir, package_json)

        if not (repo_dir / "node_modules").exists():
            progress(f"Installing dependencies with {package_manager}.")
            self._run_command(
                self._install_command(package_manager),
                cwd=repo_dir,
                log_path=build_log_path,
                env=self._command_env(repo_dir),
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
        self._wait_for_preview(preview_url, process, build_log_path)
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
            return [self._resolve_executable("pnpm"), "install"]
        if package_manager == "yarn":
            return [self._resolve_executable("yarn"), "install"]
        return [self._resolve_executable("npm"), "install"]

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
        if framework == "next":
            command = [executable, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(port)]
        else:
            command = [executable, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port), "--strictPort"]

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n\n[uxray] starting preview command: {' '.join(command)}\n")

        log_handle = log_path.open("a", encoding="utf-8")
        creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            return subprocess.Popen(
                command,
                cwd=repo_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                env={**self._command_env(repo_dir), "BROWSER": "none"},
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
    ) -> None:
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"\n\n[uxray] running: {' '.join(command)}\n")
                completed = subprocess.run(
                    command,
                    cwd=cwd,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                    env=env,
                )
        except OSError as exc:
            raise RuntimeError(
                f"Local repo build command could not start: {' '.join(command)} ({exc}). "
                f"See {log_path} for details."
            ) from exc
        if completed.returncode != 0:
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
            handle.write("\n\n[uxray] git clone failed, downloaded GitHub archive instead.\n")

    def _wait_for_preview(self, preview_url: str, process: subprocess.Popen[str], log_path: Path) -> None:
        deadline = time.time() + 90
        while time.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"Local repo preview exited before becoming ready. See {log_path} for details."
                )
            if self._is_preview_healthy(preview_url, process):
                return
            time.sleep(1.0)
        self._stop_process(process)
        raise RuntimeError(
            f"Timed out waiting for local repo preview at {preview_url}. See {log_path} for details."
        )

    def _is_preview_healthy(self, preview_url: str, process: subprocess.Popen[str]) -> bool:
        if process.poll() is not None:
            return False
        try:
            response = httpx.get(preview_url, timeout=2.0, follow_redirects=True)
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

    def _command_env(self, repo_dir: Path) -> dict[str, str]:
        cache_root = repo_dir.parent / ".cache"
        npm_cache = cache_root / "npm"
        yarn_cache = cache_root / "yarn"
        pnpm_store = cache_root / "pnpm-store"
        temp_root = cache_root / "tmp"
        npm_cache.mkdir(parents=True, exist_ok=True)
        yarn_cache.mkdir(parents=True, exist_ok=True)
        pnpm_store.mkdir(parents=True, exist_ok=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        return {
            **os.environ,
            "NPM_CONFIG_CACHE": str(npm_cache),
            "npm_config_cache": str(npm_cache),
            "NPM_CONFIG_TMP": str(temp_root),
            "npm_config_tmp": str(temp_root),
            "YARN_CACHE_FOLDER": str(yarn_cache),
            "PNPM_HOME": str(cache_root / "pnpm-home"),
            "PNPM_STORE_DIR": str(pnpm_store),
            "TEMP": str(temp_root),
            "TMP": str(temp_root),
        }
