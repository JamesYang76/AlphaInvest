# AlphaInvest

매일 아침 '내 계좌와 관심사'에 완벽히 맞춘 서술형(Narrative) 주식 리포트를 제공하는 구독형 서비스입니다.

## 0. 개요
기존 로보어드바이저의 한계를 넘어, 전문 애널리스트 수준의 교차 검증된 인사이트와 명확한 행동 지침(Action Plan)을 텍스트 형태로 제공합니다.

### 주요 기능
- **리스크 알림**: 한/미 양국 증시에서 현재 절대 매수하면 안 되는 위험 섹터 및 함정 주식(Value Trap) 사전 경고.
- **내 계좌 맞춤 진단**: 보유 중인 복잡한 ETF의 현 상태 진단 및 홀딩/스위칭 액션 플랜 제시.
- **AI 추천**: 데이터 기반으로 도출된 글로벌 주도 섹터 및 양국 대장주 추천.

## 1. 기술 스택
- **데이터 수집 API**:
  - Macro: `FRED API`
  - US Stocks: `yfinance`
  - KR Stocks: `pykrx`
  - Common: `FinanceDataReader (FDR)`
  - News/Search: `Tavily Search API`
- **AI/LLM 아키텍처**: 
  - `LangGraph` (워크플로우 제어)
  - `OpenAI API (GPT-4o)` (MVP 단계)
- **배포 및 리포트**: 
  - `Notion API` 연동

## 2. 에이전트 워크플로우 (LangGraph)
1. **Macro Analysis (거시 경제 분석)**
2. **Risk Detection (리스크 스캔)**
3. **Portfolio Diagnosis (개인 계좌 진단)**
4. **Alpha Hunter (알파 섹터 발굴)**
5. **Report & Publish (최종 리포트 발행)**

## 3. 실행 계획 
- **1일차**: 팀빌딩, 아키텍처 검토/수립, 개발환경 세팅
- **2일차**: LangGraph 핵심 알고리즘 완성, Notion 연동
- **3일차**: 통합 테스트 및 정량/정성 평가 결과 작성
- **4일차**: 발표 준비

## 4. 설치 및 실행 방법 (How to Execute)

### 1) 가상환경 생성 및 패키지 설치
```bash
# pyenv-virtualenv를 사용한 가상환경 생성 및 활성화 (Python 3.12.0 기준)
pyenv virtualenv 3.12.0 alphainv
pyenv local alphainv
pyenv activate alphainv

# 필수 패키지 설치
pip install -r requirements.txt
```

### 2) 환경 변수 세팅
프로젝트 최상단 `.env.example` 파일을 복사하여 `.env` 파일을 만들고, 발급받은 API 키들을 입력합니다.
```bash
cp .env.example .env
```
> **필요한 API 키 목록**
> - `FRED_API_KEY` : (필수) FRED 거시경제 데이터
> - `TAVILY_API_KEY` : (필수) Tavily Web Search
> - `OPENAI_API_KEY` : (필수) OpenAI LLM
> - `NOTION_API_KEY` : (선택) Notion 페이지 발행

### 3) 에이전트 실행
모든 설정이 완료되면 메인 파일을 실행하여 리포트 생성을 시작합니다.
```bash
python main.py
```
