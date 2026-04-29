#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parents[1]
AUDIO_DIR = BASE_DIR / "audio"
OUT_DIR = BASE_DIR / "transcripts"
MODEL = "gpt-4o-transcribe-diarize"

PARTS = [
    {
        "index": 1,
        "label": "НА правки 4_1",
        "chunks": [AUDIO_DIR / "na_pravki_4_1.mp3"],
    },
    {
        "index": 2,
        "label": "НА правки 4_2",
        "chunks": [AUDIO_DIR / "na_pravki_4_2.mp3"],
    },
    {
        "index": 3,
        "label": "НА правки 4_3",
        "chunks": sorted((AUDIO_DIR / "chunks").glob("na_pravki_4_3_chunk_*.mp3")),
    },
]


def duration_sec(path: Path) -> float:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(raw)


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return json.loads(value.model_dump_json())


def ts(sec: float, *, comma: bool = False) -> str:
    sec = max(sec, 0.0)
    whole = int(sec)
    ms = int(round((sec - whole) * 1000))
    if ms == 1000:
        whole += 1
        ms = 0
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    sep = "," if comma else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def ts_short(sec: float) -> str:
    sec = max(sec, 0.0)
    whole = int(sec)
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def extract_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("segments", "speaker_segments", "diarization", "diarized_segments"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    # Some SDK/API variants nest diarized output under a top-level transcript object.
    for value in payload.values():
        if isinstance(value, dict):
            nested = extract_segments(value)
            if nested:
                return nested
    return []


def segment_text(segment: dict[str, Any]) -> str:
    value = segment.get("text") or segment.get("transcript") or segment.get("content") or ""
    return str(value).strip()


def segment_speaker(segment: dict[str, Any]) -> str | None:
    value = segment.get("speaker") or segment.get("speaker_label") or segment.get("label")
    if value is None:
        return None
    return str(value).strip() or None


def segment_time(segment: dict[str, Any], key: str, fallback: float) -> float:
    value = segment.get(key)
    if value is None and key == "start":
        value = segment.get("start_time")
    if value is None and key == "end":
        value = segment.get("end_time")
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    combined: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "model": MODEL,
        "parts": [],
    }
    offset = 0.0

    for part in PARTS:
        index = int(part["index"])
        label = str(part["label"])
        chunks = list(part["chunks"])
        if not chunks:
            raise FileNotFoundError(f"No audio chunks for {label}")
        for chunk in chunks:
            if not chunk.is_file():
                raise FileNotFoundError(chunk)

        part_global_start = offset
        part_segments: list[dict[str, Any]] = []
        chunk_local_offset = 0.0
        chunk_meta: list[dict[str, Any]] = []

        for chunk_index, audio_path in enumerate(chunks, start=1):
            duration = duration_sec(audio_path)
            if len(chunks) == 1:
                raw_path = OUT_DIR / f"openai_part_{index}_raw.json"
            else:
                raw_path = OUT_DIR / f"openai_part_{index}_chunk_{chunk_index}_raw.json"
            print(
                f"[part {index}/{len(PARTS)} chunk {chunk_index}/{len(chunks)}] "
                f"{label}: {duration / 60:.2f} min, "
                f"{audio_path.stat().st_size / 1024 / 1024:.2f} MB",
                flush=True,
            )

            if raw_path.exists():
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
                print(f"  skip API: {raw_path.name} already exists", flush=True)
            else:
                with audio_path.open("rb") as audio_file:
                    response = client.audio.transcriptions.create(
                        model=MODEL,
                        file=audio_file,
                        response_format="diarized_json",
                        chunking_strategy="auto",
                    )
                payload = as_dict(response)
                raw_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            local_segments = extract_segments(payload)
            for local_id, segment in enumerate(local_segments, start=1):
                if not isinstance(segment, dict):
                    continue
                text = segment_text(segment)
                if not text:
                    continue
                chunk_start = segment_time(segment, "start", 0.0)
                chunk_end = segment_time(segment, "end", chunk_start)
                local_start = chunk_local_offset + chunk_start
                local_end = chunk_local_offset + chunk_end
                item = {
                    "id": len(combined) + 1,
                    "part": index,
                    "part_label": label,
                    "chunk": chunk_index,
                    "local_id": local_id,
                    "speaker": segment_speaker(segment),
                    "local_start": local_start,
                    "local_end": local_end,
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "global_start": part_global_start + local_start,
                    "global_end": part_global_start + local_end,
                    "text": text,
                }
                combined.append(item)
                part_segments.append(item)

            chunk_meta.append(
                {
                    "index": chunk_index,
                    "audio": str(audio_path),
                    "duration_sec": duration,
                    "local_start": chunk_local_offset,
                    "local_end": chunk_local_offset + duration,
                    "raw_response": str(raw_path),
                }
            )
            chunk_local_offset += duration

        part_segments_path = OUT_DIR / f"openai_part_{index}_segments.json"
        part_segments_path.write_text(
            json.dumps(part_segments, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (OUT_DIR / f"openai_part_{index}.txt").write_text(
            "\n".join(item["text"] for item in part_segments) + "\n",
            encoding="utf-8",
        )

        meta["parts"].append(
            {
                "index": index,
                "label": label,
                "duration_sec": chunk_local_offset,
                "global_start": part_global_start,
                "global_end": part_global_start + chunk_local_offset,
                "segments": len(part_segments),
                "chunks": chunk_meta,
            }
        )
        offset += chunk_local_offset

    meta["total_duration_sec"] = offset
    meta["segments"] = len(combined)

    (OUT_DIR / "transcript_segments.json").write_text(
        json.dumps({"meta": meta, "segments": combined}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    srt_lines: list[str] = []
    for idx, segment in enumerate(combined, start=1):
        speaker = f"{segment['speaker']}: " if segment.get("speaker") else ""
        srt_lines.extend(
            [
                str(idx),
                f"{ts(segment['global_start'], comma=True)} --> {ts(segment['global_end'], comma=True)}",
                f"[{segment['part_label']} / {ts_short(segment['local_start'])}] {speaker}{segment['text']}",
                "",
            ]
        )
    (OUT_DIR / "transcript_full.srt").write_text("\n".join(srt_lines), encoding="utf-8")

    vtt_lines = ["WEBVTT", ""]
    for segment in combined:
        speaker = f"{segment['speaker']}: " if segment.get("speaker") else ""
        vtt_lines.extend(
            [
                f"{ts(segment['global_start'])} --> {ts(segment['global_end'])}",
                f"[{segment['part_label']} / {ts_short(segment['local_start'])}] {speaker}{segment['text']}",
                "",
            ]
        )
    (OUT_DIR / "transcript_full.vtt").write_text("\n".join(vtt_lines), encoding="utf-8")

    md_lines = [
        "# НА правки 4 — OpenAI транскрипция",
        "",
        f"- Модель: `{MODEL}`",
        f"- Общая длительность: `{ts_short(offset)}`",
        f"- Сегментов: `{len(combined)}`",
        "",
        "## Части",
        "",
    ]
    for part in meta["parts"]:
        md_lines.append(
            f"- `{part['label']}`: global `{ts_short(part['global_start'])}`–"
            f"`{ts_short(part['global_end'])}`, local `{ts_short(part['duration_sec'])}`, "
            f"segments `{part['segments']}`"
        )
    md_lines.extend(["", "## Транскрипт", ""])
    txt_lines: list[str] = []
    for segment in combined:
        speaker = f"{segment['speaker']}: " if segment.get("speaker") else ""
        heading = (
            f"{ts_short(segment['global_start'])}–{ts_short(segment['global_end'])} · "
            f"{segment['part_label']} · local {ts_short(segment['local_start'])}"
        )
        md_lines.extend([f"### {heading}", "", f"{speaker}{segment['text']}", ""])
        txt_lines.append(
            f"[{ts_short(segment['global_start'])} | {segment['part_label']} "
            f"{ts_short(segment['local_start'])}] {speaker}{segment['text']}"
        )

    (OUT_DIR / "transcript_full.md").write_text("\n".join(md_lines), encoding="utf-8")
    (OUT_DIR / "transcript_full.txt").write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    print(f"Done: {len(combined)} segments, {offset / 60:.2f} min", flush=True)
    print(f"Output: {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
