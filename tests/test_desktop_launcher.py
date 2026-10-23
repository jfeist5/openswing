"""Contracts for the optional Raspberry Pi desktop launcher."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_LAUNCHER = REPO_ROOT / "scripts/setup/run-openflight.example.sh"
INSTALLER = REPO_ROOT / "scripts/setup/install_desktop_launcher.sh"


def install_suffix() -> str:
    """Return the launcher suffix derived from this checkout's folder name."""
    project_name = REPO_ROOT.name
    if project_name == "openflight":
        return ""
    if project_name.startswith("openflight-"):
        return project_name.removeprefix("openflight-")
    return project_name


def display_name(project_name: str) -> str:
    """Return the desktop label: OpenSwing, suffixed only for secondary checkouts."""
    if project_name in ("openswing", "openflight"):
        return "OpenSwing"
    for base in ("openswing-", "openflight-"):
        if project_name.startswith(base):
            return f"OpenSwing ({project_name.removeprefix(base)})"
    return f"OpenSwing ({project_name})"


def installed_paths(home: Path) -> tuple[Path, Path]:
    """Return the default launcher and desktop paths for this checkout."""
    suffix = install_suffix()
    launcher_name = "run-openflight.sh" if not suffix else f"run-openflight-{suffix}.sh"
    desktop_name = "OpenFlight.desktop" if not suffix else f"OpenFlight-{suffix}.desktop"
    return home / launcher_name, home / "Desktop" / desktop_name


pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="desktop launcher contract tests need bash",
)


def test_example_launcher_is_valid_and_uses_safe_defaults():
    subprocess.run(["bash", "-n", str(EXAMPLE_LAUNCHER)], check=True)

    launcher = EXAMPLE_LAUNCHER.read_text(encoding="utf-8")
    assert "flock -n" in launcher
    assert "--startup-splash" in launcher
    assert "    --calculated-spin" not in launcher
    assert "# --calculated-spin" in launcher
    assert "--ballistics" in launcher
    assert "# --debug" in launcher
    assert 'scripts/start-kiosk.sh "${openflight_args[@]}"' in launcher
    assert "lxterminal" not in launcher


def test_installer_creates_terminal_free_desktop_entry_and_preserves_launcher(tmp_path):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "OPENFLIGHT_DESKTOP_DIR": str(desktop),
        "OPENFLIGHT_SKIP_DESKTOP_TRUST": "true",
    }

    subprocess.run(["bash", str(INSTALLER)], check=True, cwd=REPO_ROOT, env=env)

    launcher_path, desktop_path = installed_paths(home)
    assert launcher_path.exists()
    assert os.access(launcher_path, os.X_OK)
    desktop_entry = desktop_path.read_text(encoding="utf-8")
    assert f"Exec=/bin/bash -ilc {launcher_path}" in desktop_entry
    assert "Terminal=false" in desktop_entry
    assert "StartupNotify=false" in desktop_entry
    assert "lxterminal" not in desktop_entry
    assert "/home/coleman" not in desktop_entry
    assert f"Icon={REPO_ROOT}/ui/public/openswing-icon.svg" in desktop_entry
    assert os.access(desktop_path, os.X_OK)
    assert f"openflight_installed_dir={REPO_ROOT}" in launcher_path.read_text(encoding="utf-8")

    assert f"Name={display_name(REPO_ROOT.name)}" in desktop_entry
    assert "Comment=Softball and golf launch monitor" in desktop_entry

    launcher_path.write_text("#!/bin/bash\n# local calibration\n", encoding="utf-8")
    repeated_install = subprocess.run(
        ["bash", str(INSTALLER)],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        input="n\n",
    )
    assert launcher_path.read_text(encoding="utf-8") == ("#!/bin/bash\n# local calibration\n")
    assert "Replace it? [y/N]" in repeated_install.stderr
    assert "Existing desktop entry preserved" in repeated_install.stdout


@pytest.mark.parametrize(
    ("checkout", "expected_name", "desktop_file"),
    [
        ("openswing", "OpenSwing", "OpenFlight-openswing.desktop"),
        ("openswing-dev", "OpenSwing (dev)", "OpenFlight-openswing-dev.desktop"),
        ("openflight", "OpenSwing", "OpenFlight.desktop"),
        ("openflight-dev", "OpenSwing (dev)", "OpenFlight-dev.desktop"),
        ("softball", "OpenSwing (softball)", "OpenFlight-softball.desktop"),
    ],
)
def test_desktop_label_is_openswing_while_file_names_stay_stable(
    tmp_path, checkout, expected_name, desktop_file
):
    """Reinstalling must update the existing launcher in place, so only the label changes."""
    setup_dir = tmp_path / checkout / "scripts/setup"
    setup_dir.mkdir(parents=True)
    shutil.copy(INSTALLER, setup_dir)
    shutil.copy(EXAMPLE_LAUNCHER, setup_dir)
    home = tmp_path / "home"
    env = {
        **os.environ,
        "HOME": str(home),
        "OPENFLIGHT_DESKTOP_DIR": str(home / "Desktop"),
        "OPENFLIGHT_SKIP_DESKTOP_TRUST": "true",
    }

    subprocess.run(
        ["bash", str(setup_dir / INSTALLER.name)], check=True, cwd=tmp_path / checkout, env=env
    )

    entry = (home / "Desktop" / desktop_file).read_text(encoding="utf-8")
    assert f"Name={expected_name}\n" in entry
    assert "Comment=Softball and golf launch monitor\n" in entry
    assert "OpenFlight" not in entry.split("Exec=")[0]


def test_desktop_entry_loads_interactive_shell_path(tmp_path):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    fake_bin = home / "interactive-bin"
    home.mkdir()
    fake_bin.mkdir()
    (home / ".bash_profile").write_text('source "$HOME/.bashrc"\n', encoding="utf-8")
    (home / ".bashrc").write_text(
        '[[ $- == *i* ]] || return\nexport PATH="$HOME/interactive-bin:$PATH"\n',
        encoding="utf-8",
    )
    npm = fake_bin / "npm"
    npm.write_text('#!/bin/bash\nprintf "npm-from-interactive-shell\\n"\n', encoding="utf-8")
    npm.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "OPENFLIGHT_DESKTOP_DIR": str(desktop),
        "OPENFLIGHT_SKIP_DESKTOP_TRUST": "true",
    }

    subprocess.run(["bash", str(INSTALLER)], check=True, cwd=REPO_ROOT, env=env)

    launcher_path, desktop_path = installed_paths(home)
    launcher_path.write_text("#!/bin/bash\nnpm --prefix ui run build\n", encoding="utf-8")
    launcher_path.chmod(0o755)
    exec_line = next(
        line.removeprefix("Exec=")
        for line in desktop_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Exec=")
    )
    result = subprocess.run(
        shlex.split(exec_line),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "npm-from-interactive-shell" in result.stdout


def test_installer_prompts_before_replacing_and_backs_up_existing_desktop_entry(tmp_path):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    desktop.mkdir(parents=True)
    _, desktop_path = installed_paths(home)
    existing_entry = "[Desktop Entry]\nName=My calibrated OpenFlight\n"
    desktop_path.write_text(existing_entry, encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "OPENFLIGHT_DESKTOP_DIR": str(desktop),
        "OPENFLIGHT_SKIP_DESKTOP_TRUST": "true",
    }

    preserved = subprocess.run(
        ["bash", str(INSTALLER)],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        input="n\n",
    )

    assert desktop_path.read_text(encoding="utf-8") == existing_entry
    assert "Existing desktop entry preserved" in preserved.stdout
    assert "Replace it? [y/N]" in preserved.stderr
    backup_pattern = f"{desktop_path.name}.backup-*"
    assert not list(desktop.glob(backup_pattern))

    subprocess.run(
        ["bash", str(INSTALLER)],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        input="y\n",
        text=True,
    )

    assert "Terminal=false" in desktop_path.read_text(encoding="utf-8")
    backups = list(desktop.glob(backup_pattern))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == existing_entry


def test_main_setup_uses_the_terminal_free_launcher_installer():
    setup_script = (REPO_ROOT / "scripts/setup/setup.sh").read_text(encoding="utf-8")

    assert '"$SCRIPT_DIR/install_desktop_launcher.sh"' in setup_script
