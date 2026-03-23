# AlphaInvest 코딩 컨벤션 & 스타일 가이드

본 가이드는 여러 작업자가 투입되더라도 프로젝트 전반에 걸쳐 일관성 있고 깔끔한 코드를 유지하기 위해 작성되었습니다.

## 1. 명명 규칙 (Naming Conventions)
파이썬의 표준 스타일 가이드인 **PEP 8**을 따릅니다.

### 1.1 파일 및 모듈 이름 (Files and Modules)
- **규칙**: `snake_case` (소문자 및 띄어쓰기 대신 밑줄)
- **예시**: `macro_analysis.py`, `data_fetcher.py`
- **이유**: 운영체제 간 대소문자 구문 이슈를 방지하고 파이썬 커뮤니티 표준을 충족합니다.

### 1.2 클래스 이름 (Classes)
- **규칙**: `PascalCase` (모든 단어의 첫 글자를 대문자로 표기)
- **예시**: `MacroAnalyzer`, `UserPortfolio`
- **대상**: 일반 클래스, 사용자 정의 예외(Exception) 처리 클래스 등

### 1.3 함수, 메서드 및 변수 이름 (Functions, Methods, Variables)
- **규칙**: `snake_case` (소문자 및 띄어쓰기 대신 밑줄)
- **예시**:
  - 함수: `def create_report():`
  - 메서드: `def fetch_data(self, ticker: str):`
  - 변수: `active_users`, `current_price`
- **비공개 속성(Private)**: 모듈이나 클래스 내부에서만 사용하는 로직은 언더스코어( `_` )로 시작합니다. 예) `_internal_cache`

### 1.4 상수 이름 (Constants)
- **규칙**: `UPPER_SNAKE_CASE` (모두 대문자 표기 및 밑줄 사용)
- **예시**: `MAX_RETRIES = 5`, `BASE_URL = "https://api.fred.gov/"`
- **위치**: 주로 파일 최상단 또는 `config.py` 등에 모아 정의합니다.

---

## 2. 코드 스타일 (Code Style)

### 2.1 타입 힌팅 (Type Hinting)
LangGraph 등 최근의 파이썬 프레임워크 트렌드를 맞추어 **모드를 서명 및 반환 값에 타입 힌트를 명시**합니다. 이는 코드 자동완성(IntelliSense)과 버그 예방에 큰 도움이 됩니다.
```python
def process_portfolio(user_id: int, portfolio: dict) -> bool:
    ...
```

### 2.2 자동화 도구 활용 (Formatters & Linters)
문서를 읽고 눈으로 확인하는 것보다 시스템을 통해 **자동으로 룰을 강제(Enforce)**하는 것이 팀 프로젝트에서 가장 중요합니다.

우리 프로젝트는 **Ruff (`ruff`)** 단일 도구로 모든 스타일 검사와 포매팅을 완벽하게 통일합니다. (Python 생태계에서 가장 빠르고 강력한 차세대 All-in-One 툴)

**명령어 실행 방법 (수동 작업 시)**:
커밋을 하기 전 항상 아래의 2단계 콤보를 실행하는 것을 권장합니다.
```bash
# 1. 쓸모 없는 코드 제거 및 논리적 오류 수술, import 정렬 (Linter Fix)
ruff check --fix .

# 2. 띄어쓰기, 쌍따옴표 등 스타일 자동 정렬 (Formatter)
ruff format .
```

### 2.3 함수 길이 제한 및 선언적 프로그래밍 (Declarative)
- **함수당 100줄 이하 제한**: 하나의 함수나 메서드가 100줄을 넘긴다면 단일 책임 원칙(SRP) 위배를 의심하고, 더 작은 단위의 논리적 함수로 분리(Refactoring)해야 합니다. 이를 통해 코드 재사용성과 가독성을 높입니다.
- **선언적 코드 작성 (Declarative)**: 장황하게 `for`문과 `if-else`문을 중첩하여 "어떻게(How) 도출할 것인가"를 절차적으로 기술하기보다는, 파이썬의 고차/내장 함수나 프레임워크(Pydantic 등)를 활용해 "무엇(What)을 할 것인가"가 직관적으로 보이도록 작성해야 합니다.
