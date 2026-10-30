#!/usr/bin/env python3
"""미인식 음성 구간 집중 분석 (GitHub Actions용).

사용법: python probe.py <episode_dir> <segments_json>
segments_json: [{"start":0.7,"end":1.4,"candidates":["수고하셨습니다","안녕히 계세요"]}, ...]

각 구간을 넉넉히 잘라(앞뒤 0.3s) 다음을 모두 돌린다:
  - large-v3 / medium 두 모델, 편향 없이 beam 8
  - 편향 없이 temperature 0.4 샘플링 5회 (합의 확인)
  - 대본 후보를 initial_prompt 로 준 편향 인식 (후보 검증용; 단독 근거로 쓰지 않음)
  - 음성 대역 필터 유무 두 가지 전처리
결과를 probe.txt / probe.json 으로 남긴다. 최종 채택은 사람이(합성 담당이) 판단한다.
"""
import json
import os
import subprocess
import sys
from collections import Counter

from faster_whisper import WhisperModel

ep = os.path.abspath(sys.argv[1])
segments = json.load(open(sys.argv[2], encoding="utf-8"))
video = os.path.join(ep, "src_video.mp4")

models = {"large-v3": WhisperModel("large-v3", device="cpu", compute_type="int8"),
          "medium": WhisperModel("medium", device="cpu", compute_type="int8")}


def cut(a, b, filt, path):
    af = "loudnorm=I=-16:TP=-1.5:LRA=11"
    if filt:
        af = "highpass=f=200,lowpass=f=4000," + af
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                    "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-af", af, path], check=True)


def rec(model, path, **kw):
    segs, _ = model.transcribe(path, language="ko", word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=False, **kw)
    txt, words = [], []
    for s in segs:
        txt.append(s.text.strip())
        words += [(w.word.strip(), round(w.probability, 2)) for w in (s.words or [])]
    return " ".join(txt), words


out, lines = [], []
for i, sg in enumerate(segments):
    a, b = max(0.0, sg["start"] - 0.3), sg["end"] + 0.3
    item = {"start": sg["start"], "end": sg["end"], "runs": []}
    lines.append(f"\n##### 구간 {i+1}: {sg['start']}-{sg['end']}s (후보: {sg.get('candidates')})")
    for filt in (False, True):
        wav = os.path.join(ep, f"probe_{i}_{int(filt)}.wav")
        cut(a, b, filt, wav)
        for mname, m in models.items():
            t, w = rec(m, wav, beam_size=8, best_of=8, temperature=0.0)
            item["runs"].append({"model": mname, "filter": filt, "mode": "unbiased", "text": t, "words": w})
            lines.append(f"  [{mname} filt={int(filt)} 편향없음]  {t}   {w}")
        m = models["large-v3"]
        samples = []
        for k in range(5):
            t, _ = rec(m, wav, beam_size=1, temperature=0.4)
            samples.append(t)
        c = Counter(samples)
        item["runs"].append({"model": "large-v3", "filter": filt, "mode": "sample x5", "text": dict(c)})
        lines.append(f"  [large-v3 filt={int(filt)} 샘플링5]  {dict(c)}")
        for cand in sg.get("candidates", []):
            t, w = rec(m, wav, beam_size=8, temperature=0.0, initial_prompt=cand)
            item["runs"].append({"model": "large-v3", "filter": filt, "mode": f"biased:{cand}", "text": t, "words": w})
            lines.append(f"  [large-v3 filt={int(filt)} 편향:{cand}]  {t}   {w}")
    out.append(item)

json.dump(out, open(os.path.join(ep, "probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(ep, "probe.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
