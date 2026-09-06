"""Server tests: REST endpoints, synchronous job run, WebSocket
subscribe/broadcast round trip, static assets from view-sweep and the
dashboard tree.

Jobs run the fast registry models against the bundled Prius IGBT.
"""

from __future__ import annotations

import queue
import threading
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import pytest

if not find_spec("fastapi"):
    pytest.skip("requires heatsweep[server] (fastapi not installed)", allow_module_level=True)

from fastapi.testclient import TestClient

from heatsweep.server.app import ServerSettings, create_app, load_device_catalogue

DEVICE_DIR = Path(__file__).resolve().parent.parent / "devices"

OP: dict[str, Any] = {
    "f_sw_Hz": 5000.0, "V_dc": 500.0, "I_phase_rms": 100.0,
    "f_out_Hz": 50.0, "pf": 0.9, "m_index": 0.8,
}


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(ServerSettings(devices_dir=DEVICE_DIR, output_dir=tmp_path / "results"))
    with TestClient(app) as c:
        yield c


def submit(client: TestClient, model: str = "semiconductor_loss", **extra: Any) -> dict[str, Any]:
    body = {"device": "prius_2004_igbt", "model": model, "op": OP, **extra}
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def ws_receive_json(ws, timeout_s: float = 30.0):
    """WebSocketTestSession.receive_json blocks forever; bound it so a
    server that never sends fails the test instead of hanging it."""
    out: queue.Queue = queue.Queue()

    def _recv() -> None:
        try:
            out.put(("ok", ws.receive_json()))
        except BaseException as e:  # relayed to the test thread
            out.put(("err", e))

    threading.Thread(target=_recv, daemon=True).start()
    try:
        kind, val = out.get(timeout=timeout_s)
    except queue.Empty:
        pytest.fail(f"no WebSocket message within {timeout_s}s")
    if kind == "err":
        raise val
    return val


# -- catalogue ----------------------------------------------------------------

def test_models_lists_registry(client: TestClient) -> None:
    models = client.get("/api/models").json()
    names = {m["name"] for m in models}
    assert {"semiconductor_loss", "thermal"} <= names
    sl = next(m for m in models if m["name"] == "semiconductor_loss")
    assert "p_total_W" in sl["produces"]
    assert sl["units"]["p_total_W"] == "W"
    assert sl["version"] >= 1


def test_assemblies_lists_bundled_device(client: TestClient) -> None:
    entries = client.get("/api/assemblies").json()
    by_name = {e["name"]: e for e in entries}
    prius = by_name["prius_2004_igbt"]
    assert prius["device"]["device_type"] == "igbt"
    assert prius["device"]["Rth_jc"] > 0
    assert prius["thermal_stack"] is not None and prius["thermal_stack"].endswith("thermal_stack.toml")
    assert "half_bridge" in prius["topologies"]


def test_load_device_catalogue_skips_invalid(tmp_path: Path) -> None:
    (tmp_path / "bad.toml").write_text("[device]\nname = 'no sections'\n")
    (tmp_path / "prius_2004_igbt").mkdir()
    for f in ("prius_2004_igbt.toml", "thermal_stack.toml"):
        (tmp_path / "prius_2004_igbt" / f).write_bytes((DEVICE_DIR / "prius_2004_igbt" / f).read_bytes())
    cat = load_device_catalogue(tmp_path)
    assert set(cat) == {"prius_2004_igbt"}
    assert cat["prius_2004_igbt"].stack_path is not None
    assert load_device_catalogue(tmp_path / "missing") == {}


# -- results ------------------------------------------------------------------

def test_results_empty_store(client: TestClient) -> None:
    assert client.get("/api/results").json() == []
    assert client.get("/api/results/deadbeef0000").status_code == 404


def test_job_runs_and_stores_result(client: TestClient) -> None:
    job = submit(client)
    assert job["status"] == "completed"
    assert job["metrics"]["p_total_W"] > 0
    rid = job["result_id"]

    slim = client.get("/api/results").json()
    assert [s["config_id"] for s in slim] == [rid]
    assert slim[0]["model"] == "semiconductor_loss"
    assert slim[0]["assembly_name"] == "prius_2004_igbt_half_bridge"
    assert slim[0]["metrics"]["p_total_W"] == pytest.approx(job["metrics"]["p_total_W"])

    full = client.get(f"/api/results/{rid}").json()
    assert full["result_id"] == rid
    assert full["status"] == "OK"
    assert full["model_version"] == 1
    assert full["config"]["assembly"]["topology"] == "half_bridge"
    assert len(full["config"]["assembly"]["devices"]) == 2

    assert client.get("/api/results", params={"model": "thermal"}).json() == []
    assert client.get("/api/results", params={"assembly_config_id": job["assembly_config_id"]}).json() != []


def test_job_thermal_three_phase(client: TestClient) -> None:
    job = submit(client, model="thermal", topology="three_phase_bridge", Rth_cs=0.3, Rth_sa=0.05)
    assert job["status"] == "completed"
    m = job["metrics"]
    assert m["converged"] is True
    assert m["T_sink_C"] > 25.0
    assert m["Q1_high_Tj_C"] > m["T_sink_C"]
    full = client.get(f"/api/results/{job['result_id']}").json()
    assert len(full["config"]["assembly"]["devices"]) == 6
    assert full["config"]["assembly"]["Rth_sa"] == pytest.approx(0.05)


def test_job_response_carries_result_id_and_status(client: TestClient) -> None:
    """The dashboard selects the new result from the POST response alone
    (the WS frame is optional), so the body must carry both fields."""
    job = submit(client, job_id="job-R")
    assert job["job_id"] == "job-R"
    assert job["status"] == "completed"
    assert isinstance(job["result_id"], str) and len(job["result_id"]) == 12
    assert client.get(f"/api/results/{job['result_id']}").status_code == 200


def test_job_model_error_stored_and_broadcast(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A model that raises yields an ERROR record in the store, a 200
    ``failed`` response (not 201), and a ``job_failed`` frame."""
    import dataclasses

    from heatsweep.registry import MODEL_REGISTRY

    def boom(config: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic model failure")

    monkeypatch.setitem(MODEL_REGISTRY, "semiconductor_loss",
                        dataclasses.replace(MODEL_REGISTRY["semiconductor_loss"], fn=boom))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "job_ids": ["job-F"]})
        r = client.post("/api/jobs", json={"device": "prius_2004_igbt", "model": "semiconductor_loss",
                                           "op": OP, "job_id": "job-F"})
        msg = ws_receive_json(ws)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "failed"
    assert job["metrics"] is None
    assert "synthetic model failure" in job["error"]
    assert msg == {"type": "job_failed", "job_id": "job-F", "error": job["error"]}
    full = client.get(f"/api/results/{job['result_id']}").json()
    assert full["status"] == "ERROR"
    assert "synthetic model failure" in full["error_msg"]


def test_assemblies_paths_relative_to_catalogue(client: TestClient) -> None:
    prius = next(e for e in client.get("/api/assemblies").json() if e["name"] == "prius_2004_igbt")
    assert prius["path"] == "prius_2004_igbt/prius_2004_igbt.toml"
    assert prius["thermal_stack"] == "prius_2004_igbt/thermal_stack.toml"


def test_job_rejections(client: TestClient) -> None:
    assert client.post("/api/jobs", json={"model": "thermal"}).status_code == 422
    assert client.post("/api/jobs", json={"device": "prius_2004_igbt", "model": "thermal"}).status_code == 422
    assert client.post("/api/jobs", json={"device": "nope", "model": "thermal", "op": OP}).status_code == 404
    assert client.post("/api/jobs", json={"device": "prius_2004_igbt", "model": "nope", "op": OP}).status_code == 404
    bad_op = {**OP, "pf": 1.5}
    r = client.post("/api/jobs", json={"device": "prius_2004_igbt", "model": "thermal", "op": bad_op})
    assert r.status_code == 400 and "pf" in r.json()["detail"]
    r = client.post("/api/jobs", json={"device": "prius_2004_igbt", "model": "thermal", "op": OP, "topology": "ring"})
    assert r.status_code == 400 and "topology" in r.json()["detail"]
    assert client.get("/api/results").json() == []


# -- websocket ----------------------------------------------------------------

def test_ws_subscribe_broadcast_round_trip(client: TestClient) -> None:
    """Subscribe to a client-chosen job id, run the job over REST, receive
    the job_complete frame carrying the stored result id."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "job_ids": ["job-A"]})
        other = submit(client, job_id="job-B", topology="full_bridge")
        watched = submit(client, job_id="job-A")
        msg = ws_receive_json(ws)
    assert msg == {"type": "job_complete", "job_id": "job-A", "result_ids": [watched["result_id"]]}
    assert other["result_id"] != watched["result_id"]


def test_ws_rejects_cross_origin(client: TestClient) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
            "/ws", headers={"origin": "http://evil.example"}):
        pass


def test_host_guard(client: TestClient) -> None:
    assert client.get("/api/models", headers={"host": "evil.example"}).status_code == 400


# -- static -------------------------------------------------------------------

def test_static_assets_serve(client: TestClient) -> None:
    css = client.get("/view-sweep/css/viewsweep.css")
    assert css.status_code == 200 and "--vs-" in css.text
    assert client.get("/view-sweep/js/providers/websocket.js").status_code == 200
    assert client.get("/view-sweep/spec/palettes/engineering.json").status_code == 200
    index = client.get("/")
    assert index.status_code == 200 and "heat-sweep" in index.text
    assert "/view-sweep/css/viewsweep.css" in index.text
    js = client.get("/app.js")
    assert js.status_code == 200 and "FetchProvider" in js.text
