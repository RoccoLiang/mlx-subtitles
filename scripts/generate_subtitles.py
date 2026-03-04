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


def transcribe_file(video_path: Path, output_dir: Path, model: str, language: str | None = None) -> None:
    import mlx_whisper

    repo = MODEL_REPOS.get(model, f'mlx-community/whisper-{model}-mlx')
    stem = video_path.stem

    lang_label = f", lang={language}" if language else ""
    print(f"  Transcribing: {video_path.name}  [{model}{lang_label}]")
    print(f"  （轉錄中，請稍候…）", flush=True)
    result = mlx_whisper.transcribe(
        str(video_path),
        path_or_hf_repo=repo,
        word_timestamps=True,
        language=language,
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

    seg_count = len(result.get('segments', []))

    # words.json (used by /subtitles-srt)
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

    project_root = Path(__file__).parent.parent
    output_dir = Path(args.output) if args.output else project_root / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)

    def should_skip(video_path: Path) -> bool:
        if not args.skip_existing:
            return False
        out = output_dir / f"{video_path.stem}.words.json"
        if out.exists():
            print(f"  Skipping (already exists): {out}")
            return True
        return False

    if args.file:
        video_path = Path(args.file)
        if not video_path.is_absolute():
            video_path = project_root / video_path
        if not video_path.exists():
            print(f"ERROR: File not found: {video_path}", file=sys.stderr)
            sys.exit(1)
        if not should_skip(video_path):
            transcribe_file(video_path, output_dir, args.model, args.language)
    else:
        input_dir = project_root / 'input'
        videos = sorted(f for f in input_dir.iterdir() if f.suffix.lower() in SUPPORTED_FORMATS)
        if not videos:
            print(f"No videos found in {input_dir}", file=sys.stderr)
            sys.exit(1)
        for v in videos:
            if not should_skip(v):
                transcribe_file(v, output_dir, args.model, args.language)


if __name__ == '__main__':
    main()
