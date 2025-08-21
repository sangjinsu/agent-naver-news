# 📰 네이버 뉴스 헤드라인 요약 에이전트

> LangGraph 0.6+ 기반 AI 뉴스 수집 및 요약 시스템

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-0.6+-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 프로젝트 개요

네이버 뉴스의 주요 카테고리에서 헤드라인 뉴스를 자동으로 수집하고, OpenAI GPT 모델을 활용하여 한국어로 요약하는 지능형 뉴스 에이전트입니다.

### ✨ 주요 기능

- 🔄 **실시간 뉴스 수집**: 네이버 뉴스의 최신 헤드라인 자동 크롤링
- 🤖 **AI 기반 요약**: OpenAI GPT 모델을 활용한 한국어 뉴스 요약
- 📊 **다양한 출력 형식**: Rich 터미널 출력 + 마크다운 파일 저장
- ⚡ **고성능 병렬 처리**: 비동기 처리로 빠른 수집 및 요약
- 🔧 **완전 자동화**: LangGraph 워크플로우 기반 자동화 시스템
- 📈 **성능 모니터링**: 실시간 통계 및 성능 지표 제공

### 📂 지원 카테고리

| 카테고리 | 이모지 | 설명 |
|---------|--------|------|
| 정치 | 🏛️ | 국회, 행정, 국방, 외교 등 정치 분야 |
| 경제 | 💰 | 금융, 산업, 기업 등 경제 분야 |
| 사회 | 🏢 | 사회 이슈, 사건사고, 교육 등 |
| 생활/문화 | 🎨 | 생활정보, 문화, 예술, 스포츠 등 |
| IT/과학 | 💻 | 기술, 과학, 디지털 트렌드 등 |
| 세계 | 🌍 | 해외 뉴스, 국제 정세 등 |

## 🛠 기술 스택

### 핵심 기술

- **Language**: Python 3.12+
- **Package Manager**: uv (ultrafast Python package installer)
- **AI Framework**: LangGraph 0.6+ (State Machine based AI workflows)
- **LLM**: OpenAI GPT-4o-mini / GPT-4o
- **Web Scraping**: BeautifulSoup4 + httpx (async HTTP client)
- **Terminal UI**: Rich (beautiful terminal output)
- **Testing**: pytest + pytest-asyncio

### 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Scraper Node  │ -> │ Summarizer Node │ -> │ Formatter Node  │
│                 │    │                 │    │                 │
│ • 네이버 뉴스    │    │ • OpenAI API    │    │ • Rich 출력     │
│ • BeautifulSoup │    │ • GPT-4o-mini   │    │ • 마크다운 저장  │
│ • 병렬 처리     │    │ • 한국어 특화   │    │ • 통계 생성     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 설치 및 사용법

### 1. 시스템 요구사항

- **Python**: 3.12 이상
- **메모리**: 최소 512MB (권장 1GB)
- **디스크 공간**: 최소 100MB
- **네트워크**: 인터넷 연결 필요

### 2. 프로젝트 복제

```bash
git clone https://github.com/your-username/agent-naver-news.git
cd agent-naver-news
```

### 3. 의존성 설치

#### uv 설치 (권장)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 패키지 설치
```bash
uv sync
```

### 4. 환경 설정

#### OpenAI API 키 설정
```bash
# .env 파일 생성
echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
echo "OPENAI_MODEL=gpt-4o-mini" >> .env
```

#### 설정 파일 예시 (.env)
```env
# OpenAI API 설정
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_TOKENS=1000

# 스크래핑 설정
REQUEST_DELAY=1.0
MAX_ARTICLES_PER_CATEGORY=15
TIMEOUT=30.0

# 출력 설정
OUTPUT_DIR=./output/reports
LOG_LEVEL=INFO
```

### 5. 실행

#### 기본 실행 (모든 카테고리)
```bash
uv run python -m src.main
```

#### 특정 카테고리만 실행
```bash
# 정치 뉴스만
uv run python -m src.main --categories 정치

# 복수 카테고리
uv run python -m src.main --categories 정치 경제 IT/과학
```

#### 디버그 모드
```bash
uv run python -m src.main --debug
```

#### 도움말
```bash
uv run python -m src.main --help
```

## 📊 성능 지표

### 처리 성능

| 항목 | 목표 | 실제 성능 |
|------|------|-----------|
| 뉴스 수집 속도 | < 2초/카테고리 | ~1.3초/카테고리 |
| AI 요약 속도 | < 15초/카테고리 | ~10초/카테고리 |
| 전체 처리 시간 | < 30초 (6개 카테고리) | ~12초 (1개 카테고리) |
| 메모리 사용량 | < 500MB | ~200MB |
| 성공률 | > 95% | 100% |

### 출력 예시

```
📰 네이버 뉴스 헤드라인 요약 에이전트
LangGraph 0.6+ 기반 AI 뉴스 수집 및 요약 시스템

          📊 카테고리별 요약 결과           
╭──────────┬─────────┬─────────┬───────────╮
│ 카테고리 │  상태   │ 기사 수 │ 요약 길이 │
├──────────┼─────────┼─────────┼───────────┤
│ 🏛️ 정치   │ ✅ 성공 │      15 │   1,024자 │
╰──────────┴─────────┴─────────┴───────────╯

  처리 통계
📰 수집 기사: 15개
⏱️ 총 소요 시간: 11.55초
🔄 스크래핑: 1.26초
🤖 AI 요약: 10.30초
📈 성능: 1.3기사/초
```

## 💰 비용 예상

### OpenAI API 사용료

| 모델 | 1회 실행 | 일일 실행 (1회) | 월간 비용 (30일) |
|------|----------|----------------|------------------|
| **gpt-4o-mini** | ~$0.02 | ~$0.02 | ~$0.60 |
| **gpt-4o** | ~$0.30 | ~$0.30 | ~$9.00 |

> 💡 **권장**: 일반적인 용도로는 `gpt-4o-mini`가 충분히 좋은 품질의 요약을 제공합니다.

## 🧪 테스트

### 전체 테스트 실행
```bash
uv run pytest
```

### 모듈별 테스트
```bash
# 스크래핑 모듈 테스트
uv run pytest tests/test_scraper.py -v

# 요약 모듈 테스트
uv run pytest tests/test_summarizer.py -v

# 설정 모듈 테스트
uv run pytest tests/test_config.py -v
```

### 커버리지 테스트
```bash
uv run pytest --cov=src --cov-report=html
```

### 통합 테스트
```bash
# 실제 뉴스 데이터로 통합 테스트
uv run python -m src.main --categories 정치 --debug
```

## 🏗 프로젝트 구조

```
agent-naver-news/
├── README.md                 # 프로젝트 문서
├── pyproject.toml           # 프로젝트 설정 및 의존성
├── uv.lock                  # 의존성 잠금 파일
├── .env                     # 환경 변수 (생성 필요)
├── src/                     # 소스 코드
│   ├── __init__.py
│   ├── main.py             # CLI 엔트리포인트
│   ├── agents/             # LangGraph 에이전트
│   │   ├── __init__.py
│   │   └── graph.py        # StateGraph 워크플로우
│   ├── models/             # 데이터 모델
│   │   ├── __init__.py
│   │   └── schemas.py      # Pydantic 스키마
│   ├── nodes/              # 워크플로우 노드
│   │   ├── __init__.py
│   │   ├── scraper.py      # 뉴스 스크래핑
│   │   └── summarizer.py   # AI 요약
│   └── utils/              # 유틸리티
│       ├── __init__.py
│       ├── config.py       # 설정 관리
│       └── formatter.py    # 출력 포맷팅
├── tests/                   # 테스트 코드
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_summarizer.py
│   └── test_config.py
└── output/                  # 출력 파일
    └── reports/            # 생성된 마크다운 리포트
```

## ⚙️ 고급 설정

### 성능 튜닝

#### 동시 요청 수 조정
```env
# 스크래핑 동시 요청 수 (기본: 3)
CONCURRENT_REQUESTS=5

# OpenAI API 동시 요청 수 (기본: 2)  
OPENAI_CONCURRENT_REQUESTS=3
```

#### 타임아웃 설정
```env
# HTTP 요청 타임아웃 (초)
TIMEOUT=60.0

# OpenAI API 타임아웃 (초)
OPENAI_TIMEOUT=120.0
```

#### 재시도 설정
```env
# 스크래핑 최대 재시도 횟수
MAX_RETRIES=3

# OpenAI API 최대 재시도 횟수
OPENAI_MAX_RETRIES=3
```

### 로깅 설정

```env
# 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# 로그 파일 저장 경로 (선택사항)
LOG_FILE=./logs/news_agent.log
```

## 🔧 개발자 가이드

### 개발 환경 설정

```bash
# 개발 의존성 설치
uv sync --extra dev

# 코드 포맷팅
uv run black src/ tests/
uv run isort src/ tests/

# 타입 체크
uv run mypy src/
```

### 새로운 카테고리 추가

1. `src/models/schemas.py`에서 `CATEGORY_MAPPING` 업데이트
2. `CATEGORY_EMOJIS`에 이모지 추가
3. 테스트 케이스 추가

### 새로운 노드 추가

1. `src/nodes/` 디렉토리에 새 노드 파일 생성
2. `src/agents/graph.py`에서 그래프에 노드 추가
3. 단위 테스트 작성

## 🚨 문제 해결

### 자주 발생하는 문제

#### 1. OpenAI API 키 오류
```
Error: OPENAI_API_KEY가 설정되지 않았습니다
```
**해결**: `.env` 파일에 올바른 API 키 설정

#### 2. 네트워크 타임아웃
```
Error: Request timeout after 30.0 seconds
```
**해결**: `TIMEOUT` 값을 늘리거나 네트워크 상태 확인

#### 3. 메모리 부족
```
Error: MemoryError
```
**해결**: `MAX_ARTICLES_PER_CATEGORY` 값을 줄이거나 메모리 증설

### 디버그 방법

#### 상세 로그 활성화
```bash
LOG_LEVEL=DEBUG uv run python -m src.main --debug
```

#### 단계별 실행
```bash
# 스크래핑만 테스트
uv run python -c "
import asyncio
from src.nodes.scraper import NaverNewsScraper
async def test():
    scraper = NaverNewsScraper()
    result = await scraper.scrape_category('정치')
    print(f'Found {len(result)} articles')
asyncio.run(test())
"
```

## 🤝 기여하기

### 기여 방법

1. 이 저장소를 포크합니다
2. 새로운 기능 브랜치를 생성합니다 (`git checkout -b feature/새기능`)
3. 변경사항을 커밋합니다 (`git commit -am '새 기능 추가'`)
4. 브랜치에 푸시합니다 (`git push origin feature/새기능`)
5. Pull Request를 생성합니다

### 개발 가이드라인

- 코드 스타일: Black + isort 준수
- 테스트: 새로운 기능에는 반드시 테스트 추가
- 문서화: 공개 API에는 docstring 작성
- 커밋 메시지: 명확하고 설명적인 메시지 작성

## 📄 라이선스

이 프로젝트는 [MIT 라이선스](LICENSE) 하에 배포됩니다.

## 🙏 감사의 말

- [LangGraph](https://github.com/langchain-ai/langgraph) - AI 워크플로우 프레임워크
- [OpenAI](https://openai.com) - GPT 모델 API
- [Rich](https://github.com/Textualize/rich) - 아름다운 터미널 출력
- [uv](https://github.com/astral-sh/uv) - 빠른 Python 패키지 관리자

---

📰 **Happy News Summarizing!** 🤖✨
