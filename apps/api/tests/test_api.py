from __future__ import annotations

import time

GUEST_HEADERS = {"X-Guest-Session": "guest_test_session"}
USER_A_HEADERS = {"Authorization": "Bearer token-user-a"}
USER_B_HEADERS = {"Authorization": "Bearer token-user-b"}


def test_health_endpoint(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["browser_use_model"] == "claude-sonnet-4.6"
    assert response.json()["data"]["fetch_evaluation_enabled"] is False
    assert response.json()["data"]["source_review_enabled"] is True


def test_create_project_and_run_lifecycle(client, fake_adapter, fake_repo_builder, fake_source_reviewer) -> None:
    project_response = client.post(
        "/projects",
        json={
            "name": "UXRay Demo",
            "url": "https://example.com",
            "repo_url": "https://github.com/example/repo",
        },
        headers=GUEST_HEADERS,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    run_response = client.post(
        f"/projects/{project_id}/runs",
        json={"custom_audience": "B2B buyer comparing vendor trust and ROI"},
        headers=GUEST_HEADERS,
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["data"]["id"]

    deadline = time.time() + 5
    latest_payload: dict | None = None

    while time.time() < deadline:
        latest = client.get(f"/runs/{run_id}", headers=GUEST_HEADERS)
        assert latest.status_code == 200
        latest_payload = latest.json()["data"]
        if latest_payload["status"] == "completed" and latest_payload["source_review_status"] == "completed":
            break
        time.sleep(0.05)

    assert latest_payload is not None
    assert latest_payload["status"] == "completed"
    assert latest_payload["live_url"] == "https://browser-use.example/live-session/first_time_visitor"
    assert latest_payload["target_url"] == "http://127.0.0.1:4100"
    assert latest_payload["target_source"] == "repo_preview"
    assert latest_payload["browser_use_model"] == "claude-sonnet-4.6"
    assert latest_payload["evaluation_status"] == "skipped"
    assert latest_payload["evaluation_error"] is None
    assert latest_payload["source_review_status"] == "completed"
    assert latest_payload["source_review_error"] is None
    assert latest_payload["repo_build_status"] == "completed"
    assert latest_payload["repo_build_error"] is None
    assert latest_payload["custom_audience"] == "B2B buyer comparing vendor trust and ROI"
    assert len(latest_payload["issues"]) == 2
    assert sorted(latest_payload["issues"][0]["personas"]) == [
        "custom_audience",
        "first_time_visitor",
        "intent_driven",
        "trust_evaluator",
    ]
    assert len(latest_payload["recommendations"]) == 3
    assert latest_payload["evaluations"] == []
    assert len(latest_payload["persona_sessions"]) == 4
    assert latest_payload["persona_sessions"][0]["progress"][0]["summary"].endswith(
        "submitting Browser Use cloud run request"
    )
    assert any(
        event["summary"] == "Starting multi-persona Browser Use audit with 4 persona sessions."
        for event in latest_payload["progress"]
    )
    assert fake_adapter.calls[0]["project_url"] == "http://127.0.0.1:4100"
    assert fake_adapter.calls[0]["model"] == "claude-sonnet-4.6"
    assert fake_adapter.calls[-1]["custom_audience"] == "B2B buyer comparing vendor trust and ROI"
    assert fake_repo_builder.calls[0]["repo_url"] == "https://github.com/example/repo"
    assert fake_source_reviewer.calls[0]["framework"] == "vite"

    runs_response = client.get(f"/projects/{project_id}/runs", headers=GUEST_HEADERS)
    assert runs_response.status_code == 200
    assert runs_response.json()["data"][0]["id"] == run_id
    assert runs_response.json()["data"][0]["target_url"] == "http://127.0.0.1:4100"
    assert runs_response.json()["data"][0]["target_source"] == "repo_preview"
    assert runs_response.json()["data"][0]["browser_use_model"] == "claude-sonnet-4.6"
    assert runs_response.json()["data"][0]["evaluation_status"] == "skipped"
    assert runs_response.json()["data"][0]["evaluation_error"] is None
    assert runs_response.json()["data"][0]["source_review_status"] == "completed"
    assert runs_response.json()["data"][0]["source_review_error"] is None
    assert runs_response.json()["data"][0]["repo_build_status"] == "completed"
    assert runs_response.json()["data"][0]["repo_build_error"] is None
    assert runs_response.json()["data"][0]["custom_audience"] == "B2B buyer comparing vendor trust and ROI"


def test_create_project_rejects_invalid_url(client) -> None:
    response = client.post(
        "/projects",
        json={"name": "Bad Demo", "url": "not-a-url"},
        headers=GUEST_HEADERS,
    )

    assert response.status_code == 422


def test_create_project_accepts_public_repo_without_site_url(client) -> None:
    response = client.post(
        "/projects",
        json={"name": "Repo Only", "repo_url": "https://github.com/example/repo"},
        headers=GUEST_HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["data"]["url"] is None
    assert response.json()["data"]["repo_url"] == "https://github.com/example/repo"


def test_run_falls_back_to_site_url_when_repo_preview_fails(client, fake_adapter, fake_repo_builder) -> None:
    repo_url = "https://github.com/example/repo"
    fake_repo_builder.fail_repos.add(repo_url)

    project_response = client.post(
        "/projects",
        json={"name": "Fallback Demo", "url": "https://example.com", "repo_url": repo_url},
        headers=GUEST_HEADERS,
    )
    project_id = project_response.json()["data"]["id"]

    run_response = client.post(f"/projects/{project_id}/runs", json={}, headers=GUEST_HEADERS)
    run_id = run_response.json()["data"]["id"]

    deadline = time.time() + 5
    latest_payload: dict | None = None
    while time.time() < deadline:
        latest = client.get(f"/runs/{run_id}", headers=GUEST_HEADERS)
        latest_payload = latest.json()["data"]
        if latest_payload["status"] == "completed":
            break
        time.sleep(0.05)

    assert latest_payload is not None
    assert latest_payload["status"] == "completed"
    assert latest_payload["target_source"] == "site"
    assert latest_payload["target_url"] == "https://example.com/"
    assert latest_payload["repo_build_status"] == "failed"
    assert "Local repo preview failed" in latest_payload["repo_build_error"]
    assert fake_adapter.calls[0]["project_url"] == "https://example.com/"


def test_artifact_route_serves_file_from_artifacts_dir(client) -> None:
    file_path = client.app.state.config.artifacts_dir / "inline.png"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"fake-image")

    response = client.get("/artifacts/inline.png")

    assert response.status_code == 200
    assert response.content == b"fake-image"


def test_run_continues_when_one_persona_exhausts_invalid_output_retry(client, fake_adapter) -> None:
    fake_adapter.invalid_output_personas.add("trust_evaluator")

    project_response = client.post(
        "/projects",
        json={
            "name": "UXRay Demo",
            "url": "https://example.com",
        },
        headers=GUEST_HEADERS,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    run_response = client.post(f"/projects/{project_id}/runs", json={}, headers=GUEST_HEADERS)
    assert run_response.status_code == 201
    run_id = run_response.json()["data"]["id"]

    deadline = time.time() + 5
    latest_payload: dict | None = None

    while time.time() < deadline:
        latest = client.get(f"/runs/{run_id}", headers=GUEST_HEADERS)
        assert latest.status_code == 200
        latest_payload = latest.json()["data"]
        if latest_payload["status"] == "completed":
            break
        time.sleep(0.05)

    assert latest_payload is not None
    assert latest_payload["status"] == "completed"
    trust_session = next(
        session for session in latest_payload["persona_sessions"] if session["persona_key"] == "trust_evaluator"
    )
    assert trust_session["status"] == "failed"
    assert trust_session["result_mode"] == "failed"
    assert "Browser Use returned invalid structured output after 3 attempts" in trust_session["error_message"]
    assert len(latest_payload["issues"]) >= 1


def test_run_continues_with_salvaged_persona_evidence(client, fake_adapter) -> None:
    fake_adapter.salvaged_personas.add("trust_evaluator")

    project_response = client.post(
        "/projects",
        json={
            "name": "UXRay Demo",
            "url": "https://example.com",
        },
        headers=GUEST_HEADERS,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    run_response = client.post(f"/projects/{project_id}/runs", json={}, headers=GUEST_HEADERS)
    assert run_response.status_code == 201
    run_id = run_response.json()["data"]["id"]

    deadline = time.time() + 5
    latest_payload: dict | None = None

    while time.time() < deadline:
        latest = client.get(f"/runs/{run_id}", headers=GUEST_HEADERS)
        assert latest.status_code == 200
        latest_payload = latest.json()["data"]
        if latest_payload["status"] == "completed":
            break
        time.sleep(0.05)

    assert latest_payload is not None
    assert latest_payload["status"] == "completed"
    trust_session = next(
        session for session in latest_payload["persona_sessions"] if session["persona_key"] == "trust_evaluator"
    )
    assert trust_session["status"] == "completed"
    assert trust_session["result_mode"] == "salvaged"
    assert any(
        event["summary"] == "Continuing with fallback persona evidence for 1 persona session."
        for event in latest_payload["progress"]
    )


def test_authenticated_projects_are_scoped_per_user(client) -> None:
    project_response = client.post(
        "/projects",
        json={"name": "User A Project", "url": "https://example.com"},
        headers=USER_A_HEADERS,
    )

    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    own_list = client.get("/projects", headers=USER_A_HEADERS)
    assert own_list.status_code == 200
    assert [project["id"] for project in own_list.json()["data"]] == [project_id]

    other_list = client.get("/projects", headers=USER_B_HEADERS)
    assert other_list.status_code == 200
    assert other_list.json()["data"] == []

    other_project = client.get(f"/projects/{project_id}", headers=USER_B_HEADERS)
    assert other_project.status_code == 404


def test_api_requires_auth_or_guest_session(client) -> None:
    response = client.get("/projects")

    assert response.status_code == 401
