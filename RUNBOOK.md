# 폰콕 릴스 주간 자동 제작 런북 (매주 화요일 실행)

이 문서는 예약 작업이 새 세션에서 그대로 따라 하는 절차다. **FORMAT.md 의 규칙은 전부 강제**이며, 사람 확인 없이 끝까지 진행하고 게시한다.

## 0. 준비 (매 실행)
1. `gh api user` 로 GitHub 연결 확인. 저장소 `jjkyuseop-bit/phonkok-reels` 가 세션에 없으면 add_repo(owner=jjkyuseop-bit, repo=phonkok-reels, access=push) 후 `/home/claude/phonkok-reels` 에 clone. 이미 있으면 `git pull`.
2. Runway `whoami` 로 Pro 플랜·크레딧 확인 (영상 모델 목록이 비어 있으면 중단하고 알림).
3. Metricool `getBrandSettings` 로 brand 7556654(phon.kok) 확인.
4. `FORMAT.md` 와 `ep*/script.md` 전부 읽기 (소재 중복 방지).

## 1. 지난 편 성과 확인
- Metricool `getAnalyticsDataByMetrics` 로 지난 편(인스타 릴스·유튜브 숏츠) 조회수·도달·좋아요·저장·공유·댓글·평균 시청 시간을 가져온다.
- 결과를 `reports/YYYY-MM-DD.md` 에 기록하고, 다음 편에 반영할 한 줄 교훈을 적는다 (예: 3초 이탈 높음 → 훅 더 세게).
- 데이터가 아직 없으면 "데이터 없음"으로 기록하고 진행.

## 2. 기획
- 제목: FORMAT.md "제목(훅) 원칙" 준수 — 핸드폰·폰콕과 무관해 보이는 보편적 어그로. 포인트 단어 1개를 `[[ ]]`로 표시.
- 구조: 기(0~4s 훅) / 승(4~11s 코믹 전개) / 전(11~18s 반전) / 결(18~23s 폰콕으로 해소) + 엔드카드 6s.
- 시즌·시사 소재 우선. 기존 에피소드와 소재 중복 금지.
- 대사는 짧고 명확하게 3~5줄. 나레이션은 어절 단위 조각으로 설계하고 **대사와 겹치지 않는 구간**에만 배치할 계획을 세운다.
- 새 폴더 `epNN_<slug>/` 에 `script.md` 작성.

## 3. 생성 (Runway MCP)
- 영상: `generate_video` model=seedance-2.5, ratio=16:9, resolution=1080p, generateAudio=true, duration 12 × 2클립(동일 인물·의상·장소 묘사 반복) 또는 단일 24s 이내. 프롬프트 끝: "No on-screen text, no captions, no logos. No music." 인물·핵심 동작은 중앙에.
- 두 클립이면 `stitch_videos` 로 합쳐 하나의 taskId 를 만든다.
- **생성 결과를 반드시 확인**: `get_task` 로 영상 URL을 얻고, 아래 4단계의 analyze 워크플로가 만드는 contact_sheet.jpg 와 transcript 를 보고 실제 화면·대사를 파악한 뒤에만 제목·나레이션·캡션을 확정한다. 프롬프트에 넣었지만 안 나온 장면은 쓰지 않는다.
- 나레이션 목소리: `search_voices`(language=ko)에서 영상 톤에 맞는 네이티브 보이스 선택. `generate_speech` model=eleven_v4, 조각(문장) 단위로 각각 생성.
- BGM: `generate_music` model=lyria-3-clip, 30초, 컨셉에 맞는 톤. 효과음: `generate_sound_effect` 반전 지점용 2~3초.
- 크레딧 상한: 편당 1,100 크레딧. 넘길 것 같으면 해상도/길이를 줄인다.

## 4. 분석 → 스펙 작성
- `spec.json` 을 이전 에피소드 형식으로 작성 (assets.video.url 만 먼저 채워도 됨) → 커밋/푸시 → `analyze-speech` 워크플로 dispatch(episode=epNN_slug) → 완료 후 Release `analyze-epNN_slug` 의 `transcript.json`, `speech_segments.txt`, `contact_sheet.jpg` 를 `gh api -H "Accept: application/octet-stream" repos/.../releases/assets/<id>` 로 받는다.
- transcript 의 A/B 두 결과가 일치하는 단어만으로 `dialogue_subtitles` 를 쓴다(**대본 문구 금지, 미인식 구간은 자막 없음**). 시각은 단어 타임스탬프, 대사 사이 빈 구간에 나레이션 `at` 을 배치한다. 나레이션 `duration` 은 get_task 의 durationSeconds.
- `subtitle_chunks` 로 나레이션 자막을 어절 단위로 쪼갠다.
- 효과음 `at` 은 반전 발화 시작 시각.

## 5. 합성
- 커밋/푸시 후 `compose` 워크플로 dispatch → 완료되면 Release `epNN_slug` 의 mp4·preview 를 받아 **프레임을 직접 보고** 제목/자막 위치·겹침·오타를 점검. 문제가 있으면 spec 수정 후 재실행.
- 공개 URL: `https://github.com/jjkyuseop-bit/phonkok-reels/releases/download/epNN_slug/<output>.mp4`

## 5.5 검수 (필수 — 통과 전에는 게시 금지)
compose 워크플로는 Release 에 `qa/report.txt`, `qa/grid.jpg`(0.5초 간격 전체 프레임), `qa/sub_boundaries.jpg`(모든 자막 시작·끝 프레임)를 함께 올린다. 세 가지를 **반드시 직접 읽고 본다.**
1. **규칙 점검**: report.txt 의 "점검 결과"에 항목이 있으면 전부 해소(제목 단어, 길이, 나레이션-대사 겹침, 자막 조각 길이). FORMAT.md 를 한 번 더 열어 레이아웃·색·폰트·나레이션 규칙과 대조.
2. **자막 싱크**: sub_boundaries.jpg 에서 각 대사 자막이 그 인물이 입을 여는 프레임에 뜨고 닫을 때 사라지는지, 나레이션 조각이 발화와 맞는지 확인. 어긋나면 spec 의 start/end·at 을 Whisper 단어 시각 기준으로 수정.
3. **영상 어색함 컷편집**: grid.jpg 를 보고 멈춘 듯한 프레임, 얼굴·손 왜곡, 의미 없이 늘어지는 구간, 대사 없이 입만 움직이는 구간, 장면 전환이 어색한 지점을 찾는다. 있으면 `spec.keep_segments` 에 **원본 시간 기준으로 유지할 구간만** 적어 잘라낸다(예: `[[0,6.4],[7.1,24]]`). 자막·나레이션·효과음 시각은 원본 시간 그대로 두면 compose 가 자동 변환한다. 컷은 대사 중간을 자르지 말고 호흡(침묵) 지점에서 자른다. 템포가 빠른 고퀄리티 바이럴 영상처럼 군더더기를 덜어내되 기승전결은 유지.
4. 수정했으면 커밋·푸시 → compose 재실행 → 다시 5.5 처음부터. **점검 결과 "문제 없음" + 육안 이상 없음** 이 될 때까지 반복(최대 3회, 그래도 안 되면 영상 재생성 판단).

## 6. 게시 (Metricool, 확인 없이)
- `createScheduledPost` 두 번: instagram(REEL, isAiGenerated=true, showReelOnFeed=true, videoCoverMilliseconds=훅 장면) / youtube(short, public, category COMEDY, isAiGeneratedContent=true, 제목 "{훅} {이모지} | 폰콕 #Shorts").
- 게시 시각: 실행일(화) 오전 10:00 Asia/Seoul. 실행이 10시를 넘겼으면 가장 가까운 10분 단위 이후 시각.
- 캡션: FORMAT.md 포맷. 유튜브에는 #Shorts 추가.

## 7. 마무리
- `script.md` 에 최종 제목·캡션·사용 크레딧 기록, `reports/` 갱신, 커밋/푸시.
- 대표에게 알림: 제목, 게시 시각, 공개 URL, 사용 크레딧, 지난 편 성과 요약 5줄 이내.
- 실패 시: 어느 단계에서 왜 멈췄는지와 다음 행동을 알림으로 남기고 종료 (게시는 하지 않음).
