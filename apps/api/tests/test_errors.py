import os
from pathlib import Path

os.environ.setdefault("NIYAM_DATA_ROOT", str(Path(__file__).resolve().parents[3]))
from fastapi import HTTPException
from fastapi.testclient import TestClient


def test_error_detail_fields_are_passed_through():
    from niyam.main import app

    @app.get("/_t409")
    def _t():  # noqa: ANN202
        raise HTTPException(409, detail={"code": "stale_text_remains", "message": "m", "stale_text_remains": [{"finding_id": "f", "quote": "q"}]})

    r = TestClient(app).get("/_t409")
    assert r.status_code == 409 and r.json()["error"]["stale_text_remains"][0]["quote"] == "q" and r.json()["error"]["code"] == "stale_text_remains"
