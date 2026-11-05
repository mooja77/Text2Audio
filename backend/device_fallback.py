"""Choose the device once, and say in plain words what it means for the voices.

Order: an explicit T2A_DEVICE wins. Otherwise the settings file written by
backend.hardware (gpu_usable) decides. A CUDA choice is re-checked against torch
(free memory, the 5 GB policy from backend.hardware) every time it is asked for, so a
card that filled up since install falls back to the processor. The studio voice and
cloning need CUDA; Kokoro runs anywhere. T2A_DOWNLOAD_CHATTERBOX only decides what is
downloaded and never turns the studio voice on.

torch is imported lazily, only when a CUDA check is needed.
"""
import math
import os
import threading
from dataclasses import dataclass

from backend import hardware
from pipeline.engines import DEFAULT_STUDIO_VOICE
from pipeline.synth import FatalSynthError

MIN_FREE_GB = hardware.MIN_VRAM_GB
NEED = ('The studio voice and voice cloning need an NVIDIA graphics card with at least '
        '%g GB of free memory. ' % MIN_FREE_GB)
FORCED_CPU = ('T2A_DEVICE is set to cpu, so the studio voice and voice cloning are switched off '
              'and the fast voices run on your processor. Remove T2A_DEVICE to let Text2Audio '
              'use a graphics card.')
NO_GPU = 'No usable NVIDIA graphics card was found. The fast voices run on your processor.'
NO_CUDA = ('No usable graphics card was found, so the fast voices run on your processor.')
MPS_ONLY = ('T2A_DEVICE is set to mps. The studio voice and voice cloning need an NVIDIA graphics '
            'card, so only the fast voices are available.')
BAD_VALUE = ('T2A_DEVICE must be cuda, mps or cpu, so Text2Audio is using your processor. '
             'The studio voice and voice cloning are switched off.')
NOT_INSTALLED = ('The studio voice engine (Chatterbox) is not installed. Run Install Text2Audio.bat '
                 'again to add it. The fast voices still work.')
OOM_STUDIO = ('The graphics card ran out of memory while loading the studio voice, so the studio '
              'voice and voice cloning are unavailable right now. Close other programs that use '
              'the graphics card, or use a fast voice.')
OOM_STUDIO_INFERENCE = ('The graphics card ran out of memory while making the studio voice, so the '
                        'studio voice and voice cloning stopped. Close other programs that use the '
                        'graphics card and try again, or choose a fast voice.')


class StudioUnavailable(FatalSynthError, RuntimeError):
    """The studio voice or cloning cannot run here; the message is plain words."""


OOM_RUNTIME_CPU = ('The graphics card ran out of memory while making the fast voice, so Text2Audio '
                   'switched to your processor. The studio voice and voice cloning are unavailable '
                   'until you restart Text2Audio and free some graphics memory.')

# Actual effective fallback state: once a real load or chunk OOM moved synthesis to the CPU,
# later eligibility rechecks must not report CUDA again. Guarded by a lock (jobs run in threads).
_runtime_lock = threading.Lock()
_runtime_cpu_reason = None


def note_runtime_cpu(reason=None):
    global _runtime_cpu_reason
    with _runtime_lock:
        if _runtime_cpu_reason is None:
            _runtime_cpu_reason = reason or OOM_RUNTIME_CPU


def runtime_cpu_reason():
    with _runtime_lock:
        return _runtime_cpu_reason


def reset_runtime_fallback():
    """A controlled restart/reset (and test fixtures) clear the runtime fallback."""
    global _runtime_cpu_reason
    with _runtime_lock:
        _runtime_cpu_reason = None


@dataclass(frozen=True)
class DeviceDecision:
    device: str
    studio: bool
    reason: str = ''

    @property
    def default_voice(self):
        return DEFAULT_STUDIO_VOICE if self.studio else 'af_heart'

    def health_fields(self):
        status = {'available': self.studio, 'reason': self.reason}
        return {'engines': {'default': 'chatterbox' if self.studio else 'kokoro',
                            'available': ['kokoro'] + (['chatterbox'] if self.studio else [])},
                'studio': dict(status), 'cloning': dict(status)}


def _cpu(reason):
    return DeviceDecision('cpu', False, reason)


def _cuda_free_gb(torch_module=None):
    try:
        torch = torch_module
        if torch is None:
            import torch  # noqa: PLC0415
        if not torch.cuda.is_available():
            return None
        free, _total = torch.cuda.mem_get_info(0)
        return free / 1024**3
    except Exception:
        return None


def resolve_device(env=None, settings_path=None, torch_module=None, engine_installed=True):
    env = os.environ if env is None else env
    forced = (env.get('T2A_DEVICE') or '').strip().lower()
    if forced == 'cpu':
        return _cpu(FORCED_CPU)
    if forced == 'mps':
        return DeviceDecision('mps', False, MPS_ONLY)
    if forced not in ('', 'cuda'):
        return _cpu(BAD_VALUE)
    runtime = runtime_cpu_reason()
    if runtime:
        return _cpu(runtime)
    if forced == '':
        path = settings_path or env.get('T2A_SETTINGS_PATH') or hardware.DEFAULT_SETTINGS_PATH
        if not hardware.gpu_usable_from_settings(path):
            note = hardware.read_settings(path).get('gpu_message') or NO_GPU
            return _cpu(NEED + str(note))
    free = _cuda_free_gb(torch_module)
    if free is None:
        return _cpu(NEED + NO_CUDA)
    if free < MIN_FREE_GB:
        return _cpu(NEED + 'Only %.1f GB is free right now, so the fast voices run on your '
                    'processor.' % (math.floor(free * 10 + 1e-3) / 10))
    if not engine_installed:
        return DeviceDecision('cuda', False, NOT_INSTALLED)
    return DeviceDecision('cuda', True, '')


def worker_device(env=None, torch_module=None):
    """For the engine worker: ('cuda', '') or (None, plain-words reason)."""
    decision = resolve_device(env, torch_module=torch_module)
    return ('cuda', '') if decision.device == 'cuda' else (None, decision.reason)


def is_cuda_oom(exc):
    return type(exc).__name__ == 'OutOfMemoryError' or 'out of memory' in str(exc).lower()


def _free_cuda():
    try:
        import torch  # noqa: PLC0415
        torch.cuda.empty_cache()
    except Exception:
        pass


def build_kokoro(voice_id, speed, device, synth_cls=None):
    """In-process Kokoro on `device`; a CUDA out-of-memory error retries on the CPU."""
    from pipeline.synth import PRESET_VOICES, Synthesizer
    cls = synth_cls or Synthesizer

    def make(dev):
        return cls(voice=voice_id, lang_code=PRESET_VOICES[voice_id], speed=float(speed), device=dev)

    try:
        synth = make(device)
    except Exception as exc:
        if device != 'cuda' or not is_cuda_oom(exc):
            raise
        _free_cuda()
        synth = make('cpu')
        note_runtime_cpu()
        return synth
    if device == 'cuda':
        original = synth.synth_chunk

        def safe(text):
            try:
                return original(text)
            except Exception as exc:
                if not is_cuda_oom(exc):
                    raise
                synth.__dict__.pop('synth_chunk', None)
                synth.__dict__.update(make('cpu').__dict__)
                note_runtime_cpu()
                _free_cuda()
                return synth.synth_chunk(text)
        synth.synth_chunk = safe
    return synth
