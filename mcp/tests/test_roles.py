"""
Tests for the operator / machine token roles.

Needs the orchestrator's own dependencies (fastapi, httpx). Run with:
    cd mcp && python -m pytest tests -v
"""
import importlib.util
import json
import os
import pathlib

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

MACHINE = "machine-secret"
OPERATOR = "operator-secret"


def load(operator_token=OPERATOR):
    os.environ["PLUGIN_API_TOKEN"] = MACHINE
    if operator_token is None:
        os.environ.pop("PLUGIN_OPERATOR_TOKEN", None)
    else:
        os.environ["PLUGIN_OPERATOR_TOKEN"] = operator_token
    spec = importlib.util.spec_from_file_location("orch_main_roles", pathlib.Path(__file__).parent.parent / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeResp:
    def __init__(self, code, body):
        self.status_code, self._body = code, body
        self.text = json.dumps(body)

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._body


def client(mod):
    from fastapi.testclient import TestClient
    sent = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, timeout=None):
            sent.append((url, json))
            return FakeResp(200, {"status": "ok"})

    mod.httpx.AsyncClient = FakeClient
    return TestClient(mod.app), sent


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# every route that moves the machine or changes its setup
MACHINE_ONLY = [
    ("/machine/jog", {"axis": "X", "distance": 1, "confirm": True}),
    ("/machine/power", {"on": True, "confirm": True}),
    ("/machine/home", {"confirm": True}),
    ("/machine/gcode", {"gcode": "G0 X0", "confirm": True}),
    ("/machine/spindle", {"spindle_speed": 1000, "state": "on", "confirm": True}),
    ("/machine/estop", {"active": False, "confirm": True}),
    ("/machine/program/open", {"filename": "a.tap", "confirm": True}),
    ("/machine/program/run", {"line": 0, "confirm": True}),
    ("/machine/program/resume", {"confirm": True}),
    ("/machine/program/step", {"confirm": True}),
    ("/machine/program/rewind", {"confirm": True}),
    ("/machine/park", {"confirm": True}),
    ("/machine/goto-zero", {"confirm": True}),
    ("/machine/zero", {"axis": "X", "confirm": True}),
]

# what a remote operator may do: stop, slow down, look
OPEN_TO_EVERY_TOKEN = [
    ("/machine/estop", {"active": True}),
    ("/machine/override/feed", {"percent": 80}),
    ("/machine/override/spindle", {"percent": 80}),
    ("/machine/program/pause", {}),
    ("/machine/program/stop", {}),
]


@pytest.mark.parametrize("path,body", MACHINE_ONLY)
def test_operator_is_refused_on_machine_only_routes(path, body):
    c, sent = client(load())
    r = c.post(path, json=body, headers=auth(OPERATOR))
    assert r.status_code == 403
    assert "pantalla de la máquina" in r.json()["detail"]
    assert sent == []          # nothing reached the bridge


@pytest.mark.parametrize("path,body", MACHINE_ONLY)
def test_machine_token_is_accepted_on_machine_only_routes(path, body):
    c, sent = client(load())
    assert c.post(path, json=body, headers=auth(MACHINE)).status_code == 200
    assert len(sent) == 1


@pytest.mark.parametrize("path,body", OPEN_TO_EVERY_TOKEN)
@pytest.mark.parametrize("token", [MACHINE, OPERATOR])
def test_stop_and_overrides_are_open_to_every_token(path, body, token):
    c, sent = client(load())
    assert c.post(path, json=body, headers=auth(token)).status_code == 200
    assert len(sent) == 1


def test_whoami_reports_the_role():
    c, _ = client(load())
    assert c.get("/whoami", headers=auth(MACHINE)).json() == {"role": "machine", "operator_enabled": True}
    assert c.get("/whoami", headers=auth(OPERATOR)).json() == {"role": "operator", "operator_enabled": True}


@pytest.mark.parametrize("headers", [{}, auth("wrong"), auth("1234"), {"Authorization": "Basic abc"}])
def test_unknown_credentials_are_unauthorized(headers):
    c, _ = client(load())
    assert c.get("/whoami", headers=headers).status_code == 401
    assert c.post("/machine/program/stop", json={}, headers=headers).status_code == 401


def test_without_an_operator_token_nothing_changes():
    c, sent = client(load(operator_token=None))
    assert c.get("/whoami", headers=auth(MACHINE)).json() == {"role": "machine", "operator_enabled": False}
    for path, body in MACHINE_ONLY:
        assert c.post(path, json=body, headers=auth(MACHINE)).status_code == 200
    assert c.post("/machine/jog", json={"axis": "X", "distance": 1}, headers=auth(OPERATOR)).status_code == 401


def test_an_operator_token_equal_to_the_machine_token_is_ignored():
    mod = load(operator_token=MACHINE)
    assert mod.PLUGIN_OPERATOR_TOKEN == ""
    c, _ = client(mod)
    assert c.get("/whoami", headers=auth(MACHINE)).json()["role"] == "machine"


def test_the_operator_can_still_read():
    c, _ = client(load())
    # the bridge is faked, but authentication happens first and must let the operator through
    r = c.get("/tools", headers=auth(OPERATOR))
    assert r.status_code != 401 and r.status_code != 403


def test_bridge_errors_keep_their_status_for_the_operator_overrides():
    mod = load()
    c, _ = client(mod)

    class Failing:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, timeout=None):
            return FakeResp(422, {"detail": "override must be a whole number between 0 and 200"})

    mod.httpx.AsyncClient = Failing
    r = c.post("/machine/override/feed", json={"percent": 80}, headers=auth(OPERATOR))
    assert r.status_code == 422
