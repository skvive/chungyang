# Google Blogger 설치·연동 가이드

Blogger는 무료 블로그 CMS이고, 패키지의 FastAPI/SQLite 대시보드와 **동일한 서버는 아닙니다**. 즉 Blogger 스킨만 올리면 관리자 예약 DB나 문의 접수, CSV, 통계가 Blogger 내부에 만들어지는 것은 아닙니다.

1. https://www.blogger.com 에 로그인해 새 블로그를 생성합니다.
2. **테마 → HTML 편집 → 백업 후** `blogger/theme.xml` 내용으로 교체합니다. 업로드 전 테마 백업을 권장합니다. Blogger가 제공하는 테마 버전에 따라 위젯 구조를 조정해야 할 수 있습니다. (XML 문법 검사는 패키지 테스트에 포함)
3. 게시물에 `국내여행`, `선진지견학`, `나들이`, `워크숍`, `가족여행`, `공지사항`, `여행이야기` 라벨을 추가합니다.
4. 배너와 로고는 `static/img` 이미지를 Google Blogger 게시물/이미지에 별도 업로드하고 **공개 URL**을 확보해 삽입합니다. 로컬 서버의 `/static/img/` 는 Blogger에서 사용할 수 없습니다.
5. 관리자 허브 `Blogger 연동` 페이지는 **글 임시저장 전송**만 지원합니다. 진짜 연결은 Google Cloud Console에서 Blogger API를 활성화하고 OAuth 클라이언트 및 사용자 동의를 얻은 뒤 환경변수를 설정합니다.
   - `BLOGGER_BLOG_ID`: 내 블로그의 숫자 ID
   - `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, `BLOGGER_REFRESH_TOKEN`: OAuth 권한 동의 후 획득한 값
   - scope: `https://www.googleapis.com/auth/blogger`
   - 테스트용 단기 토큰: `BLOGGER_ACCESS_TOKEN` (우선 적용)
6. 환경 변수 재시작 후 `관리자 → Blogger 발행 → 임시글 생성`을 눌러 작업 로그의 `draft` 및 원격 ID를 확인합니다. 실제 발행(공개)은 Blogger 관리화면에서 검토 후 시행합니다.
7. 외부문의는 별도 공개 HTTPS 주소에 웹앱을 배포한 다음 블로그 전화 상담 대신 해당 `/contact` 주소로 교체할 수 있습니다.

문서: https://developers.google.com/blogger/docs/3.0/reference/posts/insert


## v1.1 검증 경계

`/admin/blogger/preview/{post_id}`에서 외부 전송 없이 안전한 게시물 HTML을 확인할 수 있습니다. 로컬 모의 테스트는 Google `posts.insert?isDraft=true` 요청 형식을 검증하지만 Google 계정 인증·실제 게시·테마 가져오기 성공을 확인한 것이 아닙니다. Blogger 공식 API: https://developers.google.com/blogger/docs/3.0/reference/posts/insert , 공식 레이아웃 태그: https://support.google.com/blogger/answer/46888?hl=ko .
