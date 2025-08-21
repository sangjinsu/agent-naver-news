"""
네이버 뉴스 에이전트 데이터 모델 스키마

이 모듈은 LangGraph 0.6+ 호환 가능한 데이터 모델들을 정의합니다.
"""

from datetime import datetime
from typing import Annotated, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph.message import AnyMessage


class NewsArticle(BaseModel):
    """
    개별 뉴스 기사 모델
    
    Attributes:
        title: 뉴스 기사 제목
        url: 뉴스 기사 URL
        summary: 기사 요약 (선택적)
        category: 뉴스 카테고리
        scraped_at: 스크래핑된 시간
    """
    title: str = Field(..., description="뉴스 기사 제목")
    url: str = Field(..., description="뉴스 기사 URL")
    summary: Optional[str] = Field(None, description="기사 요약")
    category: str = Field(..., description="뉴스 카테고리")
    scraped_at: datetime = Field(default_factory=datetime.now, description="스크래핑된 시간")

    class Config:
        """Pydantic 설정"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CategoryNews(BaseModel):
    """
    카테고리별 뉴스 컬렉션
    
    Attributes:
        category: 카테고리명
        articles: 해당 카테고리의 뉴스 기사 목록
        summary_markdown: 카테고리별 마크다운 요약
    """
    category: str = Field(..., description="카테고리명")
    articles: List[NewsArticle] = Field(default_factory=list, description="뉴스 기사 목록")
    summary_markdown: str = Field("", description="카테고리별 마크다운 요약")

    @property
    def article_count(self) -> int:
        """카테고리별 기사 수 반환"""
        return len(self.articles)

    def add_article(self, article: NewsArticle) -> None:
        """기사 추가"""
        self.articles.append(article)

    def get_articles_by_keyword(self, keyword: str) -> List[NewsArticle]:
        """키워드로 기사 필터링"""
        return [
            article for article in self.articles 
            if keyword.lower() in article.title.lower()
        ]


class NewsReport(BaseModel):
    """
    최종 뉴스 리포트 모델
    
    Attributes:
        generated_at: 리포트 생성 시간
        categories: 카테고리별 뉴스 목록
        full_markdown: 전체 마크다운 리포트
    """
    generated_at: datetime = Field(default_factory=datetime.now, description="리포트 생성 시간")
    categories: List[CategoryNews] = Field(default_factory=list, description="카테고리별 뉴스")
    full_markdown: str = Field("", description="전체 마크다운 리포트")

    class Config:
        """Pydantic 설정"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @property
    def total_articles(self) -> int:
        """전체 기사 수 반환"""
        return sum(category.article_count for category in self.categories)

    def get_category_by_name(self, name: str) -> Optional[CategoryNews]:
        """카테고리명으로 카테고리 검색"""
        for category in self.categories:
            if category.category == name:
                return category
        return None

    def add_category(self, category: CategoryNews) -> None:
        """카테고리 추가"""
        self.categories.append(category)


class NewsAgentState(TypedDict):
    """
    LangGraph 0.6+용 상태 스키마
    
    이 상태는 LangGraph 워크플로우에서 노드 간 데이터를 전달하는 데 사용됩니다.
    """
    # 입력 데이터
    categories: List[str]  # 처리할 카테고리 목록

    # 처리 단계별 데이터
    raw_news: Annotated[List[Dict], "스크래핑된 원본 뉴스 데이터"]
    summaries: Annotated[List[Dict], "카테고리별 AI 요약 결과"]

    # 출력 데이터
    final_markdown: Annotated[str, "최종 마크다운 리포트"]

    # 메타데이터
    messages: Annotated[List[AnyMessage], "LangGraph 처리 메시지"]
    errors: Annotated[List[str], "에러 메시지 목록"]
    timestamp: Annotated[str, "처리 시작 타임스탬프"]
    
    # 성능 추적
    scraping_duration: Annotated[Optional[float], "스크래핑 소요 시간 (초)"]
    summarization_duration: Annotated[Optional[float], "요약 소요 시간 (초)"]
    total_articles_scraped: Annotated[Optional[int], "총 스크래핑된 기사 수"]


# 카테고리 매핑 상수
NAVER_NEWS_CATEGORIES = {
    "정치": "100",
    "경제": "101", 
    "사회": "102",
    "생활/문화": "103",
    "IT/과학": "105",
    "세계": "104"
}

# 카테고리별 이모지 매핑
CATEGORY_EMOJIS = {
    "정치": "🏛️",
    "경제": "💰",
    "사회": "🏘️", 
    "생활/문화": "🎭",
    "IT/과학": "💻",
    "세계": "🌍"
}

# 기본 설정값
DEFAULT_CATEGORIES = ["정치", "경제", "사회", "생활/문화", "IT/과학", "세계"]

# 네이버 뉴스 기본 URL
NAVER_NEWS_BASE_URL = "https://news.naver.com"


def create_initial_state(categories: Optional[List[str]] = None) -> NewsAgentState:
    """
    초기 NewsAgentState 생성 헬퍼 함수
    
    Args:
        categories: 처리할 카테고리 목록 (기본값: 전체 카테고리)
        
    Returns:
        초기화된 NewsAgentState
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES.copy()
    
    return NewsAgentState(
        categories=categories,
        raw_news=[],
        summaries=[],
        final_markdown="",
        messages=[],
        errors=[],
        timestamp=datetime.now().isoformat(),
        scraping_duration=None,
        summarization_duration=None,
        total_articles_scraped=None
    )


def validate_category(category: str) -> bool:
    """
    카테고리가 지원되는지 확인
    
    Args:
        category: 확인할 카테고리명
        
    Returns:
        지원 여부
    """
    return category in NAVER_NEWS_CATEGORIES


def get_category_url(category: str) -> str:
    """
    카테고리에 해당하는 네이버 뉴스 URL 생성
    
    Args:
        category: 카테고리명
        
    Returns:
        카테고리 URL
        
    Raises:
        ValueError: 지원되지 않는 카테고리인 경우
    """
    if not validate_category(category):
        raise ValueError(f"지원되지 않는 카테고리: {category}")
    
    category_id = NAVER_NEWS_CATEGORIES[category]
    return f"{NAVER_NEWS_BASE_URL}/section/{category_id}"


def get_category_emoji(category: str) -> str:
    """
    카테고리에 해당하는 이모지 반환
    
    Args:
        category: 카테고리명
        
    Returns:
        카테고리 이모지 (없으면 빈 문자열)
    """
    return CATEGORY_EMOJIS.get(category, "")