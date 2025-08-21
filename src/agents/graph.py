"""
LangGraph 0.6+ 기반 뉴스 에이전트 그래프 구현

이 모듈은 네이버 뉴스 수집부터 요약까지의 전체 워크플로우를 
LangGraph StateGraph로 구현합니다.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
# SQLite 체크포인터는 선택적으로 사용
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    SqliteSaver = None

from ..models.schemas import NewsAgentState, create_initial_state, DEFAULT_CATEGORIES
from ..nodes.scraper import scraper_node
from ..nodes.summarizer import summarizer_node


# 로거 설정
logger = logging.getLogger(__name__)


class GraphError(Exception):
    """그래프 실행 관련 예외"""
    pass


def should_retry_scraping(state: NewsAgentState) -> str:
    """
    스크래핑 재시도 여부 결정하는 조건부 함수
    
    Args:
        state: 현재 상태
        
    Returns:
        다음 노드명 ("scraper" 또는 "summarizer")
    """
    # 스크래핑된 기사가 없고 에러가 있으면 재시도
    total_articles = state.get("total_articles_scraped", 0)
    errors = state.get("errors", [])
    
    # 재시도 조건: 기사가 0개이고 에러가 있는 경우
    if total_articles == 0 and errors:
        # 이미 재시도했는지 확인 (무한 루프 방지)
        scraping_retries = state.get("scraping_retries", 0)
        if scraping_retries < 2:  # 최대 2회 재시도
            logger.warning(f"스크래핑 재시도 ({scraping_retries + 1}/2)")
            return "retry_scraper"
    
    return "summarizer"


def should_retry_summarization(state: NewsAgentState) -> str:
    """
    요약 재시도 여부 결정하는 조건부 함수
    
    Args:
        state: 현재 상태
        
    Returns:
        다음 노드명 ("summarizer" 또는 "formatter")
    """
    summaries = state.get("summaries", [])
    
    # 요약이 없거나 모든 요약이 실패한 경우
    if not summaries or all(not s.get("success", False) for s in summaries):
        # 재시도 횟수 확인
        summarization_retries = state.get("summarization_retries", 0)
        if summarization_retries < 1:  # 최대 1회 재시도
            logger.warning(f"요약 재시도 ({summarization_retries + 1}/1)")
            return "retry_summarizer"
    
    return "formatter"


async def retry_scraper_node(state: NewsAgentState) -> NewsAgentState:
    """
    재시도용 스크래퍼 노드
    
    Args:
        state: 현재 상태
        
    Returns:
        업데이트된 상태
    """
    logger.info("스크래핑 재시도 실행")
    
    # 재시도 횟수 증가
    updated_state = state.copy()
    updated_state["scraping_retries"] = state.get("scraping_retries", 0) + 1
    
    # 이전 에러 정리
    updated_state["errors"] = []
    
    # 스크래핑 재실행
    result = await scraper_node(updated_state)
    return result


async def retry_summarizer_node(state: NewsAgentState) -> NewsAgentState:
    """
    재시도용 요약 노드
    
    Args:
        state: 현재 상태
        
    Returns:
        업데이트된 상태
    """
    logger.info("요약 재시도 실행")
    
    # 재시도 횟수 증가
    updated_state = state.copy()
    updated_state["summarization_retries"] = state.get("summarization_retries", 0) + 1
    
    # 요약 재실행
    result = await summarizer_node(updated_state)
    return result


async def formatter_node(state: NewsAgentState) -> NewsAgentState:
    """
    마크다운 포맷터 노드 (임시 구현)
    
    Args:
        state: 현재 상태
        
    Returns:
        업데이트된 상태
    """
    import time
    
    start_time = time.time()
    logger.info("포맷터 노드 실행 시작")
    
    try:
        summaries = state.get("summaries", [])
        
        if not summaries:
            raise ValueError("포맷할 요약이 없습니다")
        
        # 마크다운 헤더 생성
        timestamp = datetime.now()
        markdown_content = f"""# 📰 네이버 뉴스 헤드라인 요약

> 생성 시각: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

"""
        
        # 카테고리별 요약 추가
        for summary_data in summaries:
            category = summary_data.get("category", "알 수 없음")
            summary_text = summary_data.get("summary", "")
            article_count = summary_data.get("article_count", 0)
            success = summary_data.get("success", False)
            
            # 카테고리 섹션 헤더
            from ..models.schemas import get_category_emoji
            emoji = get_category_emoji(category)
            markdown_content += f"## {emoji} {category}\n\n"
            
            if success and summary_text:
                markdown_content += summary_text + "\n\n"
            else:
                markdown_content += f"⚠️ 이 카테고리의 요약을 생성할 수 없었습니다. ({article_count}개 기사)\n\n"
        
        # 통계 정보 추가
        total_articles = state.get("total_articles_scraped", 0)
        scraping_duration = state.get("scraping_duration", 0)
        summarization_duration = state.get("summarization_duration", 0)
        
        markdown_content += f"""---

## 📊 생성 정보

- **총 수집 기사 수**: {total_articles}개
- **스크래핑 소요 시간**: {scraping_duration:.2f}초
- **요약 소요 시간**: {summarization_duration:.2f}초
- **총 처리 시간**: {scraping_duration + summarization_duration:.2f}초

---

*이 리포트는 네이버 뉴스 헤드라인 요약 에이전트에 의해 자동 생성되었습니다.*
"""
        
        duration = time.time() - start_time
        
        # 상태 업데이트
        updated_state = state.copy()
        updated_state["final_markdown"] = markdown_content
        updated_state["formatting_duration"] = duration
        
        logger.info(f"포맷터 노드 완료: {len(markdown_content)}자, {duration:.2f}초")
        return updated_state
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"포맷터 노드 오류: {str(e)}"
        logger.error(error_msg)
        
        updated_state = state.copy()
        updated_state["errors"].append(error_msg)
        updated_state["final_markdown"] = "# 오류 발생\n\n마크다운 생성 중 오류가 발생했습니다."
        updated_state["formatting_duration"] = duration
        
        return updated_state


class NewsAgent:
    """
    네이버 뉴스 헤드라인 요약 에이전트
    
    LangGraph 0.6+를 사용하여 뉴스 수집부터 요약까지의 
    전체 워크플로우를 관리합니다.
    """

    def __init__(
        self,
        checkpointer: Optional[str] = None,
        enable_streaming: bool = True,
        debug: bool = False
    ):
        """
        뉴스 에이전트 초기화
        
        Args:
            checkpointer: 체크포인터 유형 ("memory", "sqlite", None)
            enable_streaming: 스트리밍 활성화 여부
            debug: 디버그 모드 활성화 여부
        """
        self.enable_streaming = enable_streaming
        self.debug = debug
        
        # 체크포인터 설정
        if checkpointer == "sqlite" and SqliteSaver is not None:
            self.checkpointer = SqliteSaver.from_conn_string("news_agent.db")
            logger.info("SQLite 체크포인터 활성화")
        elif checkpointer == "memory":
            self.checkpointer = MemorySaver()
            logger.info("메모리 체크포인터 활성화")
        else:
            self.checkpointer = None
            logger.info("체크포인터 비활성화")
        
        # 그래프 빌드
        self.graph = self._build_graph()
        logger.info("뉴스 에이전트 초기화 완료")

    def _build_graph(self) -> StateGraph:
        """
        LangGraph StateGraph 워크플로우 구성
        
        Returns:
            컴파일된 StateGraph
        """
        logger.info("StateGraph 워크플로우 빌드 시작")
        
        # StateGraph 생성
        workflow = StateGraph(NewsAgentState)
        
        # 노드 추가
        workflow.add_node("scraper", scraper_node)
        workflow.add_node("retry_scraper", retry_scraper_node)
        workflow.add_node("summarizer", summarizer_node)
        workflow.add_node("retry_summarizer", retry_summarizer_node)
        workflow.add_node("formatter", formatter_node)
        
        # 기본 플로우 엣지
        workflow.add_edge(START, "scraper")
        
        # 조건부 엣지 - 스크래핑 후
        workflow.add_conditional_edges(
            "scraper",
            should_retry_scraping,
            {
                "retry_scraper": "retry_scraper",
                "summarizer": "summarizer"
            }
        )
        
        # 재시도 스크래퍼에서 요약으로
        workflow.add_edge("retry_scraper", "summarizer")
        
        # 조건부 엣지 - 요약 후
        workflow.add_conditional_edges(
            "summarizer",
            should_retry_summarization,
            {
                "retry_summarizer": "retry_summarizer",
                "formatter": "formatter"
            }
        )
        
        # 재시도 요약에서 포맷터로
        workflow.add_edge("retry_summarizer", "formatter")
        
        # 포맷터에서 끝으로
        workflow.add_edge("formatter", END)
        
        # 그래프 컴파일
        compiled_graph = workflow.compile(
            checkpointer=self.checkpointer,
            debug=self.debug
        )
        
        logger.info("StateGraph 워크플로우 빌드 완료")
        return compiled_graph

    def _get_thread_config(self, thread_id: Optional[str] = None) -> Dict:
        """
        스레드 설정 생성
        
        Args:
            thread_id: 스레드 ID (없으면 자동 생성)
            
        Returns:
            스레드 설정 딕셔너리
        """
        if thread_id is None:
            thread_id = f"news_thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return {"configurable": {"thread_id": thread_id}}

    async def run(
        self,
        categories: Optional[list] = None,
        thread_id: Optional[str] = None
    ) -> NewsAgentState:
        """
        뉴스 에이전트 실행
        
        Args:
            categories: 처리할 카테고리 목록 (기본값: 전체)
            thread_id: 스레드 ID (체크포인팅용)
            
        Returns:
            최종 실행 결과
            
        Raises:
            GraphError: 그래프 실행 오류
        """
        start_time = datetime.now()
        logger.info(f"뉴스 에이전트 실행 시작: {start_time}")
        
        try:
            # 초기 상태 생성
            initial_state = create_initial_state(categories)
            
            # 스레드 설정
            config = self._get_thread_config(thread_id)
            
            # 그래프 실행
            if self.enable_streaming:
                # 스트리밍 모드
                final_state = None
                async for chunk in self.graph.astream(initial_state, config):
                    if self.debug:
                        logger.debug(f"스트림 청크: {chunk.keys()}")
                    final_state = chunk
                
                if final_state is None:
                    raise GraphError("스트리밍 실행에서 결과를 받지 못했습니다")
                
                # 마지막 청크에서 실제 상태 추출
                result = list(final_state.values())[0]
                
            else:
                # 일반 모드
                result = await self.graph.ainvoke(initial_state, config)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"뉴스 에이전트 실행 완료: {duration:.2f}초")
            
            # 결과 검증
            if not isinstance(result, dict):
                raise GraphError(f"예상하지 못한 결과 타입: {type(result)}")
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            error_msg = f"뉴스 에이전트 실행 실패 ({duration:.2f}초): {str(e)}"
            logger.error(error_msg)
            raise GraphError(error_msg)

    async def get_final_markdown(
        self,
        categories: Optional[list] = None,
        thread_id: Optional[str] = None
    ) -> str:
        """
        마크다운 리포트 생성 (편의 메서드)
        
        Args:
            categories: 처리할 카테고리 목록
            thread_id: 스레드 ID
            
        Returns:
            마크다운 텍스트
        """
        result = await self.run(categories, thread_id)
        return result.get("final_markdown", "# 오류\n\n결과를 생성할 수 없습니다.")

    def get_graph_visualization(self) -> str:
        """
        그래프 구조를 텍스트로 시각화
        
        Returns:
            그래프 구조 텍스트
        """
        return """
네이버 뉴스 에이전트 워크플로우:

START
  │
  ▼
┌─────────────┐
│   scraper   │ ── 스크래핑 실패 시 ──┐
└─────────────┘                    │
  │                                │
  ▼                                ▼
┌─────────────────────┐      ┌─────────────────┐
│ should_retry_       │      │ retry_scraper   │
│ scraping           │      └─────────────────┘
└─────────────────────┘              │
  │                                  │
  ▼                                  │
┌─────────────┐ ◄────────────────────┘
│ summarizer  │ ── 요약 실패 시 ──┐
└─────────────┘                 │
  │                             │
  ▼                             ▼
┌─────────────────────┐   ┌─────────────────────┐
│ should_retry_       │   │ retry_summarizer    │
│ summarization      │   └─────────────────────┘
└─────────────────────┘           │
  │                               │
  ▼                               │
┌─────────────┐ ◄─────────────────┘
│  formatter  │
└─────────────┘
  │
  ▼
END

주요 특징:
- 스크래핑 실패 시 최대 2회 재시도
- 요약 실패 시 최대 1회 재시도
- 각 단계별 상태 영속성 지원
- 중간 결과 스트리밍 가능
"""


# 편의 함수들
async def create_news_agent(
    checkpointer: str = "memory",
    enable_streaming: bool = True,
    debug: bool = False
) -> NewsAgent:
    """
    뉴스 에이전트 생성 편의 함수
    
    Args:
        checkpointer: 체크포인터 유형
        enable_streaming: 스트리밍 활성화
        debug: 디버그 모드
        
    Returns:
        NewsAgent 인스턴스
    """
    return NewsAgent(
        checkpointer=checkpointer,
        enable_streaming=enable_streaming,
        debug=debug
    )


async def generate_news_summary(
    categories: Optional[list] = None,
    thread_id: Optional[str] = None
) -> str:
    """
    뉴스 요약 생성 편의 함수
    
    Args:
        categories: 카테고리 목록
        thread_id: 스레드 ID
        
    Returns:
        마크다운 요약 텍스트
    """
    agent = await create_news_agent()
    return await agent.get_final_markdown(categories, thread_id)