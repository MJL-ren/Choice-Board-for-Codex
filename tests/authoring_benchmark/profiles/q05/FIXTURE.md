# Locked 5-question fixture

Copy the exact semantic content below into the assigned authoring format.
Do not rewrite labels, descriptions, placeholders, IDs, option values,
option labels, order, types, or flags.

## Board

- form_id: `authoring-benchmark-free-time-05q`
- locale: `ko`
- mode: fixed guided / one-question-at-a-time (`schema 2`, `stepper`)
- explanation: enabled (current default)
- explanation after completion: enabled (current default)
- Skip: enabled on every question (current guided default)
- Other: enabled on choice questions unless a question says `false`
- Questions are optional unless a question says `required: true`

Do not author derived `flow_digest` or any initial answer state.

## Questions

### 01. `time_window`

- type: `single`
- label: 다음 자유시간은 어느 정도로 생각할까요?
- required: `true`
- allow_skip: `true`
- allow_other: `true`
- options, in order:
  - `thirty_minutes` — 30분 안팎
  - `one_hour` — 1시간 안팎
  - `two_hours` — 1~2시간
  - `half_day` — 반나절

### 02. `desired_effects`

- type: `multi`
- label: 그 시간을 보내고 나서 얻고 싶은 것을 골라 주세요.
- required: `true`
- allow_skip: `true`
- description: 두 개 이상 골라도 괜찮아요.
- allow_other: `true`
- options, in order:
  - `rest` — 푹 쉰 느낌
  - `refresh` — 머리가 환기되는 느낌
  - `achievement` — 작게라도 해낸 느낌
  - `connection` — 누군가와 연결된 느낌
  - `fun` — 그냥 즐거운 시간

### 03. `energy_level`

- type: `single`
- label: 활동의 힘과 몰입 정도는 어느 쪽이 좋나요?
- required: `false`
- allow_skip: `true`
- allow_other: `false`
- options, in order:
  - `very_light` — 거의 힘들이지 않고 가볍게
  - `light` — 조금 움직이거나 집중하는 정도
  - `moderate` — 적당히 몰입하고 움직이기
  - `active` — 에너지를 충분히 쓰기

### 04. `context_note`

- type: `text`
- label: 지금 상황에서 함께 고려할 점이 있나요?
- required: `false`
- allow_skip: `true`
- description: 장소, 날씨, 컨디션처럼 추천에 영향을 주는 조건을 적어도 돼요.
- placeholder: 예: 비가 와서 실내가 좋고, 늦은 시간은 피하고 싶어요

### 05. `setting_preferences`

- type: `multi`
- label: 괜찮은 활동 장소를 여러 개 골라 주세요.
- required: `false`
- allow_skip: `true`
- allow_other: `true`
- options, in order:
  - `home` — 집 안
  - `nearby` — 동네나 가까운 곳
  - `outdoors` — 공원이나 야외
  - `cafe_library` — 카페나 도서관
  - `online` — 온라인 공간
