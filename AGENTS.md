# Choice Board for Codex — 작업 계약

## 역할

이 저장소는 Codex Desktop 안에서 단일 선택, 복수 선택, 직접 입력을 한 화면에 표시하고 결과를 현재 대화로 돌려주는 비공식 커뮤니티 스킬을 만든다.

현재 단계는 `working prototype / static validation`이다. 저장소 안에 설치 후보 스킬은 있지만, Codex Desktop 실사용 제출과 공개 배포까지 검증된 제품은 아니다.

## 현재 고정 경계

- 제품 표시명: `Choice Board for Codex`
- 저장소: `MJL-ren/Choice-Board-for-Codex`
- 예정 스킬 이름: `codex-choice-board`
- 첫 지원 표면: Codex Desktop Default mode의 thread-scoped Visualize
- 첫 질문 유형: `single`, `multi`, `text`
- 반환 방식: `window.openai.sendFollowUpMessage({ prompt })`가 만든 현재 대화의 새 사용자 메시지
- 기본 활성화: 명시 호출 전용. 사용자가 직접 바꾼 경우에만 `suggest` 또는 `auto`
- 기본 UX: 모든 선택 질문에 `기타`, 보드 전체에 `선택 전 설명 요청`
- 테마: Codex/Visualize의 host theme와 native control을 따르며 자체 색상 체계를 만들지 않는다.
- 외부 서버, localhost, 터널, MCP, DB와 영구 상태를 사용하지 않는다.
- 질문을 만든 업무 스킬과 범용 보드 renderer의 책임을 분리한다.
- 민감정보, 비밀키, 고객 원문을 보드 입력으로 받지 않는다.

## 지금 하지 않을 것

- 저장소의 스킬을 전역 스킬 폴더에 설치하지 않는다.
- 실제 Visualize 보드를 실행하거나 현재 대화에 제출하지 않는다.
- BSA를 비롯한 외부 프로젝트 파일과 기존 fallback을 수정하지 않는다.
- 원격 저장소를 공개로 전환하거나 commit·push·release하지 않는다.
- Codex CLI, VS Code, Apps SDK 또는 MCP 호환을 이미 지원한다고 표현하지 않는다.

## 소유 구조

```text
skills/codex-choice-board/  설치 가능한 스킬 본체
examples/                   민감정보 없는 공개 예시
tests/                      schema, escaping, rendering과 반환 계약 검증
docs/                       설계·결정·호환성·테스트 기록
```

필요한 파일만 유지하고 생성 HTML, 사용자 답변, 개인 설정을 저장소에 넣지 않는다.

## 구현 원칙

- SKILL.md는 실행에 필요한 절차만 간결하게 유지한다. 상세 schema와 호환성 정보는 `references/`로 분리한다.
- 정적 fragment asset은 화면 동작을 소유하고, 작은 renderer script는 canonical schema 검증과 안전한 data 주입만 담당한다.
- 자유 입력과 label은 HTML 및 follow-up prompt에 삽입하기 전에 data로 escape한다.
- 수신 세션은 marker, schema version, form ID, question ID, answer type과 option value를 다시 검증한다.
- 한 번에 활성 보드 하나, 제출 버튼 하나, 사용자 메시지 한 건을 V0 상한으로 둔다.

## 검증 경계

- 정적 검증과 실제 Codex Desktop end-to-end 검증을 구분한다.
- 정적 검증: schema, 안전한 data 주입, 필수값, 접근성 표식, 중복 제출 guard.
- 실제 검증: 현재 대화로의 단일 follow-up, 실패 복구, Unicode·줄바꿈 보존, host API 존재 여부.
- 실제 화면 검증: 320/736px layout과 Codex 라이트·다크 테마 추종.
- 실제 spike는 민재의 별도 요청 뒤 한 보드·한 제출로 시작한다.
- 성공하지 않은 부분을 완료나 지원으로 표시하지 않는다.

## Git과 공개 경계

- 기존 변경을 덮어쓰거나 정리하지 않는다.
- commit, push, tag, release와 공개 전환은 민재가 명시적으로 요청할 때만 한다.
- 공개 전 README의 비공식 프로젝트 표기, LICENSE, 지원 범위와 실제 검증 결과를 다시 확인한다.
