#!/usr/bin/env python3
"""폰콕 릴스 합성 스크립트 (PC에서 실행, ffmpeg 필요).

사용법:
  python compose.py <episode_dir>

episode_dir/spec.json 을 읽어서
  1) 본편 영상·나레이션(본편/엔드카드)·BGM·효과음 다운로드
  2) 본편(15s) + 엔드카드(6s) 이어붙이기
  3) 상단 제목 / 가운데 나레이션 자막 / 하단 대사 자막을 ASS 자막으로 생성해 본편 구간에만 번인
  4) 오디오 믹싱: 본편 원음 + 나레이션 A(본편) + 나레이션 B(엔드카드) + BGM(본편 낮게, 엔드카드 높게) + 효과음
  5) episode_dir/<output> 로 저장
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request


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
    w, h = spec["width"], spec["height"]
    font = spec.get("font", "Noto Sans CJK KR")
    main_end = spec["main_duration"]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font},64,&H0000F0FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,8,60,60,48,1
Style: Narr,{font},78,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,5,120,120,0,1
Style: Dlg,{font},50,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,120,120,54,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    lines.append(f"Dialogue: 0,{ass_time(0)},{ass_time(main_end)},Title,,0,0,0,,{esc(spec['title'])}\n")
    for s in spec["narration_subtitles"]:
        lines.append(f"Dialogue: 1,{ass_time(s['start'])},{ass_time(s['end'])},Narr,,0,0,0,,{esc(s['text'])}\n")
    for s in spec.get("dialogue_subtitles", []):
        lines.append(f"Dialogue: 2,{ass_time(s['start'])},{ass_time(s['end'])},Dlg,,0,0,0,,{esc(s['text'])}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def ff_path(p: str) -> str:
    return p.replace("\\", "/").replace(":", "\\:")


def main() -> None:
    ep_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    with open(os.path.join(ep_dir, "spec.json"), encoding="utf-8") as f:
        spec = json.load(f)
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg 가 설치되어 있지 않습니다. PowerShell에서 winget install Gyan.FFmpeg 후 새 창에서 다시 실행해 주세요.")

    a = spec["assets"]
    video = os.path.join(ep_dir, "src_video.mp4")
    narr_a = os.path.join(ep_dir, "src_narr_main.mp3")
    narr_b = os.path.join(ep_dir, "src_narr_end.mp3")
    bgm = os.path.join(ep_dir, "src_bgm.mp3")
    sfx = os.path.join(ep_dir, "src_sfx.mp3")
    endcard = os.path.abspath(os.path.join(ep_dir, spec["endcard"]["file"]))
    if not os.path.exists(endcard):
        raise SystemExit(f"엔드카드 파일이 없습니다: {endcard}")

    download(a["video"]["url"], video)
    download(a["narration_main"]["url"], narr_a)
    download(a["narration_end"]["url"], narr_b)
    download(a["bgm"]["url"], bgm)
    download(a["sfx"]["url"], sfx)

    ass = os.path.join(ep_dir, "subs.ass")
    build_ass(spec, ass)

    mix = spec["mix"]
    fps = spec.get("fps", 30)
    w, h = spec["width"], spec["height"]
    main_d = spec["main_duration"]
    end_d = spec["endcard"]["duration"]
    total = main_d + end_d
    na_ms = int(a["narration_main"]["at"] * 1000)
    nb_ms = int(a["narration_end"]["at"] * 1000)
    sfx_ms = int(a["sfx"]["at"] * 1000)
    out = os.path.join(ep_dir, spec["output"])

    # 입력: 0 본편, 1 엔드카드, 2 나레이션A, 3 나레이션B, 4 BGM, 5 SFX
    fc = (
        # 본편 정규화 + 자막 번인 (자막은 본편 타임라인 기준)
        f"[0:v]trim=0:{main_d},setpts=PTS-STARTPTS,scale={w}:{h},fps={fps},"
        f"subtitles='{ff_path(ass)}'[v0];"
        f"[1:v]scale={w}:{h},fps={fps},setpts=PTS-STARTPTS[v1];"
        f"[v0][v1]concat=n=2:v=1:a=0[v];"
        # 본편 원음 (엔드카드 구간은 무음 패딩)
        f"[0:a]atrim=0:{main_d},asetpts=PTS-STARTPTS,volume={mix['video_audio']},apad=whole_dur={total}[a0];"
        f"[2:a]volume={mix['narration']},adelay={na_ms}|{na_ms}[a1];"
        f"[3:a]volume={mix['narration']},adelay={nb_ms}|{nb_ms}[a2];"
        # BGM: 본편은 낮게, 엔드카드에서 올리고 마지막 페이드아웃
        f"[4:a]atrim=0:{total},asetpts=PTS-STARTPTS,"
        f"volume='if(lt(t,{main_d}),{mix['bgm_main']},{mix['bgm_end']})':eval=frame,"
        f"afade=t=out:st={total-1.2}:d=1.2[a3];"
        f"[5:a]volume={mix['sfx']},adelay={sfx_ms}|{sfx_ms}[a4];"
        f"[a0][a1][a2][a3][a4]amix=inputs=5:duration=longest:normalize=0,"
        f"alimiter=limit=0.95,atrim=0:{total}[a]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", video, "-i", endcard, "-i", narr_a, "-i", narr_b, "-i", bgm, "-i", sfx,
        "-filter_complex", fc,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        out,
    ]
    print("합성 중...")
    subprocess.run(cmd, check=True)
    print(f"완료: {out}  (총 {total:.0f}초)")


if __name__ == "__main__":
    main()
