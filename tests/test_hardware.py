"""GPU detection tests. Everything is mocked: no real hardware is touched."""
import json
import subprocess
from types import SimpleNamespace

from backend import hardware


def _smi(stdout, returncode=0):
    # Existing fixtures model idle cards; real queries also return free memory.
    stdout = "\n".join(line + ", " + line.rpartition(",")[2]
                       if line.count(",") == 1 else line for line in stdout.splitlines())
    return lambda cmd, **kw: SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


def _torch(available=True, name="Fake GPU", gib=8):
    props = SimpleNamespace(name=name, total_memory=int(gib * 1024**3))
    cuda = SimpleNamespace(is_available=lambda: available,
                           get_device_properties=lambda i: props,
                           mem_get_info=lambda i: (props.total_memory, props.total_memory))
    return SimpleNamespace(cuda=cuda)


def test_six_gb_gpu_is_usable_and_saved(tmp_path):
    path = tmp_path / "settings.json"
    report = hardware.check_and_save(path, run=_smi("NVIDIA GeForce GTX 1660, 6144\n"))
    assert report.usable is True and report.vram_gb == 6.0
    assert report.name == "NVIDIA GeForce GTX 1660"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["gpu_usable"] is True and saved["gpu_vram_gb"] == 6.0


def test_missing_nvidia_smi_is_not_usable_with_plain_message(tmp_path):
    def missing(cmd, **kw):
        raise FileNotFoundError("nvidia-smi")
    path = tmp_path / "settings.json"
    report = hardware.check_and_save(path, run=missing)
    assert report.usable is False
    assert "No NVIDIA graphics card" in report.message
    assert "Traceback" not in report.message
    assert json.loads(path.read_text(encoding="utf-8"))["gpu_usable"] is False


def test_failing_or_garbled_or_timed_out_nvidia_smi(tmp_path):
    assert hardware.detect_with_nvidia_smi(_smi("", returncode=9)).usable is False
    assert hardware.detect_with_nvidia_smi(_smi("garbage")).usable is False
    assert hardware.detect_with_nvidia_smi(_smi("GPU, notanumber")).usable is False

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)
    assert hardware.detect_with_nvidia_smi(slow).usable is False


def test_too_little_memory_is_not_usable():
    report = hardware.detect_with_nvidia_smi(_smi("Old Card, 2048"))
    assert report.usable is False and report.vram_gb == 2.0
    assert "needs at least" in report.message


def test_largest_of_several_gpus_is_chosen():
    report = hardware.detect_with_nvidia_smi(_smi("Small, 4096\nBig, 24576\n"))
    assert report.name == "Big" and report.vram_gb == 24.0


def test_post_install_uses_torch(tmp_path):
    report = hardware.check_and_save(tmp_path / "s.json", post_install=True,
                                     torch_module=_torch(gib=6))
    assert report.usable is True and report.source == "torch" and report.vram_gb == 6.0
    assert hardware.detect_gpu(True, torch_module=_torch(available=False)).usable is False


def test_post_install_torch_errors_are_swallowed():
    broken = SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: (_ for _ in ()).throw(RuntimeError("cuda init failed"))))
    report = hardware.detect_gpu(True, torch_module=broken)
    assert report.usable is False and "cuda init" not in report.message


def test_missing_settings_file_gives_safe_default(tmp_path):
    missing = tmp_path / "nope" / "settings.json"
    assert hardware.read_settings(missing) == {}
    assert hardware.gpu_usable_from_settings(missing) is False


def test_malformed_settings_file_gives_safe_default(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")
    assert hardware.read_settings(path) == {}
    path.write_text("[1, 2]", encoding="utf-8")
    assert hardware.read_settings(path) == {}


def test_write_keeps_other_settings_and_roundtrips(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"port": 8765}), encoding="utf-8")
    hardware.check_and_save(path, run=_smi("Card, 8192"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["port"] == 8765 and data["gpu_usable"] is True
    assert hardware.gpu_usable_from_settings(path) is True


def test_unwritable_settings_does_not_raise(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    report = hardware.check_and_save(blocker / "settings.json", run=_smi("Card, 8192"))
    assert report.usable is True


def test_cli_prints_plain_message_and_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hardware.subprocess, "run", _smi("Card, 6144"))
    path = tmp_path / "s.json"
    assert hardware.main(["--settings", str(path)]) == 0
    assert "6.0 GB" in capsys.readouterr().out
    assert json.loads(path.read_text(encoding="utf-8"))["gpu_usable"] is True

def test_busy_gpu_uses_fast_voices_instead_of_promising_studio():
    # Real query contract: name,total MiB,free MiB. Total VRAM is not free VRAM.
    def probe(cmd, **kw):
        text = "Busy Card, 24576, 2048\n" if "memory.free" in " ".join(cmd) else "Busy Card, 24576\n"
        return SimpleNamespace(returncode=0, stdout=text, stderr="")
    report = hardware.detect_with_nvidia_smi(probe)
    assert report.usable is False
    assert "free" in report.message.lower()


def test_four_gb_card_cannot_fit_the_documented_studio_peak():
    assert hardware.detect_with_nvidia_smi(_smi("Small, 4096\n")).usable is False


def test_post_install_busy_gpu_and_invalid_memory_are_safe():
    torch = _torch(gib=24)
    torch.cuda.mem_get_info = lambda i: (2 * 1024**3, 24 * 1024**3)
    assert hardware.detect_with_torch(torch).usable is False
    for text in ("Card, 24576, nan", "Card, 24576, -1", "Card, 24576, 99999"):
        assert hardware.detect_with_nvidia_smi(_smi(text)).usable is False
