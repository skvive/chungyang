# v1.1 Beta QA 검수 보고 (2026-10-30)

| 구분 | 검사 | 결과 | 확인 방법 |
|---|---|---|---|
| 기존 기능 | 상품·상담·제안서·게시판·이미지·설정·Blogger 실패 처리 | PASS | `tests/test_integration.py` — 7 tests |
| 후속업무 | 추가·유효성·마감일·상태변경·삭제·CSV | PASS | `test_tasks_crud_roles_stats_and_csv` |
| 계정 보안 | 비활성 계정 접속 거부, 암호 변경 후 세션 무효 | PASS | `test_account_disable_and_password_revocation` |
| Blogger | HTML 이스케이프, 임시글 요청 모의, 중지 차단 | PASS (MOCK) | `test_preview_safe_csv_formula_and_blogger_remote_mock` |
| 개인정보 | 수동 보유기간·dry-run·선택 삭제 | PASS (LOCAL) | `test_retention_settings_and_dry_run` |
| DB 마이그레이션 | 기존 상품 보존·계정 컬럼 추가·의도한 빈 상품 유지 | PASS | `test_deleted_seed_not_reborn_and_old_schema_migration` |
| 설정 보안 | 원격 초기설정 차단, 관리자 no-store | PASS | `test_remote_first_setup_denied_and_sensitive_cache` |
| 모듈 상태 | 후속업무·이미지 중지 반영 | PASS | `test_module_disable_blocks_new_tasks_and_media_upload` |
| 기존 화면 | 고객·관리자 PC/모바일 | PASS (OFFLINE) | `docs/visual_results.txt` 4화면 |
| 신규 화면 | 후속업무·설정·Blogger 미리보기·개인정보 PC/모바일 | PASS (OFFLINE) | `docs/v2_visual_results.txt` 8화면 |

**결과:** `python -m pytest -q` ⇒ **14 passed**. 모든 시각 검사는 네트워크를 통한 실제 사이트 탐색이 아닌 **HTTP 응답을 인라인하여 Chromium에서 렌더링한 오프라인 화면 검증**입니다.

**미검증:** Google 계정 OAuth 실제 연결·Blogger 테마 실제 설치/실게시, 온라인 예약/결제/환불, 카카오·SMS·이메일 실발송, 장기 부하, Windows 실기기 원클릭 실행, 공인 서버 HTTPS, 개인정보 정책 법률 검토 및 보안 취약점 전문가 심사.

**변경 이력:** 비밀번호 변경 시 기존 쿠키 무효화, 퇴사자 세션 자동 차단, `tasks` CRUD/통계/CSV, 개인정보 안내·수동 정리, Blogger 임시글 미리보기, 영속 데이터 재시드 보호, CSV 수식 방어, 태스크 입력 디자인 재정렬. 테스트용 DB와 암호키는 최종 ZIP에서 제외합니다.
