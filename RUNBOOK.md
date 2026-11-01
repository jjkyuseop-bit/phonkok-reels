# 폰콕 릴스 자동 제작 런북 (매주 화·금 실행)

이 문서는 예약 작업이 새 세션에서 그대로 따라 하는 절차다. **FORMAT.md 의 규칙은 전부 강제**이며, 사람 확인 없이 끝까지 진행하고 게시한다.

## 0. 준비 (매 실행)
1. `gh api user` 로 GitHub 연결 확인. 저장소 `jjkyuseop-bit/phonkok-reels` 가 세션에 없으면 add_repo(owner=jjkyuseop-bit, repo=phonkok-reels, access=push) 후 `/home/claude/phonkok-reels` 에 clone. 이미 있으면 `git pull`.
2. Runway `whoami` 로 Pro 플랜·크레딧 확인 (영상 모델 목록이 비어 있으면 중단하고 알림).
3. Metricool `getBrandSettings` 로 brand 7556654(phon.kok) 확인.
4. `FORMAT.md` 와 `ep*/script.md` 전부 읽기 (소재 중복 방지).

## 0.5 오늘 이미 예약된 영상이 있으면 생성하지 않는다 / 예산 가드
- Runway `whoami` 잔여 크레딧 < 550 이면 생성하지 않고 알림만 하고 종료.
- Metricool `getScheduledPosts`(오늘 00:00~23:59 Asia/Seoul)에 검수 완료된 릴스/숏츠가 이미 잡혀 있으면(예: 대표가 미리 검수한 편), **새 영상을 만들지 않는다.** `draft: true` 이거나 본문이 "[보관"으로 시작하는 항목은 무시한다(이전 포맷 보관본). 1단계 성과 기록과 알림만 하고 종료.

## 1. 지난 편 성과 확인
- Metricool `getAnalyticsDataByMetrics` 로 지난 편(인스타 릴스·유튜브 숏츠) 조회수·도달·좋아요·저장·공유·댓글·평균 시청 시간을 가져온다.
- 결과를 `reports/YYYY-MM-DD.md` 에 기록하고, 다음 편에 반영할 한 줄 교훈을 적는다 (예: 3초 이탈 높음 → 훅 더 세게).
- 데이터가 아직 없으면 "데이터 없음"으로 기록하고 진행.

## 2. 기획 (나레이션 중심 포맷)
- 후보 소재 3개를 먼저 적고 세 기준으로 1개 선택: ① 제목만 보고 멈추는가(핸드폰 무관 보편 어그로) ② 15초까지 폰 냄새가 없는가 ③ 마지막 한 줄로 뒤집히는가
- 제목: FORMAT.md "제목(훅) 원칙". 포인트 단어 `[[ ]]`
- 나레이션 4줄(기·승·전·결) + 엔드카드 1줄. FORMAT.md "나레이션 작법"
- 클립 4개 샷리스트: 각 5초, 장면·인물·동작·카메라. 대사 없음
- 시즌·시사 소재 우선. `ep*/script.md` 와 소재 중복 금지
- 새 폴더 `epNN_<slug>/` 에 `script.md` 작성

## 3. 생성 (Runway MCP)
1. 인물 레퍼런스: `generate_image`(nano-banana-pro, 16:9) 인물별 1장 (전신+얼굴 시트)
2. 나레이션: `search_voices`(language=ko)로 톤에 맞는 보이스 선택 → 줄마다 `generate_speech`(eleven_v4, languageCode=ko). 엔드카드 나레이션도 같은 목소리
3. BGM `generate_music`(lyria-3-clip) / 효과음 `generate_sound_effect`(2~3초, 반전 지점)
4. 클립 4개: `generate_video`(seedance-2.5, 16:9, 720p, duration=5, generateAudio=true, referenceImages=[인물 시트 taskId+tag]). 프롬프트 끝에 "No dialogue, no speech, no readable on-screen text, no captions, no logos, no music."
5. `get_task` 로 4개 모두 프레임 확인. 어색한 클립만 재생성(최대 2회). 금지: referenceAudio, 더빙, 단일 20초 대사형

## 4. 스펙 작성
- `spec.json`: `assets.video.clips = [{task_id, url}, ...]` (순서대로, 필요하면 `in`/`out`으로 클립 안 구간 지정), `narration[].at` = 클립 시작 + 0.6, `duration` = get_task durationSeconds, `subtitle_chunks` 어절 단위, `dialogue_subtitles: []`, `mix.video_audio 0.6`, sfx.at = 3번째 클립 시작
- 예: `ep04_dad/spec.json`
- analyze-speech 는 이 포맷에서 불필요(대사 없음). 클립에 말소리가 섞인 의심이 있으면 돌려서 확인

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
- 게시 시각: 실행일(화 또는 금) 오전 10:00 Asia/Seoul. 실행이 10시를 넘겼으면 가장 가까운 10분 단위 이후 시각.
- 캡션: FORMAT.md 포맷. 유튜브에는 #Shorts 추가.

## 7. 마무리
- `script.md` 에 최종 제목·캡션·사용 크레딧 기록, `reports/` 갱신, 커밋/푸시.
- 대표에게 알림: 제목, 게시 시각, 공개 URL, 사용 크레딧, 지난 편 성과 요약 5줄 이내.
- 실패 시: 어느 단계에서 왜 멈췄는지와 다음 행동을 알림으로 남기고 종료 (게시는 하지 않음).
