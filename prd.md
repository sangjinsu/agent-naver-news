# 네이버 뉴스 헤드라인 요약 에이전트 PRD

## 1. 프로젝트 개요

### 1.1 프로젝트명

Naver News Headlines Summarizer Agent

### 1.2 목적

네이버 뉴스의 주요 카테고리별 헤드라인 뉴스를 자동으로 수집하고 요약하여 사용자에게 제공하는 LangGraph 기반 에이전트 시스템 구축

### 1.3 대상 카테고리

- 정치
- 경제
- 사회
- 생활/문화
- IT/과학
- 세계

## 2. 기술 스택

### 2.1 필수 요구사항

- **Python**: 3.12+
- **패키지 관리자**: uv
- **프레임워크**: LangGraph 0.6+
- **LLM**: OpenAI API (GPT-4o-mini 또는 GPT-4o)

### 2.2 주요 라이브러리

```toml
# pyproject.toml
[project]
name = "naver-news-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langgraph>=0.6.0",
    "langchain-core>=0.3.0",
    "langchain-openai>=0.2.0",
    "beautifulsoup4>=4.12.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "rich>=13.0.0",  # for better markdown display in terminal
]
```

## 3. 시스템 아키텍처 (LangGraph 0.6+)

### 3.1 에이전트 구조

```
┌─────────────────────┐
│   StateGraph        │
│   (LangGraph 0.6)   │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │   START   │
     └─────┬─────┘
           │
     ┌─────▼─────┐
     │  Scraper  │
     │   Node    │
     └─────┬─────┘
           │
     ┌─────▼─────┐
     │ Summarizer│
     │   Node    │
     └─────┬─────┘
           │
     ┌─────▼─────┐
     │ Formatter │
     │   Node    │
     └─────┬─────┘
           │
     ┌─────▼─────┐
     │    END    │
     └───────────┘
```

### 3.2 LangGraph 0.6+ 주요 컴포넌트

#### 3.2.1 State Definition

```python
from typing import Annotated, List, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class NewsAgentState(TypedDict):
    """LangGraph 0.6+ 어노테이션이 포함된 상태"""
    categories: List[str]
    raw_news: Annotated[List[Dict], "스크래핑된 원본 뉴스 데이터"]
    summaries: Annotated[List[Dict], "카테고리별 요약된 뉴스"]
    final_markdown: Annotated[str, "최종 마크다운 출력"]
    errors: Annotated[List[str], "에러 메시지"]
```

#### 3.2.2 Graph Builder (LangGraph 0.6+ 스타일)

```python
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# 상태를 사용한 그래프 초기화
workflow = StateGraph(NewsAgentState)

# 노드 추가
workflow.add_node("scraper", scraper_node)
workflow.add_node("summarizer", summarizer_node)
workflow.add_node("formatter", formatter_node)

# 엣지 추가
workflow.add_edge(START, "scraper")
workflow.add_edge("scraper", "summarizer")
workflow.add_edge("summarizer", "formatter")
workflow.add_edge("formatter", END)

# 상태 영속성을 위한 체크포인터와 함께 컴파일
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

#### 3.2.3 노드 구현 패턴

```python
async def scraper_node(state: NewsAgentState) -> NewsAgentState:
    """LangGraph 0.6+ 패턴을 사용한 스크래퍼 노드"""
    # 구현
    return {"raw_news": scraped_data}

async def summarizer_node(state: NewsAgentState) -> NewsAgentState:
    """OpenAI 통합 요약 노드"""
    # 구현
    return {"summaries": summarized_data}
```

## 4. 데이터 모델 (LangGraph 0.6+ Compatible)

### 4.1 News Article Schema

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Annotated

class NewsArticle(BaseModel):
    """개별 뉴스 기사 모델"""
    title: str
    url: str
    summary: Optional[str] = None
    category: str
    scraped_at: datetime = Field(default_factory=datetime.now)

class CategoryNews(BaseModel):
    """카테고리별 뉴스 컬렉션"""
    category: str
    articles: List[NewsArticle]
    summary_markdown: str = ""

class NewsReport(BaseModel):
    """최종 뉴스 리포트 모델"""
    generated_at: datetime = Field(default_factory=datetime.now)
    categories: List[CategoryNews]
    full_markdown: str
```

### 4.2 LangGraph 0.6+ State

```python
from typing import TypedDict, List, Annotated
from langgraph.graph.message import AnyMessage

class NewsAgentState(TypedDict):
    """LangGraph 0.6+용 상태 스키마"""
    # 입력
    categories: List[str]

    # 처리 단계
    raw_news: Annotated[List[dict], "스크래핑된 원본 뉴스"]
    summaries: Annotated[List[dict], "카테고리별 요약"]

    # 출력
    final_markdown: Annotated[str, "최종 마크다운 리포트"]

    # 메타데이터
    messages: Annotated[List[AnyMessage], "처리 메시지"]
    errors: Annotated[List[str], "에러 추적"]
    timestamp: Annotated[str, "처리 타임스탬프"]
```

## 5. 핵심 기능

### 5.1 뉴스 수집 (Scraping)

- 각 카테고리 페이지 접근
- 헤드라인 섹션 식별 및 파싱
- 반복 실행을 위한 스케줄링 지원

### 5.2 뉴스 요약 (Summarization with OpenAI)

- OpenAI GPT-4o-mini 또는 GPT-4o 사용
- 카테고리별 중요도 기반 뉴스 선별
- 한국어 최적화된 프롬프트 엔지니어링
- Markdown 형식 요약 생성

### 5.3 Markdown 출력 형식

```markdown
# 📰 네이버 뉴스 헤드라인 요약

> 생성 시각: 2024-XX-XX HH:MM:SS

## 🏛️ 정치

### 주요 뉴스

1. **[제목]** - 핵심 내용 요약
2. **[제목]** - 핵심 내용 요약

### 오늘의 포인트

- 주요 이슈 정리

## 💰 경제

### 주요 뉴스

1. **[제목]** - 핵심 내용 요약
2. **[제목]** - 핵심 내용 요약

### 오늘의 포인트

- 시장 동향 및 주요 지표

[이하 카테고리별 동일 형식]
```

### 5.4 결과 저장

- Markdown 파일 저장 (`output/YYYY-MM-DD_news_summary.md`)
- 터미널 출력 (Rich 라이브러리 활용)
- 선택적 GitHub Gist 업로드

## 6. 프로젝트 구조 및 코딩 규칙

### 6.1 프로젝트 구조

```
naver-news-agent/
├── pyproject.toml
├── .env
├── README.md
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   └── graph.py
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── scraper.py
│   │   └── summarizer.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── config.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   ├── test_scraper.py
│   └── test_summarizer.py
└── output/
    └── reports/
```

### 6.2 코딩 규칙

- **주석 언어**: 모든 주석은 한글로 작성
- **Docstring**: 한글로 작성, Google Style 사용
- **변수명**: 영어 사용, snake_case
- **클래스명**: 영어 사용, PascalCase
- **상수**: 영어 사용, UPPER_SNAKE_CASE

### 6.3 주석 작성 예시

```python
# 뉴스 스크래핑을 위한 기본 클래스
class NewsScraper:
    """
    네이버 뉴스 헤드라인을 스크래핑하는 클래스

    Attributes:
        base_url: 네이버 뉴스 기본 URL
        categories: 스크래핑할 카테고리 목록
    """

    def __init__(self):
        # 기본 설정 초기화
        self.base_url = "https://news.naver.com"
        # 카테고리별 URL 매핑
        self.categories = {
            "정치": "/section/100",
            "경제": "/section/101"
        }

    async def scrape_headlines(self, category: str) -> List[NewsArticle]:
        """
        특정 카테고리의 헤드라인 뉴스를 스크래핑

        Args:
            category: 뉴스 카테고리 (예: "정치", "경제")

        Returns:
            NewsArticle 객체 리스트

        Raises:
            ScrapingError: 스크래핑 실패 시
        """
        # 카테고리 URL 생성
        url = f"{self.base_url}{self.categories[category]}"

        # HTTP 요청 전송
        # ...
```

## 7. 구현 단계

### Phase 1: 기본 설정 (Week 1)

- [ ] 프로젝트 초기화 (uv init)
- [ ] 의존성 설치 및 환경 설정
- [ ] 기본 프로젝트 구조 생성

### Phase 2: 크롤러 개발 (Week 1-2)

- [ ] 네이버 뉴스 HTML 구조 분석
- [ ] Scraper Node 구현
- [ ] 카테고리별 테스트

### Phase 3: LangGraph 에이전트 구현 (Week 2-3)

- [ ] Graph 상태 정의
- [ ] Node 연결 및 플로우 구현
- [ ] Orchestrator 로직 개발

### Phase 4: OpenAI 요약 기능 개발 (Week 3)

- [ ] OpenAI API 연동 설정
- [ ] Markdown 생성 프롬프트 엔지니어링
- [ ] Summary Node 구현
- [ ] 비용 최적화 (GPT-4o-mini vs GPT-4o 선택 로직)

### Phase 5: 통합 및 테스트 (Week 4)

- [ ] 전체 파이프라인 통합
- [ ] 단위 테스트 작성
- [ ] 성능 최적화

### Phase 6: 배포 준비 (Week 4)

- [ ] 문서화
- [ ] Docker 컨테이너화 (선택)
- [ ] 스케줄러 설정 (cron/airflow)

## 8. 환경 변수

```env
# .env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini  # 또는 gpt-4o

# Optional
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REQUEST_DELAY=1.0  # seconds between requests
OUTPUT_DIR=./output/reports
```

## 9. 성능 요구사항

- 전체 카테고리 스크래핑: < 30초
- 요약 생성: < 20초
- 메모리 사용량: < 500MB
- API 호출 최적화: 배치 처리 지원

## 10. 보안 고려사항

- API 키 환경 변수 관리
- 웹 스크래핑 rate limiting 준수
- User-Agent 헤더 적절히 설정
- robots.txt 준수

## 11. 확장 가능성

### 향후 개선 사항

- 실시간 알림 기능
- 사용자 맞춤형 카테고리 선택
- 감성 분석 추가
- 트렌드 분석 기능
- 다국어 지원
- 다른 뉴스 소스 통합

## 12. 성공 지표

- 일일 자동 실행 안정성 99%+
- 뉴스 요약 정확도 90%+
- 처리 시간 목표 달성
- 사용자 피드백 반영 개선

## 15. OpenAI API 사용 전략

### 15.1 모델 선택 가이드

| 용도             | 추천 모델     | 이유                          |
| ---------------- | ------------- | ----------------------------- |
| 일일 정기 요약   | gpt-4o-mini   | 비용 효율적, 충분한 성능      |
| 심층 분석 필요시 | gpt-4o        | 높은 정확도, 복잡한 맥락 이해 |
| 테스트/개발      | gpt-3.5-turbo | 최소 비용                     |

### 15.2 프롬프트 템플릿

```python
SUMMARY_PROMPT = """
당신은 한국 뉴스 전문 에디터입니다.
다음 뉴스 목록을 분석하여 Markdown 형식으로 요약해주세요.

카테고리: {category}
뉴스 목록:
{news_list}

요구사항:
1. 가장 중요한 뉴스 3-5개 선별
2. 각 뉴스는 핵심 내용을 2-3문장으로 요약
3. 카테고리별 '오늘의 포인트' 섹션 추가
4. Markdown 형식 사용 (제목은 ###, 굵은 글씨는 **)
5. 이모지를 적절히 활용

출력 형식:
### 주요 뉴스
1. **[뉴스 제목]**
   - 핵심 내용 요약

### 오늘의 포인트
- 전체적인 트렌드나 중요 시사점
"""
```

### 15.3 API 호출 최적화

- 배치 처리: 카테고리별 묶음 요청
- 토큰 제한: max_tokens=1000 per category
- 캐싱: 24시간 내 동일 뉴스 재요약 방지
- Rate Limiting: TPM/RPM 제한 준수

## 16. 예상 비용 산정

### 16.1 일일 처리량 기준

- 카테고리: 6개
- 카테고리당 뉴스: 10-15개
- 입력 토큰: ~2,000 tokens/category
- 출력 토큰: ~500 tokens/category

### 16.2 월간 예상 비용

| 모델        | 일일 비용 | 월간 비용 (30일) |
| ----------- | --------- | ---------------- |
| gpt-4o-mini | ~$0.10    | ~$3.00           |
| gpt-4o      | ~$1.50    | ~$45.00          |

## 18. LangGraph 0.6+ 구현 예제

### 18.1 Graph 초기화 및 실행

```python
# src/agents/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
import asyncio

class NewsAgent:
    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.3
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        # 워크플로우 생성
        workflow = StateGraph(NewsAgentState)

        # 노드 추가
        workflow.add_node("scraper", self.scrape_news)
        workflow.add_node("summarizer", self.summarize_news)
        workflow.add_node("formatter", self.format_markdown)

        # 엣지 정의
        workflow.add_edge(START, "scraper")
        workflow.add_edge("scraper", "summarizer")
        workflow.add_edge("summarizer", "formatter")
        workflow.add_edge("formatter", END)

        # 메모리와 함께 컴파일
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)

    async def scrape_news(self, state: NewsAgentState):
        """스크래퍼 노드 구현"""
        # 스크래핑 로직
        return {"raw_news": scraped_data, "timestamp": datetime.now().isoformat()}

    async def summarize_news(self, state: NewsAgentState):
        """OpenAI를 사용한 요약 노드"""
        summaries = []
        for category_news in state["raw_news"]:
            response = await self.llm.ainvoke(
                SUMMARY_PROMPT.format(
                    category=category_news["category"],
                    news_list=category_news["articles"]
                )
            )
            summaries.append(response.content)
        return {"summaries": summaries}

    async def format_markdown(self, state: NewsAgentState):
        """최종 마크다운 출력 포맷팅"""
        # 마크다운 포맷팅 로직
        return {"final_markdown": formatted_markdown}

    async def run(self):
        """그래프 실행"""
        initial_state = {
            "categories": ["정치", "경제", "사회", "생활/문화", "IT/과학", "세계"],
            "raw_news": [],
            "summaries": [],
            "final_markdown": "",
            "messages": [],
            "errors": [],
            "timestamp": ""
        }

        # 체크포인팅을 위한 thread_id로 실행
        config = {"configurable": {"thread_id": "news_thread_1"}}
        result = await self.graph.ainvoke(initial_state, config)
        return result["final_markdown"]
```

### 18.2 실행 스크립트

```python
# src/main.py
import asyncio
from dotenv import load_dotenv
import os
from agents.graph import NewsAgent
from rich.console import Console
from rich.markdown import Markdown

async def main():
    load_dotenv()

    console = Console()

    # 에이전트 초기화
    agent = NewsAgent(
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    # 에이전트 실행
    console.print("[bold green]뉴스 수집 시작...[/bold green]")
    markdown_result = await agent.run()

    # 결과 표시
    md = Markdown(markdown_result)
    console.print(md)

    # 파일로 저장
    output_dir = os.getenv("OUTPUT_DIR", "./output/reports")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{output_dir}/{datetime.now().strftime('%Y-%m-%d')}_news.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown_result)

    console.print(f"[bold blue]리포트가 {filename}에 저장되었습니다[/bold blue]")

if __name__ == "__main__":
    asyncio.run(main())
```

### 18.3 LangGraph 0.6+ 주요 기능 활용

#### 스트리밍 지원

```python
# 중간 결과 스트리밍
async for chunk in app.astream(initial_state, config):
    print(f"처리 중: {chunk}")
```

#### 상태 영속성

```python
# 프로덕션에서는 SQLite 사용
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("news_agent.db")
app = workflow.compile(checkpointer=checkpointer)
```

#### 조건부 엣지

```python
def should_retry(state: NewsAgentState) -> str:
    # 에러가 있으면 재시도
    if len(state["errors"]) > 0:
        return "scraper"  # 스크래핑 재시도
    return "summarizer"  # 요약으로 진행

workflow.add_conditional_edges(
    "scraper",
    should_retry,
    {
        "scraper": "scraper",
        "summarizer": "summarizer"
    }
)
```

## 19. 참고 자료

- [LangGraph 0.6+ Documentation](https://github.com/langchain-ai/langgraph)
- [LangGraph Examples](https://github.com/langchain-ai/langgraph/tree/main/examples)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Naver News](https://news.naver.com)
