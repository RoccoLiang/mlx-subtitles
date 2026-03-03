#!/usr/bin/env python3
"""
Generate English subtitles (.words.json + .en.srt) using mlx-whisper.

Usage:
    python scripts/generate_subtitles.py                    # all videos in input/
    python scripts/generate_subtitles.py --file video.mp4   # single file
    python scripts/generate_subtitles.py --model medium     # specify model
"""

import argparse
import json
import sys
from pathlib import Path

SUPPORTED_FORMATS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.webm', '.flv', '.wmv'}

DEFAULT_MODEL = 'large-v3'
MODEL_REPOS = {
    'large-v3':       'mlx-community/whisper-large-v3-mlx',
    'large-v3-turbo': 'mlx-community/whisper-large-v3-turbo',
    'medium':         'mlx-community/whisper-medium-mlx',
    'small':          'mlx-community/whisper-small-mlx',
}


def format_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h  = ms // 3_600_000; ms %= 3_600_000
    m  = ms // 60_000;    ms %= 60_000
    s  = ms // 1_000;     ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_file(video_path: Path, output_dir: Path, model: str) -> None:
    import mlx_whisper

    repo = MODEL_REPOS.get(model, f'mlx-community/whisper-{model}-mlx')
    stem = video_path.stem

    print(f"  Transcribing: {video_path.name}  [{model}]")
    result = mlx_whisper.transcribe(
        str(video_path),
        path_or_hf_repo=repo,
        word_timestamps=True,
    )

    # Collect word-level timestamps
    words = []
    for segment in result.get('segments', []):
        for w in segment.get('words', []):
            words.append({
                'word':  w['word'],
                'start': round(float(w['start']), 3),
                'end':   round(float(w['end']),   3),
            })

    # words.json (used by /translate-srt)
    words_path = output_dir / f"{stem}.words.json"
    with open(words_path, 'w', encoding='utf-8') as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
    print(f"  → {words_path}")

    # English SRT
    srt_path = output_dir / f"{stem}.en.srt"
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(result.get('segments', []), 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")
    print(f"  → {srt_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate English subtitles using mlx-whisper')
    parser.add_argument('--file',   help='Single video file to process')
    parser.add_argument('--model',  default=DEFAULT_MODEL, choices=list(MODEL_REPOS),
                        help=f'Whisper model (default: {DEFAULT_MODEL})')
    parser.add_argument('--output', default=None, help='Output directory (default: <project>/output)')
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    output_dir = Path(args.output) if args.output else project_root / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        video_path = Path(args.file)
        if not video_path.is_absolute():
            video_path = project_root / video_path
        if not video_path.exists():
            print(f"ERROR: File not found: {video_path}", file=sys.stderr)
            sys.exit(1)
        transcribe_file(video_path, output_dir, args.model)
    else:
        input_dir = project_root / 'input'
        videos = sorted(f for f in input_dir.iterdir() if f.suffix.lower() in SUPPORTED_FORMATS)
        if not videos:
            print(f"No videos found in {input_dir}", file=sys.stderr)
            sys.exit(1)
        for v in videos:
            transcribe_file(v, output_dir, args.model)


if __name__ == '__main__':
    main()
