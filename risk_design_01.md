# 데이터 기반 위험 군집 + 동적 테마 하이브리드 리스크 아키텍처

## 목표
본 문서는 `agents/nodes/risk.py`의 최신 구현을 기준으로, 다음 두 접근을 결합한 하이브리드 구조를 정의한다.

1. **Bottom-up 위험 군집화**: 뉴스 엔티티에서 위험 군집을 추출하고 정량 점수화  
2. **Top-down 테마 판정**: 동적 투자 테마를 감지하고 3-기준 하방 리스크를 판정

최종적으로 LLM은 위 두 증거를 합쳐 **1~3위 위험 섹터/테마와 회피 종목(각 2개)**을 경고한다.

---

## 핵심 설계 원칙

- LLM이 섹터/테마 후보를 임의 발명하지 않도록, **데이터 기반 중간 구조(evidence)**를 먼저 만든다.
- 단일 방식 의존을 피하고, **군집 점수 + 테마 판정**을 함께 사용한다.
- 기술적 과열(RSI/MA), 매크로 역행(FRED), 내러티브 훼손(Tavily)을 결합해 하방 리스크를 평가한다.
- 출력은 반드시 실행 가능한 경고 형태(위험 배경 + 회피 종목)로 정리한다.

---

## 전체 아키텍처

```text
[FRED / Tavily / yfinance 수집]
        ↓
[A. 위험 뉴스 엔티티 추출]
        ↓
[A-1. 티커 기반 시장신호 부착]
        ↓
[A-2. 군집화 + 군집 위험점수(0~100)]
        ↓
[B. 동적 테마 뉴스 감지]
        ↓
[B-1. 테마 추출(ETF/대장주/구조적 동인)]
        ↓
[B-2. 3-기준 판정(WATCH/CAUTION/CRITICAL)]
        ↓
[A + B evidence 병합]
        ↓
[LLM 최종 리스크 경보 생성]
```

---

## 1) 데이터 소스 맵핑

### FRED (Macro Filter)
- `DFF` (연방기금금리)
- `DGS10` (미국채 10년물)
- `BAMLH0A0HYM2` (하이일드 스프레드)

### Tavily (Narrative Sensing)
- 위험 뉴스 수집 쿼리(기존)
- 동적 테마 감지 쿼리(신규)
  - `Stock Market Rising Investment Themes structural change 2026`
  - `Sector Weakness bubble overvaluation risk concerns 2026`
- 내러티브 훼손 재검증 쿼리(테마별)

### yfinance / Yahoo API fallback (Market Quant)
- 5일/20일 수익률
- 20일 변동성(yfinance 경로)
- 3개월 최대 낙폭
- **RSI(14)**
- **5일 이동평균 이격도(%)**

---

## 2) Bottom-up 트랙: 위험 군집 추출

### Step A-1. 뉴스 엔티티 정규화
각 기사에서 아래를 구조화 추출한다.
- `tickers`
- `companies`
- `industry_terms`
- `risk_keywords`
- `event_type`
- `sentiment_score`

### Step A-2. 군집화
규칙 기반 군집화(Union-Find):
- 공통 티커가 있으면 병합
- 산업 키워드 교집합이 2개 이상이면 병합

### Step A-3. 군집 위험 점수(연속값)

```python
risk_score = macro_score * 0.35 + market_score * 0.35 + news_score * 0.30
```

- `news_score`: 부정 감성 + 뉴스 반복도
- `market_score`: 관련 종목 20일 수익률 약세 중심
- `macro_score`: 금리/신용/경기 민감도 키워드와 FRED 연계

---

## 3) Top-down 트랙: 동적 테마 하방 판정

### Step B-1. 테마 추출
LLM이 테마 뉴스에서 아래를 추출한다.
- `theme_name` (ETF 티커명이 아닌 산업/서사 중심 이름)
- `theme_type` (`growth | defensive | cyclical | speculative`)
- `theme_keywords` (4~8개, 구조적 드라이버 중심)
- `representative_etfs` (선택, 0~2개)
- `leader_stocks` (2~3개)
- `structural_driver`
- `sentiment`

### Step B-2. 테마 시장 신호 부착
대장주 신호를 우선으로 RSI/MA 이격도를 부착한다. ETF는 보조 지표로만 사용한다.

### Step B-3. 3-기준 판정
아래 3개 플래그를 평가한다.

1. **기술적 과열**
   - RSI > 75 또는 5MA 이격도 > 10%
2. **매크로 역행**
   - 고성장/투기 테마에서 금리 레벨이 높은 경우(예: 10Y > 4.5, Fed > 5.0)
   - 경기민감 테마에서 HY 스프레드 확장(예: > 4.5)
3. **내러티브 훼손**
   - 테마별 부정 키워드 뉴스가 상위 결과에서 반복 노출

### Step B-4. 의사결정 매트릭스
- 플래그 2개 이상: `CRITICAL`
- 플래그 1개: `CAUTION`
- 플래그 0개: `WATCH`

---

## 4) 하이브리드 통합 규칙

- 군집 evidence와 테마 evidence를 하나의 컨텍스트로 합쳐 최종 LLM에 전달한다.
- `CRITICAL` 테마는 최우선 경고 대상으로 강제한다.
- `WATCH` 테마는 경고보다 참고 수준으로 축약한다.
- 최종 출력 종목은 반드시 evidence에 존재하는 티커에서만 선택한다.
- 관련종목은 개별 종목 기준으로 제시하며 ETF는 제외한다.

---

## 5) 출력 계약 (risk_report)

최종 응답은 아래 형식을 따른다.

1위
1. `위험섹터/테마 : [테마명]`
2. `관련종목 : [종목명(TICKER), 종목명(TICKER)]`
3. `리스크 근거 : [최소 5줄]`

2위
1. `위험섹터/테마 : [테마명]`
2. `관련종목 : [종목명(TICKER), 종목명(TICKER)]`
3. `리스크 근거 : [최소 5줄]`

3위
1. `위험섹터/테마 : [테마명]`
2. `관련종목 : [종목명(TICKER), 종목명(TICKER)]`
3. `리스크 근거 : [최소 5줄]`

추가 제약:
- 1위/2위/3위 블록이 모두 없으면 재생성
- 각 블록 관련종목이 2개 미만이면 재생성
- 관련종목에 ETF가 포함되면 재생성
- 각 블록 리스크 근거가 5줄 미만이면 재생성
- 재생성 후에도 미달 시 폴백 메시지 사용

---

## 6) 예외 처리

### 데이터 부재
- 특정 테마 ETF가 없으면 대장주만으로 판정
- 대장주도 부족하면 해당 테마는 `WATCH`로 보수적 처리

### 신호 상충
- 매크로 우호 vs 내러티브 악화 충돌 시 `Risk First` 원칙으로 `CAUTION` 우선

### API 실패
- Tavily/FRED/yfinance 일부 실패 시 사용 가능한 증거만으로 축소 실행
- LLM 실패 시 폴백 문구 반환

---

## 7) 현재 코드 기준 함수 맵

### 데이터/유틸
- `_build_macro_context`
- `_fetch_news_articles`
- `_fetch_market_signal`
- `_fetch_market_signal_api`

### 기술적 지표
- `_compute_rsi`
- `_compute_ma_divergence`
- `_compute_rsi_from_list`
- `_compute_ma_divergence_from_list`

### Bottom-up 트랙
- `_extract_risk_entities`
- `_attach_market_signals`
- `_cluster_entities`
- `_score_cluster`
- `_format_clusters_evidence`

### Top-down 트랙
- `_fetch_theme_news`
- `_extract_themes`
- `_enrich_theme_signals`
- `_is_technically_overheated`
- `_assess_macro_headwind`
- `_check_narrative_damage`
- `_score_themes`
- `_format_theme_evidence`

### 통합/출력
- `risk_node`
- `_generate_risk_text`
- `_has_enough_tickers`
- `_has_required_risk_format`
- `_build_fallback_result`

---

## 최종 정리

현재 리스크 노드는 다음 원칙으로 동작한다.

> **군집 기반 정량 점수(연속값)와 테마 기반 경보 판정(이산값)을 병합한 뒤, LLM이 근거 기반 리스크 경고를 생성하는 하이브리드 구조**가 기본 운영 모드다.