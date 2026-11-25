"""Procedural sound effects, synthesized at runtime with numpy.

No audio files are needed: engine hum, missile launch, radar ping,
explosions and the win jingle are all generated as waveforms.
"""

import math

import pygame

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False

_SAMPLE_RATE = 22050


class Audio:
    def __init__(self, enabled: bool = True):
        self.enabled = False
        self.sounds = {}
        if not enabled:
            return
        try:
            pygame.mixer.init(frequency=_SAMPLE_RATE, size=-16, channels=1,
                              buffer=512)
            pygame.mixer.set_num_channels(16)
            self.enabled = True
        except pygame.error:
            self.enabled = False
            return
        self._build()

    def _make(self, name: str, samples) -> None:
        if not _HAS_NUMPY:
            return
        arr = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
        self.sounds[name] = pygame.mixer.Sound(buffer=arr.tobytes())

    def _build(self) -> None:
        if not _HAS_NUMPY:
            return
        t = np.arange(int(_SAMPLE_RATE * 1.2)) / _SAMPLE_RATE

        # engine: layered sawtooth with slow amplitude wobble
        engine = (np.sign(np.sin(2 * np.pi * 90 * t))
                  + 0.5 * np.sign(np.sin(2 * np.pi * 135 * t))
                  + 0.3 * np.sin(2 * np.pi * 45 * t))
        engine *= 0.25 * (1.0 + 0.3 * np.sin(2 * np.pi * 7 * t))
        fade = np.minimum(1.0, t / 0.4)
        self._make("engine", engine * fade)

        # radar ping: short sine sweep
        dur = 0.35
        n = int(_SAMPLE_RATE * dur)
        tt = np.arange(n) / _SAMPLE_RATE
        ping = np.sin(2 * np.pi * (900 + 700 * tt / dur) * tt) * np.exp(-tt * 9)
        self._make("ping", ping * 0.5)

        # missile launch: noise burst with rising pitch
        n = int(_SAMPLE_RATE * 0.5)
        tt = np.arange(n) / _SAMPLE_RATE
        noise = np.random.uniform(-1, 1, n)
        whoosh = np.convolve(noise, np.ones(120) / 120, mode="same")
        whoosh *= np.exp(-tt * 4) * (0.4 + tt)
        self._make("launch", whoosh * 0.6)

        # explosion: decaying noise + low thump
        n = int(_SAMPLE_RATE * 0.9)
        tt = np.arange(n) / _SAMPLE_RATE
        boom = np.random.uniform(-1, 1, n) * np.exp(-tt * 6)
        boom += 0.8 * np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 8)
        self._make("explosion", boom * 0.8)

        # win jingle: rising arpeggio
        notes = [523.25, 659.25, 783.99, 1046.5]
        parts = []
        for f in notes:
            n = int(_SAMPLE_RATE * 0.22)
            tt = np.arange(n) / _SAMPLE_RATE
            tone = (np.sin(2 * np.pi * f * tt)
                    + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 5)
            parts.append(tone * 0.5)
        jingle = np.concatenate(parts)
        self._make("win", jingle)

    def play(self, name: str, volume: float = 1.0, loops: int = 0) -> None:
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        snd.set_volume(volume)
        snd.play(loops=loops)

    def stop(self, name: str) -> None:
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            snd.stop()

    def engine_loop(self, throttle: float, afterburner: bool):
        """Keep a looping engine bed going, scaled by throttle."""
        if not self.enabled:
            return
        vol = 0.12 + 0.22 * throttle + (0.15 if afterburner else 0.0)
        snd = self.sounds.get("engine")
        if snd is None:
            return
        if not pygame.mixer.get_busy() or getattr(self, "_engine_playing", False) is False:
            snd.play(loops=-1)
            self._engine_playing = True
        snd.set_volume(min(1.0, vol))

    def stop_engine(self):
        self.stop("engine")
        self._engine_playing = False
