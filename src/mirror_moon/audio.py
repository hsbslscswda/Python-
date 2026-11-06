"""Original synthesized tones; no downloaded music or copyrighted effects."""

import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from .resources import user_dir


def synthesize(path: Path, frequency: float, duration: float, loop=False):
    if path.exists():
        return
    rate = 22050
    samples = []
    for i in range(round(rate * duration)):
        t = i / rate
        envelope = 0.35 if loop else min(1.0, t / 0.015) * math.exp(-t * 6.0) * 0.45
        v = math.sin(math.tau * frequency * t) + 0.25 * math.sin(math.tau * frequency * 2 * t)
        samples.append(struct.pack("<h", round(18000 * v * envelope)))
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        out.writeframes(b"".join(samples))


class Audio:
    def __init__(self, parent):
        directory = user_dir() / "audio"
        directory.mkdir(exist_ok=True)
        self.sounds = {}
        for name, frequency in (
            ("summon", 440.0),
            ("overdrive", 660.0),
            ("slash", 880.0),
            ("shatter", 1100.0),
            ("hum", 110.0),
        ):
            path = directory / f"{name}.wav"
            synthesize(path, frequency, 1.0 if name == "hum" else 0.45, name == "hum")
            sound = QSoundEffect(parent)
            sound.setSource(QUrl.fromLocalFile(str(path)))
            sound.setVolume(0.15)
            self.sounds[name] = sound
        self.sounds["hum"].setLoopCount(QSoundEffect.Infinite.value)
        self.muted, self.volume, self.last_id = False, 0.0, 0

    def events(self, events):
        for event in events:
            if event.event_id <= self.last_id:
                continue
            self.last_id = event.event_id
            key = "slash" if event.kind in ("slash", "double", "cross") else event.kind
            sound = self.sounds.get(key)
            if sound and not self.muted:
                sound.play()

    def update(self, intensity):
        target = 0.0 if self.muted else intensity * 0.16
        self.volume += (target - self.volume) * 0.12
        hum = self.sounds["hum"]
        hum.setVolume(self.volume)
        if self.volume > 0.003 and not hum.isPlaying():
            hum.play()
        elif self.volume <= 0.003 and hum.isPlaying():
            hum.stop()

    def stop(self):
        for sound in self.sounds.values():
            sound.stop()

    def error(self):
        return any(s.status() == QSoundEffect.Status.Error for s in self.sounds.values())
