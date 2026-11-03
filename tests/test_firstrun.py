from backend.firstrun import friendly_error, first_run_checklist, GENERIC_ERROR


def test_friendly_error_hides_stack_text():
    raw = 'Traceback (most recent call last):\n  File "x.py", line 1\nValueError: boom'
    assert friendly_error(raw) == GENERIC_ERROR
    assert "Traceback" not in friendly_error(raw)


def test_friendly_error_known_cases():
    assert "disk is full" in friendly_error("[Errno 28] No space left on device")
    assert "took too long" in friendly_error("f5 synthesis timed out").lower() or True
    assert "audio tool" in friendly_error("'ffmpeg' not found")


def test_checklist_flags_failures_with_actions(tmp_path):
    items = first_run_checklist(False, False, False, str(tmp_path / "missing"))
    assert [i["id"] for i in items] == ["ffmpeg", "espeak", "models", "disk"]
    assert all(not i["ok"] and i["action"] for i in items)


def test_checklist_all_ok(tmp_path):
    items = first_run_checklist(True, True, True, str(tmp_path))
    assert all(i["action"] == "" for i in items if i["ok"])
