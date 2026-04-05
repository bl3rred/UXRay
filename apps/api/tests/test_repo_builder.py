from pathlib import Path
import sys
import uuid
from unittest.mock import patch
import subprocess

from app.services.repo_builder import LocalRepoBuilder


def test_repo_builder_command_env_is_non_interactive() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)

    env = builder._command_env(build_root / "repo")

    assert env["CI"] == "true"
    assert env["PNPM_CONFIG_CONFIRM_MODULES_PURGE"] == "false"
    assert env["PNPM_CONFIG_IGNORE_WORKSPACE"] == "true"
    assert env["NPM_CONFIG_CACHE"]
    assert env["PNPM_STORE_DIR"]
    assert Path(env["NPM_CONFIG_CACHE"]).is_absolute()
    assert Path(env["PNPM_STORE_DIR"]).is_absolute()
    assert Path(env["TEMP"]).is_absolute()


def test_repo_builder_uses_absolute_build_root_and_workspace_safe_pnpm_commands() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)

    assert builder.build_root.is_absolute()
    assert builder._install_command("pnpm")[1:] == ["--ignore-workspace", "install"]


def test_repo_builder_validates_writable_project_directory() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)

    project_root = builder.build_root / "project_test"
    builder._ensure_writable_directory(project_root, "test directory")

    assert project_root.exists()
    assert project_root.is_dir()


def test_repo_builder_uses_short_project_root() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)

    project_root = builder._project_root("project_1234567890ab")

    assert project_root.name == "p-1234567890ab"


def test_repo_builder_retries_npm_spawn_eperm_with_ignore_scripts() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    repo_dir = builder._project_root("project_retry") / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_dir.parent / "logs" / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("npm error Error: spawn EPERM", encoding="utf-8")

    commands: list[list[str]] = []

    def fake_run_command(command, *, cwd, log_path, env=None, timeout_seconds=None, inactivity_timeout_seconds=None):
        commands.append(command)
        if len(commands) == 1:
            raise RuntimeError(f"Local repo build command failed: {' '.join(command)}. See {log_path} for details.")

    with patch.object(builder, "_run_command", side_effect=fake_run_command):
        builder._install_dependencies(
            package_manager="npm",
            repo_dir=repo_dir,
            log_path=log_path,
        )

    assert commands[0][-3:] == ["install", "--no-audit", "--no-fund"]
    assert commands[1][-4:] == ["install", "--no-audit", "--no-fund", "--ignore-scripts"]


def test_repo_builder_retries_npm_on_install_timeout() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    repo_dir = builder._project_root("project_timeout") / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_dir.parent / "logs" / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    commands: list[list[str]] = []

    def fake_run_command(command, *, cwd, log_path, env=None, timeout_seconds=None, inactivity_timeout_seconds=None):
        commands.append(command)
        if len(commands) == 1:
            raise RuntimeError(
                f"Local repo build command timed out after 60 seconds: {' '.join(command)}. "
                f"See {log_path} for details."
            )

    with patch.object(builder, "_run_command", side_effect=fake_run_command):
        builder._install_dependencies(
            package_manager="npm",
            repo_dir=repo_dir,
            log_path=log_path,
        )

    assert len(commands) == 2
    assert commands[1][-4:] == ["install", "--no-audit", "--no-fund", "--ignore-scripts"]


def test_repo_builder_disables_npm_inactivity_timeout() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    repo_dir = builder._project_root("project_no_inactivity") / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_dir.parent / "logs" / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    captured: list[tuple[list[str], int | None]] = []

    def fake_run_command(command, *, cwd, log_path, env=None, timeout_seconds=None, inactivity_timeout_seconds=None):
        captured.append((command, inactivity_timeout_seconds))

    with patch.object(builder, "_run_command", side_effect=fake_run_command):
        builder._install_dependencies(
            package_manager="npm",
            repo_dir=repo_dir,
            log_path=log_path,
        )

    assert captured == [([builder._resolve_executable("npm"), "install", "--no-audit", "--no-fund"], None)]


def test_repo_builder_treats_successful_npm_debug_log_as_success_after_retry_error() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    repo_dir = builder._project_root("project_debug_success") / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_dir.parent / "logs" / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    npm_logs_dir = repo_dir.parent / ".cache" / "npm" / "_logs"
    npm_logs_dir.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []

    def fake_run_command(command, *, cwd, log_path, env=None, timeout_seconds=None, inactivity_timeout_seconds=None):
        commands.append(command)
        if len(commands) == 1:
            (npm_logs_dir / "2026-04-05T19_35_06_834Z-debug-0.log").write_text(
                "error command C:\\Windows\\system32\\cmd.exe /d /s /c husky\n",
                encoding="utf-8",
            )
            raise RuntimeError(f"Local repo build command failed: {' '.join(command)}. See {log_path} for details.")
        (npm_logs_dir / "2026-04-05T19_35_35_650Z-debug-0.log").write_text(
            "verbose exit 0\ninfo ok\n",
            encoding="utf-8",
        )
        raise RuntimeError(
            f"Local repo build command failed: {' '.join(command)}. See {log_path} for details."
        )

    with patch.object(builder, "_run_command", side_effect=fake_run_command):
        builder._install_dependencies(
            package_manager="npm",
            repo_dir=repo_dir,
            log_path=log_path,
        )

    assert len(commands) == 2


def test_repo_builder_identifies_husky_prepare_retry_from_npm_debug_log() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    repo_dir = builder._project_root("project_husky") / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_dir.parent / "logs" / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    npm_logs_dir = repo_dir.parent / ".cache" / "npm" / "_logs"
    npm_logs_dir.mkdir(parents=True, exist_ok=True)
    (npm_logs_dir / "2026-04-05T19_35_06_834Z-debug-0.log").write_text(
        "error command C:\\Windows\\system32\\cmd.exe /d /s /c husky\n",
        encoding="utf-8",
    )

    error = RuntimeError(
        f"Local repo build command failed: {builder._resolve_executable('npm')} install --no-audit --no-fund. "
        f"See {log_path} for details."
    )

    assert builder._is_npm_retryable_install_error(error) is True


def test_vite_preview_uses_windows_native_config_loader() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    repo_dir = builder._project_root("project_vite") / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_dir.parent / "logs" / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    captured: dict[str, list[str]] = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]

        class _Proc:
            def poll(self):
                return None

            def terminate(self):
                return None

            def wait(self, timeout=None):
                return 0

        return _Proc()

    with patch("app.services.repo_builder.subprocess.Popen", side_effect=fake_popen):
        builder._start_dev_server(
            framework="vite",
            package_manager="npm",
            repo_dir=repo_dir,
            port=4173,
            log_path=log_path,
        )

    assert "--configLoader" in captured["command"]
    assert "native" in captured["command"]
    assert "--require=" in captured["env"]["NODE_OPTIONS"]
    assert "vite_windows_realpath_shim.cjs" in captured["env"]["NODE_OPTIONS"]


def test_static_preview_uses_python_http_server() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    repo_dir = builder._project_root("project_static") / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_dir.parent / "logs" / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    captured: dict[str, list[str]] = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command

        class _Proc:
            def poll(self):
                return None

            def terminate(self):
                return None

            def wait(self, timeout=None):
                return 0

        return _Proc()

    with patch("app.services.repo_builder.subprocess.Popen", side_effect=fake_popen):
        builder._start_dev_server(
            framework="static",
            package_manager="python",
            repo_dir=repo_dir,
            port=4173,
            log_path=log_path,
        )

    assert captured["command"][:3] == [sys.executable, "-m", "http.server"]


def test_preview_is_not_usable_when_asset_request_fails() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)

    class _Proc:
        def poll(self):
            return None

    responses = [
        type("Resp", (), {"status_code": 200, "text": '<script type="module" src="/src/main.tsx"></script>'})(),
        type("Resp", (), {"status_code": 500, "text": ""})(),
    ]

    with patch("app.services.repo_builder.httpx.get", side_effect=responses):
        assert builder._preview_is_usable("http://127.0.0.1:4173", _Proc(), "vite") is False


def test_preview_integrity_errors_detect_vite_esbuild_failure() -> None:
    build_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    builder = LocalRepoBuilder(enabled=True, build_root=build_root)
    log_path = build_root / "repo-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "Internal server error: spawn EPERM\nPlugin: vite:esbuild\nFile: /src/index.tsx\n",
        encoding="utf-8",
    )

    assert builder._preview_has_integrity_errors(log_path) is True
