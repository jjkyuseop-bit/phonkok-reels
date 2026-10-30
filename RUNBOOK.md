# 폰콕 릴스 주간 자동 제작 런북 (매주 화요일 실행)

이 문서는 예약 작업이 새 세션에서 그대로 따라 하는 절차다. **FORMAT.md 의 규칙은 전부 강제**이며, 사람 확인 없이 끝까지 진행하고 게시한다.

## 0. 준비 (매 실행)
1. `gh api user` 로 GitHub 연결 확인. 저장소 `jjkyuseop-bit/phonkok-reels` 가 세션에 없으면 add_repo(owner=jjkyuseop-bit, repo=phonkok-reels, access=push) 후 `/home/claude/phonkok-reels` 에 clone. 이미 있으면 `git pull`.
2. Runway `whoami` 로 Pro 플랜·크레딧 확인 (영상 모델 목록이 비어 있으면 중단하고 알림).
3. Metricool `getBrandSettings` 로 brand 7556654(phon.kok) 확인.
4. `FORMAT.md` 와 `ep*/script.md` 전부 읽기 (소재 중복 방지).

## 0.5 오늘 이미 예약된 영상이 있으면 생성하지 않는다
- Metricool `getScheduledPosts`(오늘 00:00~23:59 Asia/Seoul)에 검수 완료된 릴스/숏츠가 이미 잡혀 있으면(예: 대표가 미리 검수한 편), **새 영상을 만들지 않는다.** 1단계 성과 기록과 알림만 하고 종료.

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

## 3. 생성 (Runway MCP) — v2: 레퍼런스 고정 + 샷 단위 + 대사 선녹음 (EP03부터 기본)
1. **캐릭터 시트·배경 먼저**: `generate_image`(nano-banana-pro, 16:9)로 등장인물별 시트 1장(정면 클로즈업 + 3/4 전신, 밝은 회색 스튜디오 배경, "photorealistic cinematic still, Korean web-drama look, 35mm film texture") + 빈 세트 1장(와이드, 조명 방향 명시). taskId 를 기록. **브라우저나 뷰어로 반드시 눈으로 확인** 후 진행(얼굴 왜곡·엉뚱한 의상이면 재생성).
2. **대사 선녹음**: 캐릭터마다 다른 한국어 네이티브 보이스(`search_voices`), `generate_speech` eleven_v4 로 한 줄씩. **각 파일 1.8초 이상**이어야 referenceAudio 로 쓸 수 있음 → 짧은 대사는 "아…", "잠깐…" 같은 자연스러운 호흡을 앞에 붙여 녹음. durationSeconds 기록.
3. **샷 생성**: 샷당 4~6초, `generate_video` seedance-2.5 / 720p / 16:9 / generateAudio true / `referenceImages` = [캐릭터 시트들(tag), 배경(tag)] / `referenceAudio` = 그 샷의 대사 1개(durationSeconds 포함). 프롬프트: 공통 헤더(화질·조명·@room·@캐릭터 설명) + 그 샷의 연기 지시 + '"audio 1" (대사)' 를 말한다고 명시 + "lips in sync" + 침묵 구간(대사 전 1~2초) + 인물은 프레임 중앙 + "No music, no on-screen text". 대사 없는 샷은 referenceAudio 없이.
4. 본편 합계 22~24초가 되게 샷 길이를 배분(예: 5+5+6+5+4). 나레이션은 대사 없는 침묵 구간(보통 S1 앞 2초)과 엔드카드에만.
5. `stitch_videos`(cut)로 샷을 순서대로 이어 하나의 taskId/URL 로 만든다. 샷 경계 시각(누적 길이)을 기록 → 대사 자막은 **녹음 텍스트 그대로**, 시각은 analyze-speech 의 Whisper 단어 시각으로 맞춘다(내용은 Whisper 가 아니라 녹음 텍스트가 정답).
6. 나레이션(`generate_speech`), BGM(`generate_music` lyria-3-clip 30s), 효과음(`generate_sound_effect`) 은 기존과 동일.
7. 비용 가이드: 이미지 3장 ≈ 30~50, 샷 5개(24초, 720p) ≈ 700, 음성 ≈ 30 → 편당 ≈ 800~900 크레딧.
8. 잘못 나온 샷은 **그 샷만 재생성**(레퍼런스가 고정돼 있어 교체해도 티 안 남) 후 다시 stitch.

## 4. 분석 → 스펙 작성
- `spec.json` 을 이전 에피소드 형식으로 작성 (assets.video.url 만 먼저 채워도 됨) → 커밋/푸시 → `analyze-speech` 워크플로 dispatch(episode=epNN_slug) → 완료 후 Release `analyze-epNN_slug` 의 `transcript.json`, `speech_segments.txt`, `contact_sheet.jpg` 를 `gh api -H "Accept: application/octet-stream" repos/.../releases/assets/<id>` 로 받는다.
- transcript 의 A/B 두 결과가 일치하는 단어만으로 `dialogue_subtitles` 를 쓴다(**대본 문구 금지, 미인식 구간은 자막 없음**). 시각은 단어 타임스탬프, 대사 사이 빈 구간에 나레이션 `at` 을 배치한다. 나레이션 `duration` 은 get_task 의 durationSeconds.
- `subtitle_chunks` 로 나레이션 자막을 어절 단위로 쪼갠다.
- 효과음 `at` 은 반전 발화 시작 시각.

## 4.5 판정 — 영상이 잘못 나왔으면 여기서 분기
- transcript A/B 에서 핵심 대사(훅·반전·펀치라인)가 미인식·불일치면 FORMAT.md "영상이 잘못 나왔을 때" 절차대로: ①자막 비우기(부수 대사만) → ②해당 샷만 재생성해 `keep_segments`로 교체 → ③전체 재생성 1회 → ④나레이션 모드 폴백. 예산 가드 준수. 어떤 경로를 택했는지 reports/ 에 기록.
- 부분 재생성 방법: generate_video(seedance-2.5, 720p, 16:9, 5~8s, 같은 인물·의상·장소 묘사 + 해당 대사만, 프롬프트 앞부분은 원본과 동일하게) → `stitch_videos` 로 [원본 taskId, 새 클립 taskId] 를 이어 하나의 영상으로 만들고 그 URL 을 spec.assets.video.url 로 → `keep_segments` 를 **재생 순서대로** 적는다. 예: 원본 24초, 새 클립 6초(stitch 결과에서 24~30초), 원본의 15.5~18.4초를 교체 → `[[0,15.5],[24,30],[18.4,24]]`. 자막·나레이션·효과음 시각은 stitch 결과 기준 원본 시간으로 적으면 자동 변환된다. 새 클립의 대사도 analyze-speech 로 다시 받아써서 자막을 만든다.

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
