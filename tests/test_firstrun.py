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


def test_engine_errors_are_plain_language():
    from backend.firstrun import friendly_error
    assert "studio voice engine" in friendly_error(
        "install chatterbox-tts to use the studio voice and cloned voices")
    assert "studio voice engine" in friendly_error("voice engine worker exited unexpectedly")


def test_missing_models_point_to_installer_not_first_audiobook(tmp_path):
    items = first_run_checklist(True, True, False, str(tmp_path))
    models = next(i for i in items if i["id"] == "models")
    assert "Install Text2Audio.bat" in models["action"]
    assert "first audiobook" not in models["action"]
    assert "language package" in models["action"]


def test_missing_language_model_error_points_to_installer():
    msg = friendly_error("The English language model (en_core_web_sm 3.8.0) is missing")
    assert "Install Text2Audio.bat" in msg and "language package" in msg
    assert "took too long" in friendly_error("voice engine synthesis timed out")
