"""Detect a usable NVIDIA GPU and remember the answer in the settings file.

Before install there is no torch yet, so we ask nvidia-smi. After install we ask
torch.cuda. Both are best-effort and never raise: any failure means "no usable
GPU", and the app then uses the fast voices on the processor.

install.ps1 only calls this module:
    python -m backend.hardware --settings <path> [--post-install]

This module must not import torch at module level.
"""
import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

MIN_VRAM_GB = 4.0  # Chatterbox peaked at about 4.5 GB in testing; allow a little headroom
SMI_TIMEOUT_SECONDS = 15
DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"


@dataclass(frozen=True)
class GpuReport:
    usable: bool
    name: str | None
    vram_gb: float | None
    source: str  # "nvidia-smi" | "torch" | "none"
    message: str  # plain words, safe to show on screen


def _report(name, vram_gb, source, absent_reason=None) -> GpuReport:
    if name is None:
        reason = absent_reason or "No NVIDIA graphics card was found."
        return GpuReport(False, None, None, "none",
                         reason + " The fast voices will run on your processor. "
                         "Text2Audio still works.")
    if vram_gb is None or vram_gb < MIN_VRAM_GB:
        have = "an unknown amount of" if vram_gb is None else f"{vram_gb:.1f} GB of"
        return GpuReport(False, name, vram_gb, source,
                         f"Found {name}, but it has {have} memory and the studio voice "
                         f"needs at least {MIN_VRAM_GB:g} GB. The fast voices will run on "
                         "your processor. Text2Audio still works.")
    return GpuReport(True, name, vram_gb, source,
                     f"Found {name} with {vram_gb:.1f} GB of memory. "
                     "The studio voice can use it.")


def detect_with_nvidia_smi(run=None) -> GpuReport:
    """Pre-install check. `run` is injectable for tests (defaults to subprocess.run)."""
    run = run or subprocess.run
    try:
        result = run(["nvidia-smi", "--query-gpu=name,memory.total",
                      "--format=csv,noheader,nounits"],
                     capture_output=True, text=True, timeout=SMI_TIMEOUT_SECONDS)
        if result.returncode != 0:
            return _report(None, None, "none",
                           "The graphics card tool did not answer.")
        best = None
        for line in str(result.stdout).splitlines():
            name, _, mem = line.rpartition(",")
            if not name.strip():
                continue
            vram = round(float(mem.strip()) / 1024, 1)  # nvidia-smi reports MiB
            if best is None or vram > best[1]:
                best = (name.strip(), vram)
        if best is None:
            return _report(None, None, "none")
        return _report(best[0], best[1], "nvidia-smi")
    except Exception:
        return _report(None, None, "none")


def detect_with_torch(torch_module=None) -> GpuReport:
    """Post-install check via torch.cuda. torch is imported lazily, here only."""
    try:
        torch = torch_module
        if torch is None:
            import torch  # noqa: PLC0415
        if not torch.cuda.is_available():
            return _report(None, None, "none",
                           "The installed PyTorch cannot use a graphics card.")
        props = torch.cuda.get_device_properties(0)
        return _report(str(props.name), round(props.total_memory / 1024**3, 1), "torch")
    except Exception:
        return _report(None, None, "none")


def detect_gpu(post_install: bool = False, run=None, torch_module=None) -> GpuReport:
    if post_install:
        return detect_with_torch(torch_module)
    return detect_with_nvidia_smi(run)


def read_settings(path) -> dict:
    """Never raises. A missing, unreadable or malformed file gives the safe default {}."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def gpu_usable_from_settings(path) -> bool:
    """What the server asks at startup. Missing file means False (CPU, safe default)."""
    return read_settings(path).get("gpu_usable") is True


def write_settings(path, report: GpuReport) -> dict:
    """Merge the GPU result into the settings file (other keys are kept)."""
    data = read_settings(path)
    data.update({"gpu_usable": report.usable, "gpu_name": report.name,
                 "gpu_vram_gb": report.vram_gb, "gpu_checked_with": report.source,
                 "gpu_message": report.message})
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, target)
    return data


def check_and_save(settings_path=DEFAULT_SETTINGS_PATH, post_install: bool = False,
                   run=None, torch_module=None) -> GpuReport:
    report = detect_gpu(post_install, run, torch_module)
    try:
        write_settings(settings_path, report)
    except OSError:
        pass  # saving is helpful, never fatal
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check for a usable NVIDIA GPU.")
    parser.add_argument("--settings", default=str(DEFAULT_SETTINGS_PATH))
    parser.add_argument("--post-install", action="store_true")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args(argv)
    report = check_and_save(args.settings, args.post_install)
    print(json.dumps(asdict(report)) if args.json else report.message)
    return 0  # an absent GPU is normal, not an install failure


if __name__ == "__main__":
    sys.exit(main())
