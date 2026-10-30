#!/usr/bin/env python3
"""본편 영상의 한국어 대사를 Whisper로 인식해 단어 단위 타임스탬프를 기록 (GitHub Actions용).

사용법: python transcribe.py <episode_dir>
출력:   <episode_dir>/transcript.json, transcript.txt
"""
import json
import os
import sys

from faster_whisper import WhisperModel

ep = os.path.abspath(sys.argv[1])
video = os.path.join(ep, "src_video.mp4")
model = WhisperModel("large-v3", device="cpu", compute_type="int8")
segments, info = model.transcribe(
    video, language="ko", word_timestamps=True, vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 250},
    initial_prompt="휴대폰 매장. 어서오세요, 기기변경이시죠? 네, 제일 싼 걸로요. 할부원금이 백오십만 원?!",
)
out = []
lines = []
for s in segments:
    words = [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)} for w in (s.words or [])]
    out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(), "words": words})
    lines.append(f"{s.start:6.2f} - {s.end:6.2f}  {s.text.strip()}")
json.dump(out, open(os.path.join(ep, "transcript.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(ep, "transcript.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
