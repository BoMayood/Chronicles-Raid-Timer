"""Curated studio audio cues, WAV synthesizer, and clean multi-voice Windows TTS."""

from __future__ import annotations

import os
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect

from chronicles.config import get_builtin_sounds_dir, get_custom_sounds_dir

try:
    from PyQt6.QtTextToSpeech import QTextToSpeech, QVoice
except Exception:  # pragma: no cover
    QTextToSpeech = None  # type: ignore[assignment]
    QVoice = None  # type: ignore[assignment]

SAMPLE_RATE = 44100

# Five clean, unmistakable, well-balanced alert cues
BUILTIN_SOUNDS: list[tuple[str, str]] = [
    ("chronicles_horn.wav", "Chronicles War Horn (Default)"),
    ("chronicles_chime.wav", "Crystalline Chime"),
    ("tactical_ping.wav", "Tactical Radar Ping"),
    ("celestial_bell.wav", "Sanctuary Bell"),
    ("crimson_alert.wav", "Crimson Raid Alert"),
]


@dataclass(frozen=True)
class TtsVoicePreset:
    """Curated natural-sounding announcer persona."""

    id: str
    label: str
    preferred_names: tuple[str, ...]
    pitch: float
    rate: float


@dataclass(frozen=True)
class SystemVoiceOption:
    """Discovered OS Text-to-Speech voice."""

    id: str
    label: str
    engine: str
    voice_name: str
    locale: str


VOICE_PRESETS: list[TtsVoicePreset] = [
    TtsVoicePreset("preset:commander_david", "Commander (David — Deep & Clear)", ("David",), -0.14, -0.04),
    TtsVoicePreset("preset:oracle_zira", "Oracle (Zira — Clear Female)", ("Zira",), 0.00, 0.00),
    TtsVoicePreset("preset:dispatch_mark", "Dispatch (Mark — Crisp & Brisk)", ("Mark",), 0.04, 0.10),
]

TTS_CALLOUT_STYLES: list[tuple[str, str]] = [
    ("standard", "Standard Callout"),
    ("tactical", "Brief Tactical"),
    ("epic", "Epic Herald"),
]


def format_tts_callout(
    style: str,
    title: str,
    message: str,
    phase_label: str = "",
    minutes_left: Optional[int] = None,
) -> str:
    """Format spoken announcement text according to selected callout style."""
    if style == "tactical":
        if minutes_left is not None and minutes_left > 0:
            return f"Alert. {title}, {phase_label}, {minutes_left} minute{'s' if minutes_left > 1 else ''}."
        if phase_label:
            return f"{title}, {phase_label} active."
        return f"{title}. {message}"
    if style == "epic":
        if minutes_left is not None and minutes_left > 0:
            return f"Attention raiders! Prepare for {title}. {message}"
        return f"The gates have opened! {title}. {message}"
    return f"{title}. {message}"


def _write_stereo_wav(path: str, left: np.ndarray, right: np.ndarray) -> None:
    peak = float(max(np.max(np.abs(left)), np.max(np.abs(right)))) if left.size else 1.0
    if peak > 0:
        scale = 0.84 / peak
        left = left * scale
        right = right * scale
    stereo = np.column_stack([left, right]).ravel()
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


def _warm_note(freq: float, dur: float, attack: float = 0.012, decay: float = 3.2) -> np.ndarray:
    t = np.linspace(0.0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    env = np.minimum(1.0, t / max(0.001, attack)) * np.exp(-decay * t)
    # Smooth fade-out tail to guarantee zero end click
    fade_len = min(len(t), int(0.04 * SAMPLE_RATE))
    if fade_len > 0:
        env[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)
    sig = (
        0.68 * np.sin(2.0 * np.pi * freq * t)
        + 0.22 * np.sin(2.0 * np.pi * freq * 2.0 * t) * np.exp(-1.5 * t)
        + 0.08 * np.sin(2.0 * np.pi * freq * 3.0 * t) * np.exp(-3.0 * t)
        + 0.02 * np.sin(2.0 * np.pi * freq * 4.0 * t) * np.exp(-4.5 * t)
    )
    return sig * env


def _mix_stereo_notes(
    notes: list[tuple[float, float, float, float, float]]
) -> tuple[np.ndarray, np.ndarray]:
    """Mix (start_sec, freq, dur, decay, pan[-1..1]) into clean stereo buffers."""
    total_dur = max(start + dur for start, _, dur, _, _ in notes) + 0.06
    n_samples = int(SAMPLE_RATE * total_dur)
    left = np.zeros(n_samples, dtype=np.float64)
    right = np.zeros(n_samples, dtype=np.float64)
    for start, freq, dur, decay, pan in notes:
        sig = _warm_note(freq, dur, decay=decay)
        idx = int(start * SAMPLE_RATE)
        end = min(n_samples, idx + len(sig))
        chunk = sig[: end - idx]
        l_gain = np.sqrt(0.5 * (1.0 - max(-1.0, min(1.0, pan))))
        r_gain = np.sqrt(0.5 * (1.0 + max(-1.0, min(1.0, pan))))
        left[idx:end] += chunk * l_gain
        right[idx:end] += chunk * r_gain
    return left, right


def _gen_chronicles_chime() -> tuple[np.ndarray, np.ndarray]:
    return _mix_stereo_notes([
        (0.00, 523.25, 1.10, 3.0, -0.25),  # C5
        (0.09, 659.25, 1.15, 2.8,  0.20),  # E5
        (0.18, 783.99, 1.25, 2.6, -0.15),  # G5
        (0.28, 1046.5, 1.45, 2.4,  0.15),  # C6
    ])


def _gen_tactical_ping() -> tuple[np.ndarray, np.ndarray]:
    return _mix_stereo_notes([
        (0.00, 880.00, 0.36, 7.5, -0.15),
        (0.14, 1174.66, 0.65, 5.2, 0.15),
    ])


def _gen_celestial_bell() -> tuple[np.ndarray, np.ndarray]:
    dur = 1.85
    t = np.linspace(0.0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    attack = np.minimum(1.0, t / 0.010)
    partials = [
        (392.00, 0.90, 2.0),
        (783.99, 0.48, 2.7),
        (1174.66, 0.25, 3.6),
        (1567.98, 0.14, 4.5),
    ]
    left = np.zeros_like(t)
    right = np.zeros_like(t)
    for f, amp, dec in partials:
        left += amp * np.sin(2.0 * np.pi * f * t) * np.exp(-dec * t)
        right += amp * np.sin(2.0 * np.pi * (f + 1.1) * t) * np.exp(-dec * t)
    fade_len = int(0.06 * SAMPLE_RATE)
    env = attack.copy()
    env[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)
    return left * env, right * env


def _gen_crimson_alert() -> tuple[np.ndarray, np.ndarray]:
    return _mix_stereo_notes([
        (0.00, 587.33, 0.34, 6.2, -0.20),  # D5
        (0.00, 880.00, 0.34, 6.5,  0.20),  # A5
        (0.22, 659.25, 0.55, 4.8, -0.15),  # E5
        (0.22, 987.77, 0.55, 5.0,  0.15),  # B5
    ])


def ensure_builtin_sounds(target_dir: Optional[str] = None, force_synth: bool = False) -> str:
    """Ensure curated built-in WAV sound effects are present in ``assets/sounds``."""
    sounds_dir = target_dir or get_builtin_sounds_dir()
    os.makedirs(sounds_dir, exist_ok=True)

    generators = {
        "chronicles_chime.wav": _gen_chronicles_chime,
        "tactical_ping.wav": _gen_tactical_ping,
        "celestial_bell.wav": _gen_celestial_bell,
        "crimson_alert.wav": _gen_crimson_alert,
    }
    for fname, fn in generators.items():
        full = os.path.join(sounds_dir, fname)
        if force_synth or not os.path.exists(full):
            l_ch, r_ch = fn()
            _write_stereo_wav(full, l_ch, r_ch)
    return sounds_dir


class AudioEngine:
    """Unified sound effect player and clean multi-voice Windows TTS announcer."""

    def __init__(self) -> None:
        self._effect: Optional[QSoundEffect] = None
        self._player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None
        self._tts_engines: dict[str, "QTextToSpeech"] = {}
        self._builtin_dir = ensure_builtin_sounds()

    def _get_tts_engine(self, engine_name: str) -> Optional["QTextToSpeech"]:
        if QTextToSpeech is None:
            return None
        if engine_name in self._tts_engines:
            return self._tts_engines[engine_name]
        try:
            available = QTextToSpeech.availableEngines()
            chosen = engine_name if engine_name in available else (
                "winrt" if "winrt" in available else ("sapi" if "sapi" in available else "")
            )
            instance = QTextToSpeech(chosen) if chosen else QTextToSpeech()
            self._tts_engines[engine_name] = instance
            return instance
        except Exception:
            return None

    def discover_system_voices(self) -> list[SystemVoiceOption]:
        """Enumerate deduplicated installed OS voices across winrt and sapi backends."""
        if QTextToSpeech is None:
            return []
        found: list[SystemVoiceOption] = []
        seen_keys: set[str] = set()
        available = [e for e in QTextToSpeech.availableEngines() if e != "mock"]
        preferred_order = [e for e in ("winrt", "sapi") if e in available] + [
            e for e in available if e not in ("winrt", "sapi")
        ]
        for eng in preferred_order:
            tts = self._get_tts_engine(eng)
            if tts is None:
                continue
            try:
                for voice in tts.availableVoices():
                    v_name = voice.name()
                    norm = v_name.replace(" Desktop", "").strip().lower()
                    loc = voice.locale().name()
                    dedupe_key = f"{norm}:{loc}"
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)
                    vid = f"voice:{eng}:{v_name}"
                    label = f"{v_name} ({loc})"
                    found.append(SystemVoiceOption(vid, label, eng, v_name, loc))
            except Exception:
                continue
        return found

    @staticmethod
    def get_preset(voice_id: str) -> Optional[TtsVoicePreset]:
        for preset in VOICE_PRESETS:
            if preset.id == voice_id:
                return preset
        return None

    def _resolve_tts_target(self, voice_id: str) -> tuple[Optional["QTextToSpeech"], Optional["QVoice"]]:
        if QTextToSpeech is None:
            return None, None
        if voice_id.startswith("voice:"):
            parts = voice_id.split(":", 2)
            if len(parts) == 3:
                _, eng, target_name = parts
                tts = self._get_tts_engine(eng)
                if tts is not None:
                    for v in tts.availableVoices():
                        if v.name() == target_name:
                            return tts, v

        preset = self.get_preset(voice_id)
        available = [e for e in QTextToSpeech.availableEngines() if e != "mock"]
        eng_order = [e for e in ("winrt", "sapi") if e in available]
        if preset:
            for pref in preset.preferred_names:
                for eng in eng_order:
                    tts = self._get_tts_engine(eng)
                    if tts is None:
                        continue
                    for v in tts.availableVoices():
                        if pref.lower() in v.name().lower():
                            return tts, v

        for eng in eng_order:
            tts = self._get_tts_engine(eng)
            if tts is not None:
                voices = tts.availableVoices()
                return tts, (voices[0] if voices else None)
        return self._get_tts_engine("winrt"), None

    def resolve_sound_path(self, filename_or_path: str) -> str:
        if os.path.isabs(filename_or_path) and os.path.exists(filename_or_path):
            return filename_or_path
        builtin_candidate = os.path.join(self._builtin_dir, filename_or_path)
        if os.path.exists(builtin_candidate):
            return builtin_candidate
        custom_candidate = os.path.join(get_custom_sounds_dir(), filename_or_path)
        if os.path.exists(custom_candidate):
            return custom_candidate
        default_path = os.path.join(self._builtin_dir, "chronicles_horn.wav")
        if os.path.exists(default_path):
            return default_path
        return os.path.join(self._builtin_dir, "chronicles_chime.wav")

    def play_sound(self, filename_or_path: str, volume_percent: int = 60) -> None:
        path = self.resolve_sound_path(filename_or_path)
        if not os.path.exists(path):
            return
        vol = max(0.0, min(1.0, float(volume_percent) / 100.0))
        try:
            if path.lower().endswith(".wav"):
                if self._effect is None:
                    self._effect = QSoundEffect()
                self._effect.stop()
                self._effect.setSource(QUrl.fromLocalFile(path))
                self._effect.setVolume(vol)
                self._effect.play()
            else:
                if self._player is None:
                    self._player = QMediaPlayer()
                    self._audio_output = QAudioOutput()
                    self._player.setAudioOutput(self._audio_output)
                self._player.stop()
                assert self._audio_output is not None
                self._audio_output.setVolume(vol)
                self._player.setSource(QUrl.fromLocalFile(path))
                self._player.play()
        except Exception:
            pass

    def speak(
        self,
        text: str,
        volume_percent: int = 75,
        rate: float = -0.04,
        pitch: float = -0.14,
        voice_id: str = "preset:commander_david",
    ) -> None:
        if QTextToSpeech is None or not text.strip():
            return
        try:
            tts, voice = self._resolve_tts_target(voice_id)
            if tts is None:
                return
            if voice is not None:
                tts.setVoice(voice)
            tts.setVolume(max(0.0, min(1.0, float(volume_percent) / 100.0)))
            tts.setRate(max(-1.0, min(1.0, float(rate))))
            tts.setPitch(max(-1.0, min(1.0, float(pitch))))
            tts.say(text)
        except Exception:
            pass
