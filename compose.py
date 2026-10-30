#!/usr/bin/env python3
"""폰콕 릴스 합성 스크립트 (GitHub Actions / 로컬, ffmpeg 필요).

사용법:
  python compose.py <episode_dir>            # 합성
  python compose.py <episode_dir> --analyze  # 본편 음성 구간 분석만 (speech_segments.txt 생성)

레이아웃 (9:16, 1080x1920):
  - 가로 16:9 본편을 1080x608 로 축소해 세로 캔버스 가운데에 배치 → 위아래 검은 띠
  - 위 띠: 어그로 제목 (노랑)
  - 영상 가운데: 나레이션 자막 (흰색, 큼)
  - 아래 띠: 대사 자막 (흰색)
  - 엔드카드도 같은 방식으로 가운데 배치

오디오:
  - 본편 원음 + 나레이션 세그먼트(여러 개, 각자 시작 시각) + BGM + 효과음
  - 나레이션 구간에서는 본편 원음과 BGM을 자동으로 낮춤(더킹)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

W, H = 1080, 1920          # 세로 캔버스
VW, VH = 1080, 608         # 16:9 영상 축소 크기
VY = (H - VH) // 2         # 영상 상단 y = 656


def download(url: str, dest: str) -> None:
    if not url:
        raise SystemExit(f"URL 비어 있음: {dest}")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    print(f"다운로드: {os.path.basename(dest)}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def esc(text: str) -> str:
    return text.replace("\n", "\\N")


def build_ass(spec: dict, path: str) -> None:
    font = spec.get("font", "Noto Sans CJK KR")
    main_end = spec["main_duration"]
    # 위 띠 높이 656: 제목은 띠 아래쪽(영상 바로 위)에, 아래 띠: 대사는 띠 위쪽(영상 바로 아래)에
    title_margin_v = H - VY + 40           # 하단 기준 마진 → 제목 하단이 영상 위 40px
    dlg_margin_v = VY + VH + 40            # 상단 기준 마진 → 대사 상단이 영상 아래 40px (아래 검은 띠)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font},62,&H0000F0FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,2,50,50,{title_margin_v},1
Style: Narr,{font},60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,5,60,60,0,1
Style: Dlg,{font},50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,8,50,50,{dlg_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    lines.append(f"Dialogue: 0,{ass_time(0)},{ass_time(main_end)},Title,,0,0,0,,{esc(spec['title'])}\n")
    for seg in spec["narration"]:
        if seg.get("subtitle"):
            lines.append(f"Dialogue: 1,{ass_time(seg['at'])},{ass_time(seg['at'] + seg['duration'] + 0.3)},Narr,,0,0,0,,{esc(seg['subtitle'])}\n")
    for s in spec.get("dialogue_subtitles", []):
        lines.append(f"Dialogue: 2,{ass_time(s['start'])},{ass_time(s['end'])},Dlg,,0,0,0,,{esc(s['text'])}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def ff_path(p: str) -> str:
    return p.replace("\\", "/").replace(":", "\\:")


def analyze_speech(video: str, out_txt: str) -> None:
    """본편 오디오에서 음성(대사) 구간을 추정해 기록. 300~3400Hz 대역 통과 후 silencedetect."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", video, "-vn",
        "-af", "highpass=f=300,lowpass=f=3400,silencedetect=noise=-28dB:d=0.35",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                               capture_output=True, text=True).stdout.strip())
    # 무음 구간의 보수 = 음성 구간
    speech = []
    cur = 0.0
    for s, e in zip(starts, ends if len(ends) == len(starts) else ends + [dur]):
        if s - cur >= 0.25:
            speech.append((cur, s))
        cur = e
    if dur - cur >= 0.25:
        speech.append((cur, dur))
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"duration={dur:.2f}\n")
        for a, b in speech:
            f.write(f"speech {a:.2f} {b:.2f}\n")
    print(open(out_txt, encoding="utf-8").read())


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    analyze_only = "--analyze" in sys.argv
    ep_dir = os.path.abspath(args[0] if args else ".")
    with open(os.path.join(ep_dir, "spec.json"), encoding="utf-8") as f:
        spec = json.load(f)
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg 가 없습니다.")

    a = spec["assets"]
    video = os.path.join(ep_dir, "src_video.mp4")
    download(a["video"]["url"], video)

    if analyze_only:
        analyze_speech(video, os.path.join(ep_dir, "speech_segments.txt"))
        return

    bgm = os.path.join(ep_dir, "src_bgm.mp3")
    sfx = os.path.join(ep_dir, "src_sfx.mp3")
    download(a["bgm"]["url"], bgm)
    download(a["sfx"]["url"], sfx)
    narr_files = []
    for i, seg in enumerate(spec["narration"]):
        p = os.path.join(ep_dir, f"src_narr_{i}.mp3")
        download(seg["url"], p)
        narr_files.append(p)
    endcard = os.path.abspath(os.path.join(ep_dir, spec["endcard"]["file"]))
    if not os.path.exists(endcard):
        raise SystemExit(f"엔드카드 파일이 없습니다: {endcard}")

    ass = os.path.join(ep_dir, "subs.ass")
    build_ass(spec, ass)

    mix = spec["mix"]
    fps = spec.get("fps", 30)
    main_d = spec["main_duration"]
    end_d = spec["endcard"]["duration"]
    total = main_d + end_d
    sfx_ms = int(a["sfx"]["at"] * 1000)
    out = os.path.join(ep_dir, spec["output"])

    # 나레이션 구간에서 원음/BGM 더킹: 구간 밖 1.0, 구간 안 duck 배율
    duck = mix.get("duck", 0.35)
    conds = "+".join(f"between(t,{s['at']-0.15},{s['at']+s['duration']+0.15})" for s in spec["narration"])
    duck_expr = f"'if(gt({conds},0),{duck},1)'"

    n = len(narr_files)
    # 입력: 0 본편, 1 엔드카드, 2 BGM, 3 SFX, 4.. 나레이션들
    fc = []
    fc.append(
        f"[0:v]trim=0:{main_d},setpts=PTS-STARTPTS,scale={VW}:{VH}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:{VY}:black,fps={fps},subtitles='{ff_path(ass)}'[v0]"
    )
    fc.append(
        f"[1:v]scale={VW}:{VH}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:{VY}:black,"
        f"fps={fps},setpts=PTS-STARTPTS[v1]"
    )
    fc.append("[v0][v1]concat=n=2:v=1:a=0[v]")
    fc.append(
        f"[0:a]atrim=0:{main_d},asetpts=PTS-STARTPTS,volume={mix['video_audio']},"
        f"volume={duck_expr}:eval=frame,apad=whole_dur={total}[a0]"
    )
    fc.append(
        f"[2:a]atrim=0:{total},asetpts=PTS-STARTPTS,"
        f"volume='if(lt(t,{main_d}),{mix['bgm_main']},{mix['bgm_end']})':eval=frame,"
        f"volume={duck_expr}:eval=frame,afade=t=out:st={total-1.2}:d=1.2[a1]"
    )
    fc.append(f"[3:a]volume={mix['sfx']},adelay={sfx_ms}|{sfx_ms}[a2]")
    labels = ["[a0]", "[a1]", "[a2]"]
    for i, seg in enumerate(spec["narration"]):
        ms = int(seg["at"] * 1000)
        fc.append(f"[{4+i}:a]loudnorm=I=-14:TP=-1.5:LRA=7,volume={mix['narration']},adelay={ms}|{ms}[n{i}]")
        labels.append(f"[n{i}]")
    fc.append(
        "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        f"alimiter=limit=0.95,atrim=0:{total}[a]"
    )
    cmd = ["ffmpeg", "-y", "-i", video, "-i", endcard, "-i", bgm, "-i", sfx]
    for p in narr_files:
        cmd += ["-i", p]
    cmd += [
        "-filter_complex", ";".join(fc),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        out,
    ]
    print("합성 중...")
    subprocess.run(cmd, check=True)
    print(f"완료: {out}  ({W}x{H}, 총 {total:.0f}초)")


if __name__ == "__main__":
    main()
