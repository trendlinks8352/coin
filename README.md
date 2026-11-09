# NASDAQ × Semiconductor Sentiment Radar

첨부해주신 코인 감성 레이더의 UI 아이디어(다크 테마, 소스별 데이터, 게시물 리스트, 감성 게이지, 기간별 추이, 키워드)를 참고하되, 대상은 나스닥과 반도체로 제한한 개선 버전입니다.

## 분석 결과는 4개이며, 두 범주를 절대 섞지 않습니다
- 미국 뉴스: 나스닥/미국 반도체 뉴스만
- 한국 뉴스: 나스닥/반도체 관련 한국어 뉴스만
- 미국 커뮤니티: Reddit 등 미국 관련 게시글 + 공개 검색 색인된 커뮤니티 게시글
- 한국 커뮤니티: 디시인사이드/네이버 카페/Reddit의 한국 반도체 관련 공개 게시글

뉴스와 커뮤니티는 별도 계산합니다. 미국/한국도 별도입니다.

## 데이터 수집 방식
### 뉴스
Google News RSS 다중 쿼리로 Nasdaq Composite/100, SOX, Nvidia, AMD, Broadcom, Micron, TSMC, ASML, Intel, HBM/DRAM/NAND와 한국 반도체 기업/산업 뉴스를 각각 검색하고, 제목·요약 중복 제거 후 전날(KST 00:00~24:00) 기사만 남깁니다.

### 커뮤니티
- Reddit: Google News RSS에서 `site:reddit.com` 검색으로 공개 색인된 게시글만 수집합니다. Reddit API/OAuth, 앱 등록, GitHub Secrets 설정은 필요하지 않습니다.
- DCInside / Naver Cafe: Google News RSS에 공개 색인된 `dcinside.com`, `gall.dcinside.com`, `cafe.naver.com` 게시글만 수집합니다. 비공개 카페, 로그인 전용 게시글, 검색엔진에 색인되지 않은 게시물은 가져올 수 없습니다.
- Reddit도 동일하게 Google 검색에 노출된 공개 게시글만 수집합니다. 따라서 Reddit 전체 게시글을 빠짐없이 가져오는 방식은 아니며, Google 색인 범위에 따라 누락될 수 있습니다. 별도 API 인증은 사용하지 않습니다.

## 점수 계산
각 기사/게시글을 긍정(+1), 중립(0), 부정(-1)으로 분류합니다.
`점수 = 100 × (긍정 건수 + 중립 건수 × 0.5) / 전체 건수`
- 0~20 극심한 공포
- 21~40 공포
- 41~60 중립
- 61~80 탐욕
- 81~100 극심한 환희

모든 게시물은 동일 가중치입니다. 단순 키워드 사전 기반이므로 문맥, 반어, 풍자, 부정어 범위, 게시글의 중요도를 완벽하게 이해하지 못합니다. `collector.py`의 POS/NEG 사전을 수정해 보완할 수 있습니다.

## 설치 / 배포
1. 저장소 루트에 파일과 `.github` 폴더를 업로드합니다.
2. Settings → Pages → Deploy from a branch → `main` / `/ (root)` 선택
3. Actions → `Update Nasdaq Semiconductor Sentiment` → Run workflow
4. GitHub Actions가 매일 08:35 KST에 전날 데이터를 수집하고 `data.json`, `history.json`을 갱신합니다.

## 중요
- 전날 데이터가 없으면 점수는 `null` / 데이터 부족입니다. 50점으로 위장하지 않습니다.
- history.json은 Actions가 수집한 실제 일별 점수만 저장합니다. 과거 데이터가 없는 기간을 임의 생성하지 않습니다.
- Google News RSS 검색 결과는 공개된 모든 기사를 보장하지 않으며 검색어/색인 범위에 따라 누락될 수 있습니다.
- 이 지수는 투자 판단 참고용 실험 지표이며 공식 공포·탐욕 지수나 투자 조언이 아닙니다.
