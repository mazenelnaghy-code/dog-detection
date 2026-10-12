from dog_repeller.dashboard import DashboardState, create_app


def client(token=""):
    state = DashboardState()
    return state, create_app(state, token).test_client()


def test_status_and_page():
    state, c = client()
    state.update(b"jpeg", {"level": "DANGER", "dogs": 1})
    assert c.get("/api/status").get_json() == {"level": "DANGER", "dogs": 1}
    assert b"stream.mjpg" in c.get("/").data


def test_commands_are_queued_once():
    state, c = client()
    assert c.post("/api/arm").status_code == 202
    assert c.post("/api/test").status_code == 202
    assert c.post("/api/explode").status_code == 404
    assert state.pop_commands() == ["arm", "test"]
    assert state.pop_commands() == []


def test_token_protects_everything_but_the_page():
    state, c = client(token="s3cret")
    assert c.get("/").status_code == 200
    assert c.get("/api/status").status_code == 401
    assert c.post("/api/disarm").status_code == 401
    assert c.post("/api/disarm?token=wrong").status_code == 401
    assert c.post("/api/disarm?token=s3cret").status_code == 202
    assert c.post("/api/arm", headers={"X-Token": "s3cret"}).status_code == 202
    assert state.pop_commands() == ["disarm", "arm"]


def test_wait_frame_returns_new_frames_only():
    state = DashboardState()
    state.update(b"a", {})
    seq, jpeg = state.wait_frame(-1, timeout=0.1)
    assert jpeg == b"a"
    assert state.wait_frame(seq, timeout=0.05) == (seq, None)
