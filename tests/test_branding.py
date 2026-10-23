"""OpenSwing branding must keep OpenFlight credit and protocol identifiers intact."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_readme_credits_openflight_and_its_license():
    readme = _read("README.md")

    assert "ui/public/openswing-logo-light.svg" in readme
    assert "https://github.com/open-flight/openflight" in readme
    assert "based on [OpenFlight]" in readme
    assert "AGPL-3.0" in readme


def test_license_is_kept():
    assert _read("LICENSE").lstrip().startswith("GNU AFFERO GENERAL PUBLIC LICENSE")


def test_kiosk_splash_failure_messages_name_openswing():
    script = _read("scripts/start-kiosk.sh")

    for message in (
        '"OpenSwing preparation failed"',
        '"OpenSwing server timed out"',
        '"OpenSwing server exited during startup"',
        "then relaunch OpenSwing.",
    ):
        assert message in script
    for message in (
        "OpenFlight preparation failed",
        "relaunch OpenFlight",
        "OpenFlight server timed out",
    ):
        assert message not in script


def test_kiosk_copies_and_cleans_up_the_openswing_splash_logo():
    script = _read("scripts/start-kiosk.sh")

    assert 'cp "$splash_assets/openswing-logo-on-dark-transparent.svg"' in script
    assert 'rm -f "$STARTUP_RUNTIME_DIR/openswing-logo-on-dark-transparent.svg"' in script
    assert "openflightlogo.svg" not in script


def test_server_startup_messages_name_openswing():
    server = _read("src/openflight/server.py")

    assert 'startup_status.start("server", "Preparing OpenSwing server")' in server
    assert 'startup_status.start("server", "Starting OpenSwing server")' in server
    assert "relaunch OpenFlight" not in server


def test_protocol_identifiers_keep_the_openflight_name():
    """Phone, iOS, and simulator integrations match on these exact strings."""
    assert 'response.headers["OpenFlight-Features"]' in _read("src/openflight/server.py")
    assert 'device_id: str = "OpenFlight"' in _read("src/openflight/sim/config.py")
