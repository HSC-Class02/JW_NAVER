[![🔗 대시보드 바로가기](assets/dashboard-badge.svg)](https://hsc-class02.github.io/JW_NAVER/)

# NAVER 재무 공시 대시보드

**[🔗 대시보드 바로가기](https://hsc-class02.github.io/JW_NAVER/)** · [Open DART](https://opendart.fss.or.kr/) · [NAVER 공시 검색](https://dart.fss.or.kr/)

NAVER(035420)의 사업·반기·1/3분기 보고서를 월 1일 오전 9시(KST)에 조회합니다. 보고서 목록과 정정 공시를 다시 확인하고, 2015년 이후 구조화 재무제표에서 연결 수치를 우선 추출합니다. 결과는 `data/reports/*.json`, 원문 접수목록은 `data/filings.json`, 공개 대시보드 자료는 `docs/data.json`입니다. 2010년 이후 각 기간의 최종 정정 보고서 원문 ZIP은 `data/archive/`에 보관을 시도하고, 제공되지 않은 원문은 `data/archive_status.json`에 기록합니다. 2010–2014년의 숫자는 Open DART 재무제표 API가 제공하지 않으므로 검증 없이 채우지 않습니다. 2013년 네이버·NHN 분할 때문에 분할 전후 실적을 같은 사업 범위로 비교할 수 없습니다.

## 설치와 배포

1. [Open DART](https://opendart.fss.or.kr/)에서 본인의 API 인증키를 발급받습니다. 코드를 열어 키를 입력하거나 커밋하지 마세요.
2. ZIP을 풀고 **압축 해제 폴더에서** `python install_workflow.py`를 한 번 실행합니다. GitHub Actions가 요구하는 `.github/workflows/update-and-deploy.yml`이 생성됩니다. ZIP에는 숨김 파일·폴더가 없습니다.
3. 이 폴더의 내용 전체를 `HSC-Class02/JW_NAVER` 저장소의 기본 브랜치에 업로드합니다. GitHub 웹 업로드에서 숨김 폴더가 보이지 않으면 `git add .github` 후 `git commit`/`git push`를 쓰거나 GitHub 웹 UI에서 `.github/workflows/update-and-deploy.yml` 경로로 새 파일을 만드세요.
4. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 이름 `DART_API_KEY`, 값은 발급받은 40자리 키로 저장합니다.
5. **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 설정합니다. Actions 탭에서 **Update DART data and deploy dashboard → Run workflow**를 1회 실행합니다. 이후 매월 1일 00:00 UTC(한국시간 09:00)에 실행됩니다. GitHub Actions 일정 실행은 부하에 따라 지연될 수 있습니다.
6. 저장소 오른쪽 **About ⚙ → Website**에 `https://hsc-class02.github.io/JW_NAVER/`를 입력하고 저장합니다. 저장소 설정 권한이 필요한 작업입니다. 처음 실행이 성공하면 README 배지의 링크도 열립니다.

로컬 실행: `DART_API_KEY=발급받은_키 python src/dart_pipeline.py`. API 키는 환경변수로만 사용합니다. 초기 과거 원문 다운로드와 재무 수집은 시간이 걸릴 수 있고 원문 ZIP 보관은 저장소 용량을 늘립니다. 원문 파일 보관을 생략하려면 `--skip-document-archives` 옵션을 추가하세요. GitHub의 파일당 업로드 제한을 초과하는 원문이 있으면 수동으로 크기를 확인한 후 저장 정책을 조정해야 합니다.

## 지표

첨부된 **재무제표 및 재무비율 실무 가이드**를 기준으로 매출·매출총이익·영업이익·순이익, 자산·부채·자본·현금·차입금, CFO·CAPEX·FCF를 추출합니다. 매출성장률, 매출총이익률, 영업이익률, 순이익률, 유동비율, 당좌비율, 부채비율, 자기자본비율, 차입금의존도, 연간 ROA·ROE·ROIC·매출채권회수일수(DSO)·재고보유일수(DIO)와 현금전환율을 계산합니다. 분모가 없거나 0 이하인 비율, 원자료가 모호한 항목은 공란 처리합니다. 금액은 원 단위 원본을 저장하고 화면에서 억원으로 보여줍니다. 시장가격이 필요한 PER·PBR·EV/EBITDA, 검증된 상각비가 필요한 EBITDA는 표시하지 않습니다.

분기보고서 손익은 누적과 3개월 금액 필드를 구분합니다. 분기 단독 실적은 각 누적 값의 차이로 계산하며, 4분기는 연간에서 3분기 누적을 뺍니다. 반기는 상반기 누적입니다. 각 표에서 접수 원문을 열어 수치를 대조할 수 있습니다.

## 국내 비교 기업

| 기업 | 종목코드 | NAVER와 겹치는 영역 | 비교 시 주의점 |
|---|---|---|---|
| [카카오](https://www.kakaocorp.com/) | 035720 | 플랫폼·광고·커머스 | 메신저 중심 생태계와 자회사 구성 |
| [NHN](https://www.nhn.com/) | 181710 | 클라우드·결제·커머스 | 게임·결제 사업 비중 및 2013년 분할 |
| [카페24](https://www.cafe24corp.com/) | 042000 | 이커머스 플랫폼 | 커머스 중심의 좁은 사업 범위 |

선정은 사업 영역의 부분적 중첩을 기준으로 하며 동일 사업모델의 완전한 비교군은 아닙니다. 출처: 각 기업 공식 사이트 및 [NAVER 연혁](https://www.navercorp.com/company/history).
