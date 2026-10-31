import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from niyam.db import audit
from niyam.db.session import get_engine

pytestmark = pytest.mark.db


@pytest.fixture
def conn():
    c = get_engine().connect()
    t = c.begin()
    yield c
    t.rollback()
    c.close()


def _card(status="draft", approved_by=None):
    return json.dumps({"id": "X-TEST", "approved_by": approved_by, "source": {"regulator": "RBI"}})


def _insert_rule(c, status, approved_by=None, sha="a" * 64):
    c.execute(text("INSERT INTO rule_cards (tenant_id,id,version,status,title,severity,tier,check_type,effective_from,regulator,card,card_sha256,validation) "
                   "VALUES ('t-inv','X-TEST',1,:s,'t','high','A','must_contain','2026-01-01','RBI',CAST(:c AS jsonb),:h,'{}'::jsonb)"),
              {"s": status, "c": _card(status, approved_by), "h": sha})


def test_active_card_requires_a_named_approver(conn):
    with pytest.raises(DBAPIError):
        _insert_rule(conn, "active", approved_by=None)


def test_active_card_is_immutable(conn):
    _insert_rule(conn, "active", approved_by="officer-1")
    with pytest.raises(DBAPIError):
        conn.execute(text("UPDATE rule_cards SET card_sha256=:h WHERE tenant_id='t-inv' AND id='X-TEST'"), {"h": "b" * 64})


def test_draft_card_can_change(conn):
    _insert_rule(conn, "draft")
    conn.execute(text("UPDATE rule_cards SET card_sha256=:h WHERE tenant_id='t-inv' AND id='X-TEST'"), {"h": "c" * 64})


def test_audit_log_is_append_only(conn):
    audit.append(conn, actor="test", action="t.a", object_type="t", object_id="1")
    for stmt in ("UPDATE audit_events SET actor='x'", "DELETE FROM audit_events", "TRUNCATE audit_events"):
        sp = conn.begin_nested()
        with pytest.raises(DBAPIError):
            conn.execute(text(stmt))
        sp.rollback()


def test_audit_chain_verifies_and_detects_nothing_broken(conn):
    for i in range(3):
        audit.append(conn, actor="test", action="t.chain", object_type="t", object_id=str(i), payload={"i": i})
    v = audit.verify_chain(conn)
    assert v["ok"] and v["events"] >= 3


def test_verdict_confidence_and_span_constraints(conn):
    run = uuid.uuid4()
    conn.execute(text("INSERT INTO check_runs (id,as_of,text_sha256,summary,engine_version,cards_snapshot,duration_ms) VALUES (:i,'2026-10-31',:h,'{}'::jsonb,'0','{}'::jsonb,1)"), {"i": run, "h": "d" * 64})
    base = dict(i=uuid.uuid4(), r=run)
    sp = conn.begin_nested()
    with pytest.raises(DBAPIError):          # confidence out of range
        conn.execute(text("INSERT INTO verdicts (id,run_id,rule_id,rule_version,rule_status,verdict,tier,confidence,reason) VALUES (:i,:r,'R',1,'draft','pass','A',1.5,'x')"), base)
    sp.rollback()
    sp = conn.begin_nested()
    with pytest.raises(DBAPIError):          # half a span
        conn.execute(text("INSERT INTO verdicts (id,run_id,rule_id,rule_version,rule_status,verdict,tier,confidence,reason,span_start) VALUES (:i,:r,'R',1,'draft','fail','A',1,'x',3)"), base)
    sp.rollback()
