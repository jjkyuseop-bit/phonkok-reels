# 폰콕 릴스 자동 제작 파이프라인

Runway(영상·나레이션·BGM 생성) → GitHub Actions(ffmpeg 합성) → Metricool(인스타 릴스·유튜브 숏츠 예약)

- `FORMAT.md` — 매 에피소드 제작 규칙
- `compose.py` — 합성 스크립트 (본편 + 엔드카드, 3층 자막, 오디오 믹싱)
- `endcard/` — 공통 엔드카드 (6초, #E84855)
- `epNN_*/spec.json` — 에피소드별 에셋 URL·자막·타이밍
- `.github/workflows/compose.yml` — `episode` 입력으로 수동 실행 → Release에 완성본 업로드
