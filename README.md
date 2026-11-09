# Market Sentiment Dashboard — News vs Community

대시보드는 딱 두 종류의 독립적인 심리 판단을 표시합니다.

1. **뉴스 심리 판단**: 뉴스 기사만 분석
2. **커뮤니티 심리 판단**: Reddit, 디시인사이드, 공개 검색 가능한 네이버 카페 게시물만 분석

두 점수는 절대 합산하지 않습니다. 각 종류 안에서 미국 관련/한국 관련 심리를 나눠 보여줍니다.

## 파일
- `index.html`: GitHub Pages 대시보드
- `update.py`: RSS 수집 및 점수 계산
- `data.json`: 최근 분석 데이터
- `.github/workflows/update.yml`: 매일 자동 갱신

## 설치
1. 파일을 GitHub 저장소 루트에 업로드
2. Settings → Pages → Deploy from a branch → `main` / `/(root)`
3. Actions → Update market sentiment → Run workflow
4. GitHub Pages 주소 접속

자동 실행은 매일 한국시간 08:30입니다.

## 점수
0~20 극심한 공포 / 21~40 공포 / 41~60 중립 / 61~80 탐욕 / 81~100 극심한 환희

## 데이터 한계
- 뉴스: Google News RSS 검색 결과
- 커뮤니티: Reddit, 디시인사이드, 네이버 카페 도메인의 공개 검색 색인 결과
- 비공개 카페, 로그인 전용 게시물, 검색엔진에 노출되지 않은 게시글은 수집할 수 없습니다.
- 커뮤니티 수집은 전수조사가 아닙니다. 특히 Google News RSS는 커뮤니티 게시글을 모두 노출하는 API가 아닙니다.
- 현재 감성 점수는 제목·요약의 긍정/부정 키워드 기반 프로토타입입니다. 반어, 문맥, 게시글 영향력, 작성자 중복 등을 정교하게 판별하지 못합니다.
- 투자 판단을 위한 공식 지수나 투자 조언이 아닙니다.

정확도를 높이려면 Reddit 공식 API 인증, 공개적으로 허용된 커뮤니티 데이터 접근 방식, 문맥형 감성 분석 모델을 추가하는 것이 좋습니다. API 키는 HTML에 넣지 말고 GitHub Actions Secrets에 저장하세요.
