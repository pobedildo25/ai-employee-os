"""Smoke checks for Sprint D ops assets (docs + deploy scripts)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _assert_nonempty(path: Path) -> None:
    assert path.is_file(), f"missing: {path}"
    assert path.stat().st_size > 0, f"empty: {path}"


def test_ops_runbook_exists() -> None:
    path = REPO_ROOT / "docs" / "OPS_RUNBOOK.md"
    _assert_nonempty(path)
    text = path.read_text(encoding="utf-8")
    assert "TLS at edge" in text
    assert "Backups schedule" in text
    assert "Release / Rollback" in text
    assert "Celery" in text


def test_nginx_tls_config_exists() -> None:
    _assert_nonempty(REPO_ROOT / "deploy" / "nginx" / "nginx.conf")
    _assert_nonempty(REPO_ROOT / "deploy" / "nginx" / "nginx.conf.example")
    conf = (REPO_ROOT / "deploy" / "nginx" / "nginx.conf").read_text(encoding="utf-8")
    assert "listen 443 ssl" in conf
    assert "backend:8000" in conf


def test_backup_and_rollback_scripts_exist() -> None:
    for rel in (
        "deploy/backup_loop.sh",
        "deploy/rollback.sh",
        "deploy/tag_release.sh",
    ):
        _assert_nonempty(REPO_ROOT / rel)


def test_prod_compose_has_tls_and_backup_profiles() -> None:
    compose = (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "profiles: [\"tls\"]" in compose or "profiles: ['tls']" in compose
    assert "profiles: [\"backup\"]" in compose or "profiles: ['backup']" in compose
    assert "nginx:1.27-alpine" in compose
    assert "backup_loop.sh" in compose
