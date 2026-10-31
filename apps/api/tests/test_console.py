from fastapi.testclient import TestClient

from niyam.config import get_settings
from niyam.main import app


def test_no_console_keeps_unknown_paths_404():
    with TestClient(app) as c:
        r = c.get("/overview")
        assert r.status_code == 404
        assert c.get("/healthz").json() == {"ok": True}


def test_console_spa_when_configured(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html>niyam-console")
    (tmp_path / "favicon.svg").write_text("<svg></svg>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "x.js").write_text("ok")
    monkeypatch.setattr(get_settings(), "console_dir", str(tmp_path))
    with TestClient(app) as c:
        assert "niyam-console" in c.get("/").text
        assert "niyam-console" in c.get("/overview").text
        assert c.get("/assets/x.js").text == "ok"
        assert c.get("/favicon.svg").text.startswith("<svg")
        assert c.get("/healthz").json() == {"ok": True}
        assert c.get("/api/nope").status_code == 404
