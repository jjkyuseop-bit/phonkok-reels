#!/usr/bin/env python3
"""본편 영상의 한국어 대사를 Whisper로 인식 (GitHub Actions용).

- 대사 자막은 반드시 실제 발화와 동일해야 하므로, 대본으로 편향시키지 않고(initial_prompt 없음) 두 가지 설정으로 받아쓴 뒤
  둘 다 기록한다. 합성 담당은 두 결과가 일치하는 부분을 우선 채택하고, 불일치 구간은 더 자연스러운 한국어 쪽을 쓴다.
- 입력은 음성 대역(200~4000Hz)으로 필터링하고 라우드니스 정규화한 wav 를 사용해 배경음 영향을 줄인다.

사용법: python transcribe.py <episode_dir>
출력:   transcript.json / transcript.txt (설정 A: large-v3 beam 8, 설정 B: large-v3 temperature fallback 포함)
"""
import json
import os
import subprocess
import sys

from faster_whisper import WhisperModel

ep = os.path.abspath(sys.argv[1])
video = os.path.join(ep, "src_video.mp4")
wav = os.path.join(ep, "src_speech.wav")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                "-af", "highpass=f=200,lowpass=f=4000,loudnorm=I=-16:TP=-1.5:LRA=11", wav], check=True)

model = WhisperModel("large-v3", device="cpu", compute_type="int8")


def run(**kw):
    segs, _ = model.transcribe(wav, language="ko", word_timestamps=True, vad_filter=True,
                               vad_parameters={"min_silence_duration_ms": 200, "speech_pad_ms": 150},
                               condition_on_previous_text=False, **kw)
    out = []
    for s in segs:
        words = [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2), "p": round(w.probability, 2)} for w in (s.words or [])]
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "avg_logprob": round(s.avg_logprob, 2), "words": words})
    return out


A = run(beam_size=8, best_of=8, temperature=0.0)
B = run(beam_size=5, temperature=[0.0, 0.2, 0.4])

# C: 에너지 기반 음성 구간(speech_segments.txt)별 개별 인식 — 짧은 한국어 대사는 전체 통과보다 구간 단위가 훨씬 잘 잡힌다
C = []
seg_file = os.path.join(ep, "speech_segments.txt")
if os.path.exists(seg_file):
    for line in open(seg_file, encoding="utf-8"):
        if not line.startswith("speech"):
            continue
        _, a, b = line.split()
        a, b = max(0.0, float(a) - 0.25), float(b) + 0.35
        part = os.path.join(ep, "seg.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                        "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", part], check=True)
        res = []
        for kw in ({"beam_size": 8, "temperature": 0.0}, {"beam_size": 5, "temperature": [0.0, 0.2, 0.4]}):
            segs, _ = model.transcribe(part, language="ko", word_timestamps=True, vad_filter=False,
                                       condition_on_previous_text=False, **kw)
            txt, words = [], []
            for sg in segs:
                txt.append(sg.text.strip())
                for w in (sg.words or []):
                    words.append({"w": w.word, "s": round(a + w.start, 2), "e": round(a + w.end, 2), "p": round(w.probability, 2)})
            res.append({"text": " ".join(txt), "words": words})
        C.append({"start": round(a, 2), "end": round(b, 2), "A": res[0], "B": res[1]})

json.dump({"A": A, "B": B, "C": C}, open(os.path.join(ep, "transcript.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
lines = ["=== A (beam 8, temp 0) ==="]
lines += [f"{s['start']:6.2f} - {s['end']:6.2f}  {s['text']}   (lp {s['avg_logprob']})" for s in A]
lines += ["", "=== B (beam 5, temp fallback) ==="]
lines += [f"{s['start']:6.2f} - {s['end']:6.2f}  {s['text']}   (lp {s['avg_logprob']})" for s in B]
lines += ["", "=== A words ==="]
for s in A:
    lines.append(" ".join(f"{w['w'].strip()}[{w['s']}-{w['e']}:{w['p']}]" for w in s["words"]))
lines += ["", "=== C (구간별 개별 인식: 시작-끝 | A | B) ==="]
for c in C:
    lines.append(f"{c['start']:6.2f} - {c['end']:6.2f}  A: {c['A']['text']}   | B: {c['B']['text']}")
    lines.append("        " + " ".join(f"{w['w'].strip()}[{w['s']}-{w['e']}:{w['p']}]" for w in c["A"]["words"]))
open(os.path.join(ep, "transcript.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
