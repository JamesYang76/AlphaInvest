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

## 5. Style 가이드

본 프로젝트는 일관된 코드 품질 관리를 위해 `Ruff` 도구와 `GitHub Pull Request` 병합 프로세스를 사용합니다.
상세한 명명 규칙과 깃 브랜치(Git Branch) 전략은 [STYLE_GUIDE.md](STYLE_GUIDE.md) 문서를 참고하시기 바랍니다.

### 💡 항상 명심해야 할 핵심 명령어 (Commit 직전 수동 정리)
로컬에서 개발 후 커밋(`git commit`)을 진행하기 전에는 가급적 아래 명령어를 입력하여 코드를 정리하는 것을 생활화합니다.
```bash
ruff check --fix .   # 1. 안 쓰는 변수 제거 및 import 위치 등 논리/문법적 오류 사전 수술
ruff format .        # 2. 줄바꿈 여백, 쌍따옴표, 120자 래핑 등 모양새 예쁘게 포장
```
*(단, `pre-commit install`을 통해 Git Hook 설정을 활성화해 두셨다면 커밋 시 위 기능들이 백그라운드에서 자동으로 수행됩니다.)*

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
