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

## 2. 에이전트 워크플로우 (LangGraph 기반 병렬 아키텍처)
본 프로젝트는 속도(Latency) 최적화와 리포트 품질 검수를 위해 **다중 에이전트 병렬(Concurrency) 및 피드백 구조**를 채택했습니다.

1. **리서치 그룹 (동시 실행 - Fan-out) 🚀**
   - 아래 4명의 에이전트가 각자의 임무를 비동기 병렬로 동시에 수행하여 전체 실행 시간을 획기적으로 단축합니다.
   - 📊 `Macro Agent` : 거시 경제 데이터 스캔 및 시황 요약
   - 🛑 `Risk Agent` : 잠재적 폭락 위험 섹터 경고
   - 🎯 `Alpha Agent` : 글로벌 자금 이동 기반 상승 주도 섹터 발굴
   - 💼 `Portfolio Agent` : 위 3가지 뷰를 바탕으로 내 계좌 리밸런싱 전략 도출

2. **품질 검수자 (대기 후 취합 - Fan-in) 🕵️‍♂️**
   - ⚖️ `GP (Gatekeeper) Agent`: 4명의 리서치 결과가 모두 모일 때까지 대기한 후 교차 검증을 실시합니다.
   - 만약 논리가 충돌하거나 부실한 결과물이 발견되면, 해당 에이전트에게 반려(Reject)하여 **독자적인 재작성 루프(Feedback Loop)**를 수행하게 합니다.

3. **총괄 및 발행 (Publish) 📝**
   - 📰 `CIO Agent`: GP의 까다로운 검수를 모두 통과한 무결점 데이터 종합본을 넘겨받아, 최종 퍼블리시용 Markdown 리포트를 작성합니다.

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

### 4) 로그 레벨 제어 (선택 사항)
실행 시 시스템 로그의 출력 양을 조절할 수 있습니다.
- **모든 로그 보기 (기본값)**: `python main.py`
- **INFO 로그 숨기기 (중요 알림/경고만 보기)**: `LOG_LEVEL=WARNING python main.py`
- **디버그 모드**: `LOG_LEVEL=DEBUG python main.py` (에이전트 내부 통신 확인용)

## 5. Style 가이드

본 프로젝트는 일관된 코드 품질 관리를 위해 `Ruff` 도구와 `GitHub Pull Request` 병합 프로세스를 사용합니다.
상세한 명명 규칙과 깃 브랜치(Git Branch) 전략은 [STYLE_GUIDE.md](STYLE_GUIDE.md) 문서를 참고하시기 바랍니다.

### 💡 항상 명심해야 할 핵심 명령어 (Commit 직전 수동 정리)
커밋(`git commit`)을 진행하기 전에는 반드시 아래 명령어를 입력하여 코드를 정리해 주세요.
```bash
ruff check --fix .   # 1. 논리/문법적 오류 사전 수술 (추천)
ruff format .        # 2. 코드 스타일(띄어쓰기 등) 예쁘게 포장 (필수)
```

> **(선택 사항) Git Hook 자동화**
> 매번 명령어를 치기 귀찮다면 아래 명령어로 자동 감시 기능을 켤 수 있습니다. (권장하지만 선택 사항입니다.)
> ```bash
> pre-commit install
> ```

---

## 6. 깃허브 협업 프로세스 (Git Merge Workflow)

코드 병합 시 충돌(Conflict)을 최소화하고 안전하게 버전을 관리하기 위해, `main` 브랜치에 직접 푸시(Push)하지 않고 반드시 **개인 브랜치 작업 후 Pull Request(Merge)** 방식을 사용합니다.

### 6.1 터미널 작업 흐름 (로컬 컴퓨터)

```bash
# [1] 최초 프로젝트 폴더 세팅 (최초 1회당)
git clone <repository_address>
cd AlphaInvest

# [2] 작업 시작 전 항상 할 것 (최신 코드 동기화)
git checkout main
git pull
pip install -r requirements.txt

# [3] 내 개인 작업 브랜치 이동
git checkout -b seonho_work   # 처음에 브랜치를 만들 때만 '-b' 옵션 사용
# git checkout seonho_work    # 이미 만들어져 있다면 '-b' 없이 이동만

# [4] 최신 main 내용을 내 브랜치에 한 번 합치기 (작업 도중 타인의 커밋과 충돌을 막기 위해)
git merge main
```

*(...🔥 seonho_work 브랜치에서 신나게 코딩...)*

```bash
# [5] 작업 완료 후 로컬에 작업 내역 저장
# (이때 자동으로 pre-commit이 실행되거나, 수동으로 ruff check --fix . 와 ruff format . 을 실행)
git add .
git commit -m "작업 내용 짧게 요약 (ex. main 파일에 로그인 로직 추가)"

# [6] 로컬 브랜치의 내용을 원격(Remote) 깃허브 서버로 내보내기
git push origin seonho_work
```

### 6.2 깃허브 웹(GitHub) 작업 흐름 (Pull Request)

1. 서버에 Push를 완료한 후 GitHub 저장소 홈페이지에 접속하면, 화면 상단에 초록색 **Compare & pull request** 버튼이 생겨 있습니다.
2. 클릭하여 `seonho_work` ➡️ `main` 방향으로 병합 요청(**PR**, Pull Request) 글을 작성합니다.
3. **코드 리뷰어(Code Reviewer)** 란에 팀원을 지정하여 코드 검토를 요청합니다.
4. 팀원들의 모든 피드백 수용이 끝나면, 관리자 혹은 지정된 리뷰어가 GitHub 화면 하단의 초록색 **Merge pull request** 버튼을 눌러 비로소 `main` 브랜치 코드로 원천 반영합니다.

### 6.3 로컬 복귀

다음 업무를 이어가기 위해 내 컴퓨터의 상태를 초기화합니다.
```bash
# [7] 작업 종료 후 다시 main 브랜치로 복귀
git checkout main

# [8] 깃허브 서버에서 방금 Merge되어 완전해진 최신 코드를 내 컴퓨터로 다운로드
git pull

# (이제 다음 개발 파트를 맡을 때 다시 [3]번 과정부터 반복합니다!)
```

---

## 7. AI 협업 가이드 (AI-Native Development)

우리 팀은 AI(Claude, GPT 등)를 적극 활용하여 개발 속도와 품질을 극대화합니다.
AI가 프로젝트의 맥락을 잃거나 각기 다른 스타일로 코딩하는 것을 방지하기 위해, **명령을 내릴 때 반드시 아래 3가지 문서를 프롬프트의 컨텍스트(Context)로 함께 제공(첨부)**해야 합니다.

1. **`TASKS.md`**: 전체 프로젝트 목표 중 본인의 역할을 명확히 한정 짓기 위함 (시야 제한 및 환각 방지).
2. **`STYLE_GUIDE.md`**: 코딩 포맷 획일화 및 함수 100줄 제한, 선언적(Declarative) 코드 작성을 강제하기 위함.
3. **`agent/state.py` (State 스키마)**: 에이전트 간 주고받는 데이터의 입출력 규격을 통일하여 통합 시 발생하는 에러를 원천 차단하기 위함.

### 📋 [복붙용 프롬프트 템플릿]
본인의 파트 코딩을 AI에게 맡길 때 최초 프롬프트로 아래 양식을 복사해서 사용하세요.

```text
[Role]
너는 우리 알파 투자 퀀트 AI 에이전트 프로젝트의 담당 개발자야.

[Context]
아래 제공된 첨부파일 3개를 꼭 읽고 내 지시를 완벽히 따라줘.
1. TASKS.md: 전체 시스템 중 너의 역할과 목표는 [ 본인 태스크 번호 및 제목, 예: 4번. Risk Alert ] 야. 다른 시스템은 신경 쓰지 말고 지정된 태스크에만 집중해.
2. STYLE_GUIDE.md: 네가 코딩할 때 무조건 지켜야 할 파이썬 코딩 룰이야. (함수 100줄 이하, 선언적 코드 작성, 타입 힌팅 필수)
3. state.py: 우리가 주고받을 LangGraph의 핵심 데이터(State) 인터페이스야. 너의 입력과 출력은 반드시 이 스키마를 준수해야 해. 절대 무단으로 키값을 수정하거나 새로 만들지 마.

[Action]
자, 이제 숙지했으면 TASKS.md에 명시된 내 파트를 구현하기 위한 최적의 파이썬 코드를 작성해 줘.
```

---

## 8. 정량/정성 평가 시스템 (Benchmark)

본 프로젝트는 생성된 리포트의 품질을 객관적으로 측정하기 위해 독립적인 평가 시스템을 갖추고 있습니다. `main.py`와 분리되어 있으며, 전체 파이프라인(Macro -> ... -> CIO)을 실행한 후 최종 결과물을 검증합니다.

### 평가 실행 방법 (How to Evaluate)
```bash
# 전체 파이프라인 구동 및 CIO 리포트 정량/정성 평가 실시
python -m evaluations.run_eval
```

### 주요 평가 항목
- **정량 평가**: 필수 경제 지표 누락 여부, 리포트 섹션 구조(I~IV) 준수 여부, 수치적 논리 일관성.
- **정성 평가**: 스타일 가이드 준수 및 전문가 페르소나 반영도 (LLM-as-a-Judge 활용).
- **결과 저장**: `evaluations/results/` 폴더에 타임스탬프와 함께 JSON 형식으로 저장됩니다.
