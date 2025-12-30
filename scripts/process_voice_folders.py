"""
Batch helper to combine raw voice snippets and generate canonical Chatterbox voices.

Steps per numeric subfolder under audio/voices/raw/:
1) Load all audio files (.wav/.mp3/.ogg), convert to mono 48kHz, concatenate => combined.wav.
2) Feed combined.wav as the audio_prompt to Chatterbox Turbo and synthesize the canonical
   sentences (from docs/Canonical Audio Sentences.txt).
3) Save the generated clip to audio/voices/generated/actor-<folder>.wav

Intended for overnight processing of many folders (e.g., 30-50).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, List, Optional

import os
import torch
import torchaudio

try:
    from chatterbox.tts_turbo import ChatterboxTurboTTS
except ImportError as e:  # pragma: no cover - requires optional dependency
    raise SystemExit(
        "chatterbox-tts is required for this script. Install with: pip install chatterbox-tts"
    ) from e


logger = logging.getLogger("process_voice_folders")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = REPO_ROOT / "audio" / "voices" / "raw"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "audio" / "voices" / "generated"
CANONICAL_SENTENCES_PATH = REPO_ROOT / "docs" / "Canonical Audio Sentences.txt"
DEFAULT_LOCAL_MODEL_DIR = REPO_ROOT / "models" / "chatterbox-turbo"
TARGET_SAMPLE_RATE = 48_000


def load_canonical_sentences(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Canonical sentences file not found: {path}")
    sentences = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not sentences:
        raise ValueError(f"No canonical sentences found in {path}")
    return "\n".join(sentences)


def gather_audio_files(folder: Path) -> List[Path]:
    exts = {".wav", ".mp3", ".ogg"}
    return sorted([p for p in folder.iterdir() if p.suffix.lower() in exts and p.is_file()])


def load_and_normalize_audio(files: Iterable[Path], target_sr: int) -> Optional[torch.Tensor]:
    clips: List[torch.Tensor] = []
    for f in files:
        try:
            wav, sr = torchaudio.load(f)
        except Exception as e:
            logger.warning("Skipping %s (failed to load: %s)", f, e)
            continue

        # Ensure mono
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)

        # Resample if needed
        if sr != target_sr:
            resampler = torchaudio.transforms.Resample(sr, target_sr)
            wav = resampler(wav)

        clips.append(wav)

    if not clips:
        return None

    return torch.cat(clips, dim=1)  # [1, total_samples]


def load_and_normalize_file(path: Path, target_sr: int) -> Optional[torch.Tensor]:
    try:
        wav, sr = torchaudio.load(path)
    except Exception as e:
        logger.warning("Skipping %s (failed to load: %s)", path, e)
        return None

    if wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)

    if sr != target_sr:
        resampler = torchaudio.transforms.Resample(sr, target_sr)
        wav = resampler(wav)
    return wav


def get_duration_seconds(path: Path) -> float:
    try:
        info = torchaudio.info(path)
        if info.num_frames and info.sample_rate:
            return info.num_frames / float(info.sample_rate)
    except Exception:
        pass
    # Fallback: load to get duration
    try:
        _, sr = torchaudio.load(path)
        info = torchaudio.info(path)
        if info.num_frames and sr:
            return info.num_frames / float(sr)
    except Exception:
        return 0.0
    return 0.0


def save_wav(path: Path, wav: torch.Tensor, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(path, wav, sample_rate=sample_rate, bits_per_sample=16)


def synthesize_canonical(
    model: ChatterboxTurboTTS,
    prompt_path: Path,
    text: str,
    out_path: Path,
    cfg_weight: float = 0.5,
    exaggeration: float = 0.5,
) -> None:
    wav = model.generate(
        text,
        audio_prompt_path=str(prompt_path),
        cfg_weight=cfg_weight,
        exaggeration=exaggeration,
    )
    # model outputs float tensor (channels, samples) at model.sr
    if wav.dim() > 1 and wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)
    save_wav(out_path, wav, sample_rate=model.sr)


def process_folder(
    folder: Path,
    out_dir: Path,
    sentences_text: str,
    model: ChatterboxTurboTTS,
    target_sr: int,
) -> None:
    files = gather_audio_files(folder)
    if not files:
        logger.info("No audio files in %s; skipping.", folder)
        return

    logger.info("Processing folder %s with %d files", folder.name, len(files))
    combined = load_and_normalize_audio(files, target_sr)
    if combined is None:
        logger.info("No loadable audio in %s; skipping.", folder)
        return

    combined_path = folder / "combined.wav"
    save_wav(combined_path, combined, sample_rate=target_sr)

    out_path = out_dir / f"actor-{folder.name}.wav"
    synthesize_canonical(model, combined_path, sentences_text, out_path)
    logger.info("Wrote %s", out_path)


def process_pair_mix(
    folder_a: Path,
    folder_b: Path,
    out_dir: Path,
    sentences_text: str,
    model: ChatterboxTurboTTS,
    target_sr: int,
) -> None:
    files_a = gather_audio_files(folder_a)
    files_b = gather_audio_files(folder_b)
    if not files_a or not files_b:
        logger.info("No audio files in %s or %s; skipping mix.", folder_a.name, folder_b.name)
        return

    # Duration-aware selection
    durations_a = [(p, get_duration_seconds(p)) for p in files_a]
    durations_b = [(p, get_duration_seconds(p)) for p in files_b]
    total_a = sum(d for _, d in durations_a)
    total_b = sum(d for _, d in durations_b)

    # Identify shorter (S) and longer (L) sets
    if total_a <= total_b:
        short_set, long_set = durations_a, durations_b
    else:
        short_set, long_set = durations_b, durations_a

    target = sum(d for _, d in short_set)
    # Sort long_set by duration
    long_sorted = sorted(long_set, key=lambda x: x[1])
    selected_long: List[Path] = []
    i, j = 0, len(long_sorted) - 1
    total_selected = 0.0
    use_long_end = True
    while total_selected < target and i <= j:
        path, dur = long_sorted[j] if use_long_end else long_sorted[i]
        selected_long.append(path)
        total_selected += dur
        if use_long_end:
            j -= 1
        else:
            i += 1
        use_long_end = not use_long_end

    # If still under target, take remaining longest files
    while total_selected < target and j >= i:
        path, dur = long_sorted[j]
        selected_long.append(path)
        total_selected += dur
        j -= 1

    # Interleave short_set (all files) and selected_long
    interleaved: List[Path] = []
    short_paths = [p for p, _ in short_set]
    long_paths = selected_long
    max_len = max(len(short_paths), len(long_paths))
    for idx in range(max_len):
        if idx < len(short_paths):
            interleaved.append(short_paths[idx])
        if idx < len(long_paths):
            interleaved.append(long_paths[idx])

    logger.info(
        "Processing mix %s + %s with %d interleaved files (short total %.1fs, long subset %.1fs)",
        folder_a.name,
        folder_b.name,
        len(interleaved),
        target,
        total_selected,
    )

    clips: List[torch.Tensor] = []
    for f in interleaved:
        wav = load_and_normalize_file(f, target_sr)
        if wav is not None:
            clips.append(wav)

    if not clips:
        logger.info("No loadable audio in mix %s + %s after interleave; skipping.", folder_a.name, folder_b.name)
        return

    combined = torch.cat(clips, dim=1)

    mix_name = f"{folder_a.name}-{folder_b.name}"
    combined_path = (folder_a.parent / f"combined-{mix_name}.wav")
    save_wav(combined_path, combined, sample_rate=target_sr)

    out_path = out_dir / f"actor-{mix_name}.wav"
    synthesize_canonical(model, combined_path, sentences_text, out_path)
    logger.info("Wrote %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-generate canonical voices from raw folders.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="Root folder containing numbered subfolders.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for generated voices.")
    parser.add_argument("--device", type=str, default=None, help='Device for Chatterbox (e.g., "cuda" or "cpu"; defaults to auto).')
    parser.add_argument("--cfg-weight", type=float, default=0.5, help="CFG weight for Chatterbox generation.")
    parser.add_argument("--exaggeration", type=float, default=0.5, help="Expressiveness for Chatterbox generation.")
    parser.add_argument("--test", action="store_true", help="Process only the first numbered folder (smoke test).")
    parser.add_argument(
        "--model-path",
        type=Path,
        default=None,
        help="Path to local chatterbox-turbo model (defaults to CHATTERBOX_LOCAL_PATH env or models/chatterbox-turbo).",
    )
    parser.add_argument(
        "--mixer",
        type=int,
        default=0,
        help="Number of random folder mixes to generate (pairs of folders concatenated).",
    )
    args = parser.parse_args()

    raw_root: Path = args.raw_dir
    out_dir: Path = args.out_dir
    sentences_text = load_canonical_sentences(CANONICAL_SENTENCES_PATH)

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    # Resolve local model path (no remote downloads)
    env_model = os.getenv("CHATTERBOX_LOCAL_PATH")
    model_path = args.model_path or (Path(env_model) if env_model else DEFAULT_LOCAL_MODEL_DIR)
    if not model_path.exists():
        raise SystemExit(
            f"Local chatterbox-turbo model not found at {model_path}. "
            "Download it manually or set CHATTERBOX_LOCAL_PATH to a valid path."
        )

    logger.info("Loading Chatterbox Turbo model from %s on device=%s", model_path, device)
    model = ChatterboxTurboTTS.from_local(str(model_path), device=device)

    if not raw_root.exists():
        raise SystemExit(f"Raw directory does not exist: {raw_root}")

    all_folders = [p for p in raw_root.iterdir() if p.is_dir() and p.name.isdigit()]
    if not all_folders:
        logger.info("No numbered folders found under %s; nothing to do.", raw_root)
        return

    all_folders = sorted(all_folders, key=lambda p: int(p.name))
    folders = all_folders[:1] if (args.test and all_folders) else all_folders

    if args.mixer > 0:
        # Mixer mode only: skip the base per-folder pass
        if len(all_folders) < 2:
            logger.info("Mixer requested but fewer than 2 folders; nothing to mix.")
            return
        import random

        for _ in range(args.mixer):
            a, b = random.sample(all_folders, 2)
            try:
                process_pair_mix(a, b, out_dir, sentences_text, model, TARGET_SAMPLE_RATE)
            except Exception as e:  # pragma: no cover - best-effort batch run
                logger.error("Failed processing mix %s-%s: %s", a.name, b.name, e, exc_info=True)
        return

    # Deterministic base pass over folders (single-folder processing)
    for folder in folders:
        try:
            process_folder(folder, out_dir, sentences_text, model, TARGET_SAMPLE_RATE)
        except Exception as e:  # pragma: no cover - best-effort batch run
            logger.error("Failed processing %s: %s", folder, e, exc_info=True)


if __name__ == "__main__":
    main()

