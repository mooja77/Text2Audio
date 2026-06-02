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
