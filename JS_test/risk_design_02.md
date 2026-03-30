# risk.py 리팩터링 설계안

## 목표
현재의 복잡한 2트랙 구조를 단일 파이프라인으로 단순화하여, 아래 3가지 결과를 안정적으로 생성하는 것을 목표로 합니다.

1. 위험섹터/테마
2. 관련종목
3. 리스크 근거

입력 데이터는 다음 3가지만 사용합니다.

- Tavily 실시간 뉴스
- yfinance 가격 데이터
- FRED 거시경제 지표

핵심 원칙은 **LLM을 판단 엔진이 아니라 설명 엔진으로 두는 것**입니다.

---



---

## 리팩터링 후 목표 아키텍처

```text
[FRED / Tavily / yfinance 수집]
        ↓
[뉴스에서 위험 후보 추출]
        ↓
[후보별 가격/거시 신호 부착]
        ↓
[후보별 위험 점수 계산]
        ↓
[상위 3개 후보 선택]python test_risk_node.py
        ↓
[LLM이 최종 설명 생성]
        ↓
[최종 risk_report 출력]
```

이 구조에서는 군집과 테마를 따로 관리하지 않고, 모두 **RiskCandidate**라는 하나의 개념으로 통합합니다.

---

## 핵심 설계 원칙

### 1. 군집과 테마를 분리하지 않는다
기존에는 군집과 테마가 별도 구조였지만, 리팩터링 후에는 모두 `RiskCandidate`로 통일합니다.

### 2. 뉴스에서 후보를 먼저 만든다
시스템의 출발점은 Tavily 실시간 뉴스입니다. 뉴스에서 반복적으로 나타나는 위험 신호를 기반으로 후보를 만듭니다.

### 3. yfinance와 FRED는 후보 강화 신호로 사용한다
가격 추세와 거시 지표는 후보를 새로 만들기 위한 용도가 아니라, 이미 생성된 후보의 위험도를 강화하거나 약화하는 데 사용합니다.

### 4. LLM은 마지막 단계에서만 사용한다
LLM은 다음 역할만 수행합니다.

- 후보명을 사람이 읽기 쉬운 위험섹터/테마명으로 정리
- 관련 종목 2개 선택
- 리스크 근거 5줄 내외 설명

즉, **후보 추출과 점수 계산은 코드**, **최종 표현은 LLM**이 담당합니다.

---

## 리팩터링 후 데이터 모델

### RiskCandidate

```python
from pydantic import BaseModel
from typing import Any

class RiskCandidate(BaseModel):
    candidate_id: str
    name_hint: str | None = None
    tickers: list[str]
    companies: list[str]
    keywords: list[str]
    event_types: list[str]
    news_evidence: list[str]

    market_signals: dict[str, Any]
    macro_signals: dict[str, Any]

    news_score: float = 0.0
    market_score: float = 0.0
    macro_score: float = 0.0
    risk_score: float = 0.0
```

설명:
- `name_hint`: 내부 임시 이름
- `tickers`: 관련 종목 후보
- `keywords`: 산업/리스크 키워드
- `news_evidence`: 근거가 되는 기사 요약
- `market_signals`: 수익률, 변동성, RSI, MA 이격도
- `macro_signals`: 금리, 10년물, HY 스프레드 관련 상태
- `risk_score`: 최종 통합 점수

---

### RiskResult

```python
class RiskResult(BaseModel):
    rank: int
    theme_name: str
    related_stocks: list[str]
    risk_reasons: list[str]
```

설명:
- 사용자에게 보여줄 최종 결과 모델입니다.
- 내부 계산 구조와 최종 출력 구조를 분리해 유지보수를 쉽게 합니다.

---

## 리팩터링 후 함수 구조

기존처럼 많은 세부 함수를 유지하지 않고, 6개의 핵심 함수로 줄이는 것을 추천합니다.

### 1. `collect_inputs`

```python
def collect_inputs(state: dict) -> dict:
    ...
```

역할:
- FRED 데이터 수집
- Tavily 뉴스 수집
- yfinance 데이터 수집
- 공통 입력 구조 생성

반환 예시:

```python
{
    "macro": {...},
    "articles": [...],
    "market_cache": {...}
}
```

---

### 2. `extract_risk_candidates`

```python
def extract_risk_candidates(articles: list[dict]) -> list[RiskCandidate]:
    ...
```

역할:
- 뉴스 기사에서 티커, 회사명, 산업 키워드, 리스크 키워드, 이벤트 유형 추출
- 유사 기사끼리 묶어 후보 생성
- 기존 Bottom-up 군집화와 Top-down 테마 추출을 하나의 후보 추출 단계로 통합

핵심 규칙 예시:
- 공통 ticker가 있으면 같은 후보로 묶기
- 산업 키워드 겹침이 2개 이상이면 묶기
- 리스크 키워드가 유사하면 묶기

---

### 3. `enrich_candidates`

```python
def enrich_candidates(
    candidates: list[RiskCandidate],
    macro: dict,
    market_cache: dict,
) -> list[RiskCandidate]:
    ...
```

역할:
- 각 후보에 yfinance 가격 신호 부착
- 각 후보에 FRED 거시 신호 부착
- RSI, MA 이격도, 20일 수익률, 3개월 최대 낙폭 등 계산
- 금리 민감도 / 경기 민감도 / 신용 민감도 연결

예시 규칙:
- `refinancing`, `debt`, `leverage`, `real estate` → 금리/스프레드 민감
- `consumer`, `auto`, `industrial`, `demand` → 경기/스프레드 민감
- `speculative`, `unprofitable`, `growth` → 금리 민감

---

### 4. `score_risk_candidates`

```python
def score_risk_candidates(candidates: list[RiskCandidate]) -> list[RiskCandidate]:
    ...
```

역할:
- 각 후보에 대해 뉴스 점수, 시장 점수, 거시 점수를 계산
- 최종 리스크 점수 산출
- 우선순위 정렬 가능 상태로 변환

기본 공식 예시:

```python
risk_score = (
    news_score * 0.40 +
    market_score * 0.35 +
    macro_score * 0.25
)
```

권장 이유:
- 시스템 출발점이 실시간 뉴스이므로 뉴스 비중을 가장 높게 둡니다.
- 시장 가격은 두 번째 검증 신호입니다.
- 거시 지표는 배경 필터로 사용합니다.

---

### 5. `select_top_candidates`

```python
def select_top_candidates(
    candidates: list[RiskCandidate],
    top_k: int = 3,
) -> list[RiskCandidate]:
    ...
```

역할:
- 점수 상위 후보만 선택
- 너무 약한 후보 제거
- 중복 후보 제거

추천 규칙:
- `risk_score >= 40` 이상만 후보 유지
- 비슷한 ticker 묶음이 중복되면 상위 점수 하나만 유지
- 최대 3개만 반환

---

### 6. `generate_risk_report`

```python
def generate_risk_report(candidates: list[RiskCandidate]) -> list[RiskResult]:
    ...
```

역할:
- 상위 후보만 LLM에 전달
- 사용자용 결과 생성
- 반드시 구조화된 JSON으로 응답받고, 마지막에 포맷팅

LLM 입력에는 아래 정보만 넣습니다.
- 후보 이름 힌트
- 관련 ticker
- 핵심 뉴스 근거
- 가격 신호 요약
- 거시 신호 요약
- 최종 점수

LLM에게 요구할 출력:
- 위험섹터/테마명
- 관련종목 2개
- 리스크 근거 5줄

---

## 후보 추출 규칙 상세

### 최소 구현 버전
처음 버전에서는 아래 정도로 충분합니다.

#### 기사에서 추출할 필드
- ticker
- company
- industry_terms
- risk_keywords
- event_type
- summary

#### 후보 병합 규칙
- ticker 교집합이 있으면 병합
- industry_terms 교집합이 2개 이상이면 병합
- risk_keywords가 강하게 겹치면 병합

#### 후보 이름 생성
처음에는 LLM 없이 `name_hint`만 만들어도 됩니다.

예:
- `office_reit_refinancing`
- `legacy_auto_margin_pressure`
- `clean_energy_capital_stress`

최종 사용자 노출 이름은 LLM이 정리합니다.

---

## 점수 체계 상세

### 1. 뉴스 점수

```python
news_score = min(
    100,
    negative_article_count * 12
    + repeated_keyword_bonus
    + severe_event_bonus
)
```

구성 예시:
- 부정 기사 수 많음: 가점
- 같은 위험 키워드 반복: 가점
- `default`, `refinancing`, `guidance cut`, `capital raise` 등 심각 이벤트: 추가 가점

---

### 2. 시장 점수

예시 기준:
- 20일 수익률이 나쁠수록 점수 상승
- 3개월 최대 낙폭이 클수록 점수 상승
- RSI 과열 후 약세 구간이면 가점
- MA 이격도가 과도하면 가점

예시 개념:

```python
market_score = (
    return_20d_penalty
    + drawdown_penalty
    + rsi_penalty
    + ma_divergence_penalty
)
```

---

### 3. 거시 점수

거시 점수는 절대값보다 **후보의 민감도**와 함께 평가해야 합니다.

예:
- 금리 민감 키워드가 있는 후보에서 금리가 높으면 가점
- 경기 민감 키워드가 있는 후보에서 HY 스프레드가 확대되면 가점

예시:

```python
macro_score = rate_headwind + yield_headwind + spread_headwind
```

---

## 추천 출력 포맷

LLM에서 바로 최종 문자열을 만들지 말고, 먼저 JSON을 받는 것이 좋습니다.

### 권장 JSON 형태

```json
[
  {
    "rank": 1,
    "theme_name": "상업용 오피스 부동산",
    "related_stocks": ["BXP", "VNO"],
    "risk_reasons": [
      "고금리 환경이 차환 부담을 키우고 있습니다.",
      "오피스 공실률 관련 부정 뉴스가 반복되고 있습니다.",
      "관련 종목의 최근 수익률이 부진합니다.",
      "신용 스프레드 확대가 부동산 금융 여건에 부담입니다.",
      "뉴스와 시장 신호가 같은 방향으로 약세를 가리킵니다."
    ]
  }
]
```

그 다음 포맷터가 아래처럼 사용자용 텍스트를 만듭니다.

```text
1위
위험섹터/테마: 상업용 오피스 부동산
관련종목: Boston Properties(BXP), Vornado Realty Trust(VNO)
리스크 근거:
- 고금리 환경이 차환 부담을 키우고 있습니다.
- 오피스 공실률 관련 부정 뉴스가 반복되고 있습니다.
- 관련 종목의 최근 수익률이 부진합니다.
- 신용 스프레드 확대가 부동산 금융 여건에 부담입니다.
- 뉴스와 시장 신호가 같은 방향으로 약세를 가리킵니다.
```

---

## 기존 함수와의 매핑

아래는 기존 함수들을 어떻게 정리할지에 대한 권장안입니다.

### 유지 가능
- `_build_macro_context`
- `_fetch_news_articles`
- `_fetch_market_signal`
- `_fetch_market_signal_api`
- `_compute_rsi`
- `_compute_ma_divergence`
- `_compute_rsi_from_list`
- `_compute_ma_divergence_from_list`
- `_generate_risk_text`
- `_build_fallback_result`

### 통합 대상
- `_extract_risk_entities`
- `_attach_market_signals`
- `_cluster_entities`
- `_score_cluster`
- `_format_clusters_evidence`
- `_fetch_theme_news`
- `_extract_themes`
- `_enrich_theme_signals`
- `_is_technically_overheated`
- `_assess_macro_headwind`
- `_check_narrative_damage`
- `_score_themes`
- `_format_theme_evidence`

위 함수들은 아래 3개 단계로 흡수하는 것을 권장합니다.

- `extract_risk_candidates`
- `enrich_candidates`
- `score_risk_candidates`

### 검증 단순화
기존의 포맷 재생성 규칙은 줄이는 것이 좋습니다.

기존:
- 블록 수 검사
- ticker 개수 검사
- ETF 포함 여부 검사
- 근거 줄 수 검사
- 재생성

리팩터링 후:
- JSON schema 검사
- related_stocks 길이 2 이상 검사
- risk_reasons 길이 3~5 이상 검사
- 실패 시 폴백

즉, 문자열 형식 검증보다 **구조화된 결과 검증**으로 바꾸는 것이 핵심입니다.

---

## 최종 `risk_node` 구성 예시

```python
def risk_node(state: dict) -> dict:
    inputs = collect_inputs(state)
    candidates = extract_risk_candidates(inputs["articles"])
    candidates = enrich_candidates(
        candidates,
        macro=inputs["macro"],
        market_cache=inputs["market_cache"],
    )
    candidates = score_risk_candidates(candidates)
    top_candidates = select_top_candidates(candidates, top_k=3)
    results = generate_risk_report(top_candidates)

    return {
        **state,
        "risk_report": format_risk_results(results),
    }
```

이 구조의 장점:
- 전체 흐름이 직선형이라 이해하기 쉽습니다.
- 디버깅 포인트가 명확합니다.
- 후보 단위로 로그를 찍기 쉽습니다.
- 새로운 신호를 붙일 때도 `enrich_candidates`만 수정하면 됩니다.
- 점수 규칙 조정이 `score_risk_candidates` 안에서 끝납니다.

---

## 단계별 구현 우선순위

### 1차 구현
- Tavily 기사 수집
- ticker/keyword/event_type 추출
- 후보 생성
- 20일 수익률 + FRED 간단 연결
- 상위 3개 출력

### 2차 구현
- RSI / MA 이격도 추가
- 3개월 최대 낙폭 추가
- 거시 민감도 규칙 정교화

### 3차 구현
- 후보 병합 규칙 고도화
- 중복 후보 제거 개선
- LLM 출력 품질 향상

즉, 처음부터 모든 규칙을 완성하려고 하지 말고, **후보 추출 → 신호 부착 → 점수화 → 설명 생성**의 기본 파이프라인을 먼저 안정화하는 것이 좋습니다.

---

## 최종 정리

이번 리팩터링의 핵심은 다음 한 문장으로 정리할 수 있습니다.

> Bottom-up 군집화와 Top-down 테마 판정을 별도 트랙으로 유지하지 말고, 뉴스에서 추출한 위험 후보를 중심으로 가격 신호와 거시 신호를 덧붙여 점수화한 뒤, 상위 후보만 LLM이 설명하는 단일 파이프라인 구조로 단순화하는 것이 가장 유지보수성과 안정성이 높습니다.
