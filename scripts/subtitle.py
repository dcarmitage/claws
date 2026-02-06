#!/usr/bin/env python3
"""
subtitle.py - Lightweight video/audio subtitle tool
Transcribes media using faster-whisper, generates SRT, optionally burns or embeds subs.

Usage:
  python3 subtitle.py input.mp4                     # generate .srt only
  python3 subtitle.py input.mp4 --burn              # burn subs into video
  python3 subtitle.py input.mp4 --embed             # soft-embed subs
  python3 subtitle.py input.mp4 --burn --translate   # placeholder for future translation
  python3 subtitle.py input.mp4 -o output.srt       # custom output path
  python3 subtitle.py input.mp4 --model large-v3    # use different model
"""

import argparse
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# SRT formatting helpers
# ---------------------------------------------------------------------------

MAX_LINE_CHARS = 42
MAX_LINES = 2

# Punctuation where we prefer to break
_BREAK_RE = re.compile(r'([,;:!?\.\-–—])\s+')


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _smart_wrap(text: str, max_chars: int = MAX_LINE_CHARS, max_lines: int = MAX_LINES) -> str:
    """
    Wrap subtitle text with natural breaks at punctuation,
    max_chars per line, max_lines lines.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text

    # Try breaking at punctuation near the midpoint
    mid = len(text) // 2
    best_break = None
    best_dist = len(text)

    for match in _BREAK_RE.finditer(text):
        pos = match.end()
        dist = abs(pos - mid)
        if dist < best_dist and pos < len(text) - 3:
            best_dist = dist
            best_break = pos

    if best_break and best_break < max_chars + 5:
        line1 = text[:best_break].strip()
        line2 = text[best_break:].strip()
        # Ensure each line fits
        line1 = line1[:max_chars]
        line2 = line2[:max_chars]
        return f"{line1}\n{line2}"

    # Fallback: textwrap
    lines = textwrap.wrap(text, width=max_chars, max_lines=max_lines,
                          break_long_words=False, break_on_hyphens=True)
    return "\n".join(lines[:max_lines])


def segments_to_srt(segments) -> str:
    """Convert faster-whisper segments to SRT string."""
    srt_blocks = []
    for idx, seg in enumerate(segments, 1):
        start_ts = _format_timestamp(seg.start)
        end_ts = _format_timestamp(seg.end)
        text = _smart_wrap(seg.text.strip())
        srt_blocks.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")
    return "\n".join(srt_blocks)


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(input_path: str, model_size: str = "base", language: str | None = None):
    """Transcribe using faster-whisper. Returns list of segments."""
    from faster_whisper import WhisperModel

    print(f"[subtitle] Loading model '{model_size}' (int8, cpu)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"[subtitle] Transcribing: {input_path}")
    kwargs = {"beam_size": 5, "vad_filter": True}
    if language:
        kwargs["language"] = language

    segments_gen, info = model.transcribe(input_path, **kwargs)
    print(f"[subtitle] Detected language: {info.language} (prob {info.language_probability:.2f})")

    # Materialise generator so we can reuse
    segments = list(segments_gen)
    print(f"[subtitle] Got {len(segments)} segment(s)")
    return segments, info


# ---------------------------------------------------------------------------
# ffmpeg operations
# ---------------------------------------------------------------------------

def burn_subtitles(input_path: str, srt_path: str, output_path: str):
    """Burn (hardcode) subtitles into video using ffmpeg."""
    # Escape special chars for ffmpeg subtitles filter
    srt_escaped = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    style = (
        "FontName=Arial,"
        "FontSize=22,"
        "PrimaryColour=&H00FFFFFF,"     # white
        "OutlineColour=&H00000000,"     # black outline
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"                  # bottom center
        "MarginV=40"
    )

    filter_str = f"subtitles='{srt_escaped}':force_style='{style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]
    print(f"[subtitle] Burning subs → {output_path}")
    subprocess.run(cmd, check=True)
    print(f"[subtitle] Done: {output_path}")


def embed_subtitles(input_path: str, srt_path: str, output_path: str):
    """Embed soft subtitles as a stream in the container."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", srt_path,
        "-c:v", "copy", "-c:a", "copy",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng",
        output_path,
    ]
    print(f"[subtitle] Embedding soft subs → {output_path}")
    subprocess.run(cmd, check=True)
    print(f"[subtitle] Done: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Transcribe & subtitle videos")
    parser.add_argument("input", help="Input video or audio file")
    parser.add_argument("-o", "--output", help="Output SRT path (default: input.srt)")
    parser.add_argument("--burn", action="store_true", help="Burn subtitles into video")
    parser.add_argument("--embed", action="store_true", help="Embed soft subtitles")
    parser.add_argument("--model", default="base", help="Whisper model size (default: base)")
    parser.add_argument("--language", default=None, help="Force language code (e.g. en, es)")
    parser.add_argument("--translate", action="store_true",
                        help="[placeholder] Translate to English (future feature)")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(f"[subtitle] Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    base = os.path.splitext(input_path)[0]
    srt_path = args.output or f"{base}.srt"

    if args.translate:
        print("[subtitle] Note: --translate is a placeholder for future translation support")

    # Transcribe
    try:
        segments, info = transcribe(input_path, model_size=args.model, language=args.language)
    except Exception as e:
        err_msg = str(e)
        if "index out of range" in err_msg or "audio" in err_msg.lower():
            print(f"[subtitle] Warning: could not decode audio (file may have no audio track)")
            segments, info = [], None
        else:
            raise

    if not segments:
        print("[subtitle] Warning: no speech segments detected")
        # Write empty SRT
        Path(srt_path).write_text("")
    else:
        srt_content = segments_to_srt(segments)
        Path(srt_path).write_text(srt_content, encoding="utf-8")
        print(f"[subtitle] SRT written: {srt_path}")

    # Burn or embed (only if we have subtitles)
    if args.burn:
        if segments:
            out_video = f"{base}_subtitled.mp4"
            burn_subtitles(input_path, srt_path, out_video)
        else:
            print("[subtitle] Skipping --burn: no subtitle segments to burn")

    if args.embed:
        if segments:
            out_video = f"{base}_softsub.mp4"
            embed_subtitles(input_path, srt_path, out_video)
        else:
            print("[subtitle] Skipping --embed: no subtitle segments to embed")

    print("[subtitle] All done ✓")


if __name__ == "__main__":
    main()
