# 청양플러스 여행사 Hub v1.1 Beta (2026-10-30)

**전수점검 + 순차 보완 보고서:** `docs/UNFINISHED_WORK_PLAN_2026-10-30.md`  
**추가 QA:** `docs/QA_V2.md` · **기존 DB 이행:** `docs/MIGRATION_V1_TO_V2.md`

이번 판에는 `후속업무/마감일` 모듈(`/admin/tasks`), **직원 계정 중지 및 세션 즉시 무효화**, **Blogger 발행 전 미리보기**, **개인정보 처리 안내 초안** 및 **운영자 승인 수동 보유기간 정리 도구**가 추가됐습니다. 새 환경에서 로컬 테스트 14개가 통과했습니다. **운영 공개/외부 계정·예약/결제 실연동은 완료된 것이 아닙니다.**

**개인정보 보존 주의:** `data/`, `backups/`, `.env`에는 비밀키·개인정보가 들어갈 수 있습니다. 배포 ZIP에는 넣지 않았습니다. 보유기간 확정 및 법정 고지·접근 보안 검토 전 공개 운영을 보류하세요.

---

# 청양플러스 여행사 | 고객 사이트 + 모듈형 운영 허브

**브랜드:** 청양플러스 여행사 / 좋은 여행, 행복한 기억  
**사업:** 국내여행 · 선진지견학 · 나들이 · 워크숍 · 가족여행  
**기술:** Python 3.11+ · FastAPI · Jinja2 · SQLite · Pillow · 순수 HTML/CSS/JS  
**버전:** local beta v1.0.0 / 2026-10-29

## 1. Windows 1차 실행

1. 전체 압축을 풉니다. 바탕화면 또는 `C:\CheongyangPlus` 같은 영문·한글 폴더 모두 사용 가능합니다.
2. PC에 **Python 3.11 이상**을 설치합니다. 설치 시 `Add python.exe to PATH`를 선택합니다.
3. `start_windows.bat` 을 더블클릭합니다. 최초 실행에는 **인터넷 연결 및 pip 패키지 설치**가 필요합니다. 이후 같은 환경의 패키지는 재사용됩니다.
4. 브라우저에서 **http://127.0.0.1:8787/setup** 을 열고 첫 관리자 계정/강력한 비밀번호(12자 이상)를 생성합니다.
5. 이후 **http://127.0.0.1:8787/admin/login** 에 로그인합니다. 공개 고객용 사이트는 **http://127.0.0.1:8787/** 입니다.

실행 후 `Cheongyang Plus Server` 창이 별도로 열립니다. **그 서버 창을 닫으면 프로그램이 종료**됩니다. 설치파일(.exe)이 아닌 **원클릭 실행 배치**입니다. 필요한 Python 패키지는 자동 설치합니다.

### macOS / Linux

```bash
chmod +x start_linux_mac.sh
./start_linux_mac.sh
# localhost:8787/setup
```

### 개발 환경 테스트

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## 2. 운영 화면

| 기능 | 공개 사이트 | 관리자 허브 |
|---|---|---|
| 여행상품 | `/tours`, `/services/...` | `/admin/products` |
| 게시판 | `/board/notice`, `/board/story`, `/board/review` | `/admin/posts` |
| 여행견적 상담 접수 | `/contact` | `/admin/leads` |
| 여행 제안서 | 관리자 전용 (인쇄 / PDF 저장) | `/admin/proposals` |
| 이미지 라이브러리 | `/static/img/*` | `/admin/media` |
| 방문 및 상담 통계 | - | `/admin/analytics` |
| Blogger 연동 | `blogger/theme.xml` 별도 설치 | `/admin/blogger` |
| 모듈 허브 | 상품·게시판·상담 공개 중지 가능 | `/admin/modules` |
| 계정/사업자정보/로그 | 사업자정보 공개 | `/admin/users`, `/admin/settings`, `/admin/audit` |

고객 문의는 **신규 접수 → 연락 완료 → 견적 전달 → 협의 확정 → 완료/종결** 상태로 관리합니다. `협의 확정`은 별도 예약 시스템의 발권/결제 성공을 뜻하지 않습니다.

## 3. 패키지 구성

```text
app/           데이터베이스 · 인증 · 공개/관리자 라우트 · Blogger 서버 연동
static/        반응형 CSS/JS · 브랜드 이미지 (WebP)
templates/     홈페이지 5개 서비스 · 게시판 · 상품 · 관리자 11개 섹션 · 제안서 인쇄
blogger/       Google Blogger 테마 XML 및 설치 안내, 5개 사업 게시물 초안
marketing/     로고·유튜브 채널 배너·썸네일·SNS 규격 이미지
proposals/     6종 오프라인 HTML 여행제안서 (브라우저에서 인쇄→PDF)
docs/          운영가이드 · 개발/DB 설계 · 마케팅 카피 · 검수 보고
scripts/       백업 · 이미지/제안서 재생성 · Blogger HTML 내보내기
tests/         HTTP/DB 통합 자동 테스트
run.py         로컬 서버 실행
start_windows.bat   윈도우 첫 실행
```

## 4. 사업자 확인 정보

제공하신 관광사업등록증과 명함을 바탕으로 고객 사이트에 기재한 정보입니다.

- 브랜드 및 상호: 청양플러스 (청양플러스 여행사)
- 대표: 곽태근
- 국내여행업 관광사업등록번호: 제2025-000001호
- 주소: 충청남도 청양군 운곡면 청신로 583
- 상담: 010-3742-2684 / taegeuni@naver.com

**사업자등록증·관광사업등록증 원본 이미지는 개인정보·등록증 관리 문제로 공개 자산에 넣지 않았습니다.** 대표자 및 사업정보는 실제 운영 전 검토하세요.

## 5. 실행·검증 범위

2026-10-29 로컬 pytest **7개 테스트 묶음 통과**: 공개 라우트, 실제 SQLite 상담 등록 및 상태 변경, 관리자 첫 계정/로그인/로그아웃, CRUD, 비노출, 인쇄, 파일 업로드 및 이미지 서빙, CSV, 관리자 권한, 모듈 중지·복구, 회사 정보 수정, Blogger 미설정 시 실패 기록, 샘플 이미지 파일, Blogger XML 파싱, 상담·제안서 실제 연결, 상담 개인정보 삭제, 업로드 파일 삭제.

**아직 검증하지 않은 외부 기능:** 실제 Google Blogger OAuth 후 Google 서버에 게시물 생성, 실제 항공/숙박·차량 예약, 온라인 카드 결제, 발송 이메일/SMS, 실제 트래픽을 포함한 장기 운영 테스트, 배포된 공인 도메인/HTTPS, Blogger 관리화면의 스킨 적용 결과. 이 기능을 완료로 표시하지 않습니다.

운영 전 **HTTPS, 방화벽/접근제어, 백업, 개인정보 이용·보유기간 문구, 제3자 지도·항공 연동 권한 검토**가 필요합니다. 자세한 내용은 `docs/` 참고.
