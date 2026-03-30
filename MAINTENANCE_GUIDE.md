# Maintenance Guide

이 문서는 최근 대시보드/리포트 기능 확장 이후, 유지보수 비용이 커진 지점을 정리하고 앞으로 어디를 수정해야 하는지 빠르게 판단할 수 있도록 만든 운영 메모입니다.

## 1. 이번 정리의 목적

최근 변경으로 아래 문제가 커졌습니다.

- `jobs.py` 한 파일에 상태 저장, 실행, watchdog, Notion 발행, payload 직렬화가 모두 섞여 있었음
- `render.py` 한 파일에 화면 껍데기, 섹션 렌더러, 포맷 유틸리티가 모두 몰려 있었음
- 시장 리포트/포트폴리오 리포트 분기와 UI 분기가 여러 곳에 흩어지기 쉬운 구조였음

이번 정리의 목표는 다음 두 가지입니다.

1. 파일별 책임을 분리해서 수정 위치를 예측 가능하게 만들기
2. 신규 기능을 넣을 때 기존 흐름을 덜 건드리도록 경계면을 만들기

## 2. 현재 권장 구조

### Dashboard 진입점

- `app.py`
  - HTTP 요청 처리 전용
  - GET/POST 라우팅, redirect, JSON/HTML 응답만 담당
  - 비즈니스 로직을 추가하지 말고 서비스 함수 호출만 유지

### Report Job 계층

- `jobs.py`
  - 호환성용 facade
  - 다른 파일에서는 가능하면 여기서 import해도 되지만, 신규 구현은 아래 세부 모듈을 직접 참고하는 편이 더 명확함

- `job_store.py`
  - `ReportJob`, `ReportJobStore`
  - job 상태, heartbeat, cancel flag, TTL/timeout 상수
  - job 상태 모델이 바뀌면 여기서 먼저 수정

- `job_runner.py`
  - job 실행 엔진
  - 시장/포트폴리오 리포트 실행 분기
  - watchdog
  - Notion 후발행
  - “실행 흐름”이 바뀌면 여기서 수정

- `job_payloads.py`
  - pending/failure/canceled payload 조립
  - job API 응답 직렬화
  - 상태별 프런트 표시 데이터가 바뀌면 여기서 수정

### Dashboard 데이터 계층

- `data.py`
  - holdings 해석
  - 대시보드 payload 조립
  - macro/signals/news/heatmap/view model 생성
  - 화면 데이터 구조가 바뀌면 여기서 수정

- `reporting.py`
  - 시장 리포트/포트폴리오 리포트 파이프라인 정의
  - 어떤 노드를 타는지, fast/full mode가 어떻게 갈리는지 관리
  - 리포트 생성 순서가 바뀌면 여기서 수정

### Dashboard 렌더링 계층

- `render.py`
  - 페이지 전체 HTML shell
  - inline CSS/JS
  - 섹션 조립
  - 페이지 레이아웃/오버레이/스크립트가 바뀌면 여기서 수정

- `render_sections.py`
  - KPI, 뉴스, 매크로 카드, holdings table, sector flow, treemap, portfolio intelligence 섹션 렌더링
  - 개별 위젯/섹션 마크업 변경은 여기서 우선 처리

### Agent 계층

- `agents/nodes/*.py`
  - 실제 리포트 문장 생성 노드
  - 시장/포트폴리오별 리포트 품질이나 논리 수정은 여기서 처리

## 3. 현재 시장/포트폴리오 리포트 흐름

### 시장 리포트

1. `app.py`에서 `flow=market` POST 수신
2. `job_runner.py`가 job 생성 및 실행
3. `reporting.py`의 `build_market_report()` 호출
4. 실행 체인: `macro -> chart -> risk -> alpha -> build_final_report`
5. `data.py`가 dashboard payload 생성
6. 프런트 먼저 노출
7. 완료 후 Notion 발행은 백그라운드 후처리

### 포트폴리오 리포트

1. `app.py`에서 `flow=portfolio` POST 수신
2. `job_runner.py`가 holdings 파싱 후 job 실행
3. `reporting.py`의 `build_portfolio_report()` 호출
4. 실행 체인: `macro -> portfolio -> chart -> risk -> alpha -> build_final_report`
5. `data.py`가 dashboard payload 생성
6. 프런트 먼저 노출
7. 완료 후 Notion 발행은 백그라운드 후처리

## 4. 수정할 때의 원칙

### 원칙 1. 흐름 수정과 화면 수정은 분리

- 리포트 생성 순서/분기 수정: `reporting.py`, `job_runner.py`
- 화면 표시 방식 수정: `render.py`, `render_sections.py`

한 파일에서 둘 다 만지기 시작하면 다시 엉키기 쉽습니다.

### 원칙 2. job 상태 표현은 store 기준으로만 관리

`pending`, `running`, `canceling`, `completed`, `failed`, `canceled` 같은 상태 정의는 `job_store.py`를 기준으로 유지합니다.

프런트 문구만 바꾸고 실제 상태 모델을 따로 만들지 않는 것이 좋습니다.

### 원칙 3. payload는 `data.py` / `job_payloads.py` 두 곳으로 한정

- 일반 대시보드 payload: `data.py`
- job 상태별 payload: `job_payloads.py`

새 화면용 JSON을 만들 때 이 경계를 넘기 시작하면, route와 render 쪽에 데이터 조립 코드가 새어 나옵니다.

### 원칙 4. 리포트 목적 분기는 prompt와 pipeline 양쪽에서 같이 관리

시장 리포트와 포트폴리오 리포트는 이제 명확히 분리돼 있으므로,

- 어떤 노드를 탈지: `reporting.py`
- 어떤 문서를 쓰게 할지: 각 `agents/nodes/*.py`

를 같이 맞춰야 합니다. 둘 중 하나만 바꾸면 다시 내용이 섞입니다.

## 5. 아직 큰 파일과 남은 과제

현재 유지보수상 가장 큰 파일은 여전히 아래입니다.

- `render.py`
  - 전체 페이지 템플릿과 inline CSS/JS가 길다
  - 다음 단계로는 CSS/JS asset 분리 또는 템플릿화 검토 가능

- `risk.py`
  - 지금은 orchestration과 LLM 호출 중심으로 축소됨
  - 세부 로직은 아래 파일로 분리됨
    - `risk_fetchers.py`: FRED/Tavily/yfinance 수집
    - `risk_logic.py`: 군집화, 스코어링, evidence 포맷, 형식 검증
    - `risk_prompts.py`: 프롬프트 상수
  - 다음 단계는 theme/entity 추출까지 별도 `risk_llm.py`로 빼는 것 검토 가능

- `fetchers.py`
  - 지금은 facade 역할만 수행
  - 실제 구현은 아래로 분리됨
    - `llm_client.py`
    - `macro_data_source.py`
    - `news_source.py`
    - `market_signals.py`
  - 외부 데이터 소스 추가 시 `fetchers.py`에 로직을 넣지 말고 하위 모듈을 먼저 늘리는 것이 원칙

## 6. 불필요하거나 주의할 파일

저장소에는 실행 중 생성되는 파일이 섞이기 쉽습니다.

- `__pycache__/`
- `.DS_Store`
- `.pytest_cache/`

`.gitignore`에는 들어가 있지만, 이미 추적 중인 경우에는 별도 정리가 필요합니다. 이들은 런타임에는 필요 없고, 코드 리뷰도 방해하므로 주기적으로 제거하는 편이 좋습니다.

## 7. 신규 기능 추가 시 추천 체크리스트

1. 이 기능이 “리포트 생성 흐름” 변화인지, “화면 표시” 변화인지 먼저 구분
2. job 상태가 늘어나면 `job_store.py`와 `job_payloads.py`를 같이 수정
3. 시장/포트폴리오 둘 중 하나만 바뀌는 기능이면 `reporting.py` 분기부터 확인
4. 화면 컴포넌트 추가는 `render_sections.py`에 우선 넣고 `render.py`에서 조립
5. 외부 API 호출이 늘어나면 timeout/cancel/heartbeat 영향까지 같이 점검

## 8. 이번 리팩터링 요약

- `jobs.py` 단일 파일 구조를 `job_store.py`, `job_runner.py`, `job_payloads.py`로 분리
- `render.py`에서 섹션 렌더러를 `render_sections.py`로 분리
- `risk.py`를 orchestration 중심으로 줄이고 `risk_fetchers.py`, `risk_logic.py`, `risk_prompts.py`로 분리
- `fetchers.py`를 facade로 줄이고 `llm_client.py`, `macro_data_source.py`, `news_source.py`, `market_signals.py`로 분리
- 기존 import 경로 호환성을 위해 `jobs.py`는 facade로 유지

즉, 앞으로는 “상태”, “실행”, “표시 데이터”, “화면 섹션”을 서로 다른 파일 단위로 관리하는 구조를 기본으로 삼으면 됩니다.
