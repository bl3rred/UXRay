from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app


DEFAULT_REPO_URL = "https://github.com/mdn/beginner-html-site-styled"
TERMINAL_ENRICHMENT_STATES = {"completed", "failed", "skipped"}
GUEST_HEADERS = {"X-Guest-Session": "live_repo_smoke_guest"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live repo-backed UXRay smoke test.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    parser.add_argument(
        "--custom-audience",
        default="A goal-driven evaluator checking clarity, trust, and obvious next steps.",
    )
    return parser.parse_args()


def _terminal(detail: dict) -> bool:
    if detail["status"] == "failed":
        return True
    return (
        detail["status"] in {"completed", "failed"}
        and detail["evaluation_status"] in TERMINAL_ENRICHMENT_STATES
        and detail["source_review_status"] in TERMINAL_ENRICHMENT_STATES
    )


def main() -> int:
    args = _parse_args()
    config = AppConfig.from_env()
    runtime_root = (Path("apps/api/data/test-runtime") / f"live-repo-smoke-{uuid.uuid4().hex}").resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_config = replace(
        config,
        db_path=runtime_root / "uxray-live-smoke.db",
        artifacts_dir=runtime_root / "artifacts",
        local_repo_build_root=runtime_root / "repo-builds",
        start_worker=True,
        queue_poll_seconds=0.25,
    )

    with TestClient(create_app(config=runtime_config)) as client:
        project_response = client.post(
            "/projects",
            json={"name": "Live repo smoke", "repo_url": args.repo_url},
            headers=GUEST_HEADERS,
        )
        project_response.raise_for_status()
        project_id = project_response.json()["data"]["id"]

        run_response = client.post(
            f"/projects/{project_id}/runs",
            json={"custom_audience": args.custom_audience},
            headers=GUEST_HEADERS,
        )
        run_response.raise_for_status()
        run_id = run_response.json()["data"]["id"]
        print(json.dumps({"project_id": project_id, "run_id": run_id, "repo_url": args.repo_url}))

        deadline = time.time() + args.timeout_seconds
        latest_detail: dict | None = None
        while time.time() < deadline:
            detail_response = client.get(f"/runs/{run_id}", headers=GUEST_HEADERS)
            detail_response.raise_for_status()
            latest_detail = detail_response.json()["data"]

            snapshot = {
                "status": latest_detail["status"],
                "repo_build_status": latest_detail["repo_build_status"],
                "target_source": latest_detail["target_source"],
                "target_url": latest_detail["target_url"],
                "local_preview_url": latest_detail.get("local_preview_url"),
                "public_preview_url": latest_detail.get("public_preview_url"),
                "evaluation_status": latest_detail["evaluation_status"],
                "source_review_status": latest_detail["source_review_status"],
                "issue_count": len(latest_detail["issues"]),
                "recommendation_count": len(latest_detail["recommendations"]),
            }
            print(json.dumps(snapshot))

            if _terminal(latest_detail):
                break
            time.sleep(2.0)

        if latest_detail is None:
            print(json.dumps({"error": "No run detail was returned."}))
            return 1
        if not _terminal(latest_detail):
            print(json.dumps({"error": "Timed out waiting for the live repo smoke run to finish."}))
            return 1

        source_recommendations = [
            recommendation
            for recommendation in latest_detail["recommendations"]
            if recommendation["source"] == "source_review_gpt"
        ]
        result = {
            "status": latest_detail["status"],
            "repo_build_status": latest_detail["repo_build_status"],
            "repo_build_error": latest_detail["repo_build_error"],
            "target_source": latest_detail["target_source"],
            "target_url": latest_detail["target_url"],
            "local_preview_url": latest_detail.get("local_preview_url"),
            "public_preview_url": latest_detail.get("public_preview_url"),
            "live_url": latest_detail["live_url"],
            "evaluation_status": latest_detail["evaluation_status"],
            "evaluation_error": latest_detail["evaluation_error"],
            "source_review_status": latest_detail["source_review_status"],
            "source_review_error": latest_detail["source_review_error"],
            "issue_count": len(latest_detail["issues"]),
            "recommendation_count": len(latest_detail["recommendations"]),
            "source_recommendation_count": len(source_recommendations),
            "source_recommendation_titles": [item["title"] for item in source_recommendations],
            "first_failing_stage": (
                "repo_build"
                if latest_detail["repo_build_status"] == "failed"
                else "browser_use"
                if latest_detail["status"] == "failed"
                else "evaluation"
                if latest_detail["evaluation_status"] == "failed"
                else "source_review"
                if latest_detail["source_review_status"] == "failed"
                else None
            ),
        }
        print(json.dumps(result, indent=2))

        success = (
            latest_detail["status"] == "completed"
            and latest_detail["repo_build_status"] == "completed"
            and latest_detail["target_source"] == "repo_preview"
            and bool(latest_detail["target_url"])
            and latest_detail["evaluation_status"] == "completed"
            and latest_detail["source_review_status"] == "completed"
            and len(source_recommendations) > 0
        )
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
