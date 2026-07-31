# Bridge changelog

## v5.3.1

- periodic NONE이 reliable ACK를 완료하지 않도록 수정
- delayed lower status_seq ACK 처리
- stale snapshot 회귀 방지
- 중복 M / RESET / STOP gate
- explicit REMOTE_DIRECT acceptance
- 포커스 이탈·종료 안전정지
- 최종 보정값 27 / 45 / 55, 50 / 68 / 86 / 104 / 122
- 51 tests
- clean clone test가 app_config.example.h를 기준으로 동작하도록 수정

## archive

과거 v3·v4·초기 v5 문서는 `docs/archive/`에 보관한다.
