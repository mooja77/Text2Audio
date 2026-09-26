from backend.pronunciations import PronunciationStore


def test_set_get_remove(tmp_path):
    store = PronunciationStore(str(tmp_path / "p.json"))
    assert store.get_all() == {}
    store.set_rule("Carrigaline", "Carrig a line")
    assert store.get_all() == {"carrigaline": "Carrig a line"}  # key lowercased
    store.set_rule("carrigaline", "Carrig-a-leen")  # overwrite
    assert store.get_all()["carrigaline"] == "Carrig-a-leen"
    store.remove("CARRIGALINE")
    assert store.get_all() == {}


def test_remove_missing_is_idempotent(tmp_path):
    store = PronunciationStore(str(tmp_path / "p.json"))
    store.remove("nope")  # no error
    assert store.get_all() == {}


def test_persists_across_instances(tmp_path):
    p = str(tmp_path / "p.json")
    PronunciationStore(p).set_rule("Foo", "Bar")
    assert PronunciationStore(p).get_all() == {"foo": "Bar"}


def test_corrupt_file_self_heals(tmp_path):
    p = str(tmp_path / "p.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{ not valid json")
    store = PronunciationStore(p)
    assert store.get_all() == {}          # doesn't crash on the hot path
    store.set_rule("foo", "bar")          # and editing still works (overwrites)
    assert PronunciationStore(p).get_all() == {"foo": "bar"}


def test_wrong_json_shape_is_treated_as_empty(tmp_path):
    p = tmp_path / "p.json"
    p.write_text('["not", "a", "mapping"]', encoding="utf-8")
    store = PronunciationStore(str(p))
    assert store.get_all() == {}
    store.set_rule("Name", "Naim")
    assert store.get_all() == {"name": "Naim"}
    assert not (tmp_path / "p.json.tmp").exists()
