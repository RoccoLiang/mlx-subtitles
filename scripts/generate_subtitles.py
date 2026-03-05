#!/usr/bin/env python3
"""
Generate word-level timestamps (.words.json) using mlx-whisper.

Usage:
    python scripts/generate_subtitles.py                    # all videos in input/
    python scripts/generate_subtitles.py --file video.mp4   # single file
    python scripts/generate_subtitles.py --model medium     # specify model
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SUPPORTED_FORMATS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.webm', '.flv', '.wmv'}

DEFAULT_MODEL = 'large-v3'
MODEL_REPOS = {
    'large-v3':       'mlx-community/whisper-large-v3-mlx',
    'large-v3-turbo': 'mlx-community/whisper-large-v3-turbo',
    'medium':         'mlx-community/whisper-medium-mlx',
    'small':          'mlx-community/whisper-small-mlx',
}


def validate_filename(name: str) -> str:
    """Prevent path traversal in filenames."""
    safe = re.sub(r'[^\w\-.]', '_', name)
    if not safe or safe.startswith('.'):
        safe = 'output'
    return safe


def parse_loudnorm_output(stderr: str) -> dict[str, Any] | None:
    """Safely parse ffmpeg loudnorm JSON output from stderr."""
    json_start = stderr.rfind("{")
    json_end = stderr.rfind("}") + 1
    if json_start < 0 or json_end <= 0:
        return None
    try:
        return json.loads(stderr[json_start:json_end])
    except json.JSONDecodeError:
        return None


def get_loudnorm_defaults() -> dict[str, Any]:
    """Return default values if loudnorm parsing fails."""
    return {
        'input_i': '-16',
        'input_tp': '-1',
        'input_lra': '11',
        'input_thresh': '-30',
        'target_offset': '0'
    }


def preprocess_audio(video_path: Path, tmp_dir: str) -> Path:
    """Convert to mono 16 kHz WAV with EBU R128 loudness normalization."""
    wav_path = Path(tmp_dir) / f"{validate_filename(video_path.stem)}_pre.wav"
    print(f"  前處理音訊（單聲道 + 音量正規化）…", flush=True)

    measure = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-af", "aresample=16000,loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
            "-ac", "1", "-ar", "16000", "-f", "null", "-",
        ],
        capture_output=True, text=True, check=True,
    )

    stats = parse_loudnorm_output(measure.stderr)
    if stats is None:
        stats = get_loudnorm_defaults()
        print("  WARNING: Using default loudnorm parameters", file=sys.stderr)

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-af", (
                f"aresample=16000,"
                f"loudnorm=I=-16:TP=-1:LRA=11:"
                f"measured_I={stats['input_i']}:"
                f"measured_TP={stats['input_tp']}:"
                f"measured_LRA={stats['input_lra']}:"
                f"measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}:"
                f"linear=true"
            ),
            "-ac", "1", "-ar", "16000", str(wav_path),
        ],
        capture_output=True, check=True,
    )
    return wav_path


def transcribe_file(video_path: Path, output_dir: Path, model: str, language: str | None = None) -> None:
    import mlx_whisper

    repo = MODEL_REPOS.get(model, f'mlx-community/whisper-{model}-mlx')
    stem = validate_filename(video_path.stem)

    lang_label = f", lang={language}" if language else ""
    print(f"  Transcribing: {video_path.name}  [{model}{lang_label}]")

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_input = preprocess_audio(video_path, tmp_dir)
        print(f"  （轉錄中，請稍候…）", flush=True)
        result = mlx_whisper.transcribe(
            str(audio_input),
            path_or_hf_repo=repo,
            word_timestamps=True,
            language=language,
        )

    # Collect word-level timestamps with validation
    words = []
    for segment in result.get('segments', []):
        for w in segment.get('words', []):
            if all(k in w for k in ('word', 'start', 'end')):
                words.append({
                    'word':  w['word'],
                    'start': round(float(w['start']), 3),
                    'end':   round(float(w['end']),   3),
                })

    seg_count = len(result.get('segments', []))

    words_path = output_dir / f"{stem}.words.json"
    with open(words_path, 'w', encoding='utf-8') as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
    print(f"  → {words_path}  （{len(words)} 個字，{seg_count} 段）")


def main():
    parser = argparse.ArgumentParser(description='Generate English subtitles using mlx-whisper')
    parser.add_argument('--file',   help='Single video file to process')
    parser.add_argument('--model',  default=DEFAULT_MODEL, choices=list(MODEL_REPOS),
                        help=f'Whisper model (default: {DEFAULT_MODEL})')
    parser.add_argument('--output', default=None, help='Output directory (default: <project>/output)')
    parser.add_argument('--language', default=None, help='Source language code, e.g. en, ja, zh (default: auto-detect)')
    parser.add_argument('--skip-existing', action='store_true', help='Skip files that already have a words.json')
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.resolve()
    output_dir = (project_root / 'output' if args.output is None else Path(args.output)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    def should_skip(video_path: Path) -> bool:
        if not args.skip_existing:
            return False
        stem = validate_filename(video_path.stem)
        out = output_dir / f"{stem}.words.json"
        if out.exists():
            print(f"  Skipping (already exists): {out}")
            return True
        return False

    if args.file:
        video_path = Path(args.file)
        if not video_path.is_absolute():
            video_path = project_root / video_path
        video_path = video_path.resolve()

        if not video_path.exists():
            print(f"ERROR: File not found: {video_path}", file=sys.stderr)
            sys.exit(1)
        if not should_skip(video_path):
            transcribe_file(video_path, output_dir, args.model, args.language)
    else:
        input_dir = (project_root / 'input').resolve()
        videos = sorted(f for f in input_dir.iterdir() if f.suffix.lower() in SUPPORTED_FORMATS)
        if not videos:
            print(f"No videos found in {input_dir}", file=sys.stderr)
            sys.exit(1)
        for v in videos:
            if not should_skip(v):
                transcribe_file(v, output_dir, args.model, args.language)


if __name__ == '__main__':
    main()
