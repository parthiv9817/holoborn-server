"""Synthesize summoning ritual audio stems for HoloBorn Stage 1.

Output:
- drafts/audio/summoning_drone.wav   (8s seamless low drone, loopable)
- drafts/audio/summoning_chime.wav   (1.5s magical chime, single-shot)

Both 44.1kHz 16-bit mono. Tweak frequencies/decay below and re-run.
First-pass synth stems; can be swapped for freesound CC0 textured recordings later.
"""

import numpy as np
import wave
from pathlib import Path

SAMPLE_RATE = 44100


def fade_in_out(audio: np.ndarray, fade_samples: int) -> np.ndarray:
    fade = np.linspace(0.0, 1.0, fade_samples)
    audio[:fade_samples] *= fade
    audio[-fade_samples:] *= fade[::-1]
    return audio


def normalize(audio: np.ndarray, target_peak: float = 0.7) -> np.ndarray:
    peak = float(np.max(np.abs(audio)))
    return audio * (target_peak / peak) if peak > 0 else audio


def synth_drone(duration_s: float = 8.0) -> np.ndarray:
    """Low ambient drone — 60Hz fundamental + harmonics, slow LFO breath."""
    t = np.linspace(0, duration_s, int(duration_s * SAMPLE_RATE), endpoint=False)
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.13 * t)        # breath ~7.7s cycle
    detune = np.sin(2 * np.pi * 0.07 * t) * 0.6              # slow pitch wobble

    fundamental = np.sin(2 * np.pi * (60.0 + detune) * t)
    second = 0.65 * np.sin(2 * np.pi * (90.0 + detune * 1.5) * t)
    third = 0.45 * np.sin(2 * np.pi * (120.0 + detune * 2.0) * t)
    fourth = 0.30 * np.sin(2 * np.pi * (180.0 + detune * 3.0) * t)
    high_shimmer = 0.08 * np.sin(2 * np.pi * (360.0 + detune * 6) * t)

    # Filtered noise for "air"
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 1, t.shape)
    # crude low-pass via cumulative running mean
    kernel = 32
    noise = np.convolve(noise, np.ones(kernel) / kernel, mode="same")
    noise *= 0.05

    audio = (fundamental + second + third + fourth + high_shimmer + noise) * lfo * 0.32

    fade_samples = int(0.15 * SAMPLE_RATE)
    audio = fade_in_out(audio, fade_samples)
    return normalize(audio, target_peak=0.65)


def synth_chime(duration_s: float = 1.5) -> np.ndarray:
    """Magical chime — major triad with exponential decay + high shimmer."""
    t = np.linspace(0, duration_s, int(duration_s * SAMPLE_RATE), endpoint=False)
    decay = np.exp(-2.2 * t)

    # E major triad an octave up: E5=659, G#5=830, B5=988
    root = np.sin(2 * np.pi * 659.25 * t)
    third = 0.7 * np.sin(2 * np.pi * 830.6 * t)
    fifth = 0.55 * np.sin(2 * np.pi * 987.77 * t)
    octave_shimmer = 0.25 * np.sin(2 * np.pi * 1318.5 * t) * np.exp(-3.5 * t)
    high_shimmer = 0.12 * np.sin(2 * np.pi * 2637.0 * t) * np.exp(-5.0 * t)

    audio = (root + third + fifth + octave_shimmer + high_shimmer) * decay * 0.5

    # Sharp attack envelope (8ms)
    attack_samples = int(0.008 * SAMPLE_RATE)
    audio[:attack_samples] *= np.linspace(0.0, 1.0, attack_samples)
    return normalize(audio, target_peak=0.85)


def write_wav(path: Path, audio: np.ndarray) -> None:
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
    print(f"saved {path}")


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "drafts" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_wav(out_dir / "summoning_drone.wav", synth_drone(duration_s=8.0))
    write_wav(out_dir / "summoning_chime.wav", synth_chime(duration_s=1.5))


if __name__ == "__main__":
    main()
