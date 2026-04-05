from app.services.preview_tunnel import CloudflaredTunnelManager


def test_tunnel_manager_returns_local_url_when_disabled() -> None:
    manager = CloudflaredTunnelManager(enabled=False, binary="cloudflared")

    assert manager.expose("http://127.0.0.1:4100") == "http://127.0.0.1:4100"


def test_tunnel_manager_raises_clear_error_when_binary_missing() -> None:
    manager = CloudflaredTunnelManager(enabled=True, binary="definitely-not-installed-cloudflared")

    try:
        manager.expose("http://127.0.0.1:4100")
    except RuntimeError as exc:
        assert "requires 'definitely-not-installed-cloudflared' on PATH" in str(exc)
    else:
        raise AssertionError("Expected missing tunnel binary to raise RuntimeError")
