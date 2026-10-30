#!/usr/bin/env python3
"""합성 결과 검수 자료 생성 (GitHub Actions compose 워크플로 마지막 단계에서 실행).

출력 (episode_dir/qa/):
  - grid.jpg            : 0.5초 간격 전체 프레임 그리드 (어색한 컷·멈춤·왜곡 육안 확인용)
  - sub_boundaries.jpg  : 모든 자막 시작/끝 직후 프레임 (싱크 확인용)
  - report.txt          : 규칙 자동 점검 결과 (길이, 겹침, 자막 길이, 제목 핸드폰 단어, 나레이션-대사 겹침)
"""
import json
import os
import re
import subprocess
import sys

ep = os.path.abspath(sys.argv[1])
_sp = os.path.join(ep, "spec.resolved.json")
spec = json.load(open(_sp if os.path.exists(_sp) else os.path.join(ep, "spec.json"), encoding="utf-8"))
out_mp4 = os.path.join(ep, spec["output"])
qa = os.path.join(ep, "qa")
os.makedirs(qa, exist_ok=True)

dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out_mp4],
                           capture_output=True, text=True).stdout.strip())

# 1) 전체 그리드 (0.5s 간격, 최대 60장 → 10x6)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out_mp4, "-vf",
                "fps=2,crop=1080:608:0:656,scale=320:-1,tile=10x6", "-frames:v", "1",
                os.path.join(qa, "grid.jpg")], check=True)

# 2) 자막 경계 프레임
ass = open(os.path.join(ep, "subs.ass"), encoding="utf-8").read()
events = []
for m in re.finditer(r"Dialogue: \d+,(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+),(\w+),.*?,,(.*)", ass):
    st = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    en = int(m[4]) * 3600 + int(m[5]) * 60 + float(m[6])
    events.append((st, en, m[7], m[8]))
marks = sorted({round(e[0] + 0.08, 2) for e in events if e[2] != "Title"} | {round(e[1] - 0.08, 2) for e in events if e[2] != "Title"})
marks = [t for t in marks if 0 <= t < dur][:40]
frames = []
for i, t in enumerate(marks):
    f = os.path.join(qa, f"b_{i:02d}.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", out_mp4, "-frames:v", "1",
                    "-vf", f"scale=270:-1,drawtext=text='{t:.2f}':fontsize=22:fontcolor=lime:x=6:y=6", f], check=True)
    frames.append(f)
if frames:
    cols = 8
    rows = (len(frames) + cols - 1) // cols
    inputs = sum([["-i", f] for f in frames], [])
    pad = cols * rows - len(frames)
    fc = "".join(f"[{i}:v]" for i in range(len(frames)))
    if pad:
        fc += "".join(f"color=black:s=270x480:d=1[p{i}];[p{i}]" for i in range(pad))
    layout = "|".join(f"{(i % cols) * 270}_{(i // cols) * 480}" for i in range(cols * rows))
    srcs = "".join(f"[{i}:v]" for i in range(len(frames))) + "".join(f"[p{i}]" for i in range(pad))
    fc2 = ("".join(f"color=black:s=270x480:d=1[p{i}];" for i in range(pad))
           + srcs + f"xstack=inputs={cols*rows}:layout={layout}[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc2, "-map", "[o]",
                    "-frames:v", "1", os.path.join(qa, "sub_boundaries.jpg")], check=True)

# 3) 규칙 자동 점검
issues = []
total = spec["main_duration"] + spec["endcard"]["duration"]
if total > 30.05:
    issues.append(f"총 길이 {total:.1f}s > 30s")
if spec["main_duration"] < 20 and spec.get("episode") != "ep01_halloween":
    issues.append(f"본편 {spec['main_duration']:.1f}s < 22s (기승전결 부족 가능)")
title = spec["title"]
for w in ["폰", "핸드폰", "휴대폰", "견적", "매장", "폰콕", "요금제", "할부"]:
    if w in title.replace("[[", "").replace("]]", ""):
        issues.append(f"제목에 핸드폰 관련 단어 '{w}' 포함: {title!r}")
if "[[" not in title:
    issues.append("제목에 빨강 포인트 단어([[ ]]) 없음")
dlg = spec.get("dialogue_subtitles", [])
for seg in spec["narration"]:
    a, b = seg["at"], seg["at"] + seg["duration"]
    for d in dlg:
        if a < d["end"] and d["start"] < b:
            issues.append(f"나레이션({a:.2f}-{b:.2f}) 이 대사 자막({d['start']:.2f}-{d['end']:.2f} {d['text']!r}) 과 겹침")
narr_subs = [e for e in events if e[2] == "Narr"]
for e in narr_subs:
    if len(e[3].replace("\\N", "")) > 14:
        issues.append(f"나레이션 자막 조각이 김(14자 초과): {e[3]!r}")
for d in dlg:
    if not d["text"].strip():
        issues.append("빈 대사 자막")
if "keep_segments" in spec:
    issues.append(f"[info] 컷편집 적용: {spec['keep_segments']}")

with open(os.path.join(qa, "report.txt"), "w", encoding="utf-8") as f:
    f.write(f"output={spec['output']} duration={dur:.2f}s main={spec['main_duration']}s\n")
    f.write("자막 이벤트:\n")
    for st, en, sty, txt in events:
        f.write(f"  {sty:5s} {st:6.2f}-{en:6.2f}  {txt}\n")
    f.write("\n점검 결과:\n")
    f.write("\n".join("  - " + i for i in issues) if issues else "  문제 없음\n")
print(open(os.path.join(qa, "report.txt"), encoding="utf-8").read())
