"""
스크래핑 모듈 단위 테스트

이 테스트는 네이버 뉴스 스크래핑 기능을 검증합니다.
실제 네트워크 요청 대신 모킹을 사용하여 안정적인 테스트를 제공합니다.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from src.nodes.scraper import (
    NaverNewsScraper,
    scraper_node,
    ScrapingError
)
from src.models.schemas import (
    NewsAgentState,
    NewsArticle,
    create_initial_state,
    validate_category,
    get_category_url
)


class TestNaverNewsScraper:
    """NaverNewsScraper 클래스 테스트"""

    def setup_method(self):
        """각 테스트 메서드 실행 전 설정"""
        self.scraper = NaverNewsScraper(
            request_delay=0.1,  # 테스트 속도 향상
            timeout=5.0,
            max_retries=2,
            max_articles_per_category=5
        )

    def test_scraper_initialization(self):
        """스크래퍼 초기화 테스트"""
        assert self.scraper.request_delay == 0.1
        assert self.scraper.timeout == 5.0
        assert self.scraper.max_retries == 2
        assert self.scraper.max_articles_per_category == 5
        assert "Mozilla" in self.scraper.user_agent

    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """HTTP 요청 성공 테스트"""
        mock_html = """
        <html>
            <body>
                <div class="hdline_article_tit">
                    <a href="/news/001">테스트 뉴스 제목</a>
                </div>
            </body>
        </html>
        """
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.text = mock_html
            mock_response.encoding = 'utf-8'
            mock_response.raise_for_status = MagicMock()
            
            mock_client.get.return_value = mock_response
            
            result = await self.scraper._make_request("https://test.com")
            assert result == mock_html

    @pytest.mark.asyncio
    async def test_make_request_failure(self):
        """HTTP 요청 실패 테스트"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_client.get.side_effect = Exception("Network error")
            
            result = await self.scraper._make_request("https://test.com")
            assert result is None

    def test_parse_article_from_element_success(self):
        """기사 파싱 성공 테스트"""
        from bs4 import BeautifulSoup
        
        html = """
        <div class="item">
            <a href="/news/001" data-clk="art_tit">테스트 뉴스 제목</a>
            <div class="summary">테스트 요약 내용</div>
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div', class_='item')
        
        article = self.scraper._parse_article_from_element(
            element, "정치", "https://news.naver.com"
        )
        
        assert article is not None
        assert article.title == "테스트 뉴스 제목"
        assert article.url == "https://news.naver.com/news/001"
        assert article.category == "정치"
        assert article.summary == "테스트 요약 내용"

    def test_parse_article_from_element_invalid(self):
        """잘못된 요소 파싱 테스트"""
        from bs4 import BeautifulSoup
        
        html = "<div>내용 없음</div>"
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div')
        
        article = self.scraper._parse_article_from_element(
            element, "정치", "https://news.naver.com"
        )
        
        assert article is None

    def test_parse_headlines_from_html(self):
        """HTML에서 헤드라인 파싱 테스트"""
        mock_html = """
        <html>
            <body>
                <div class="hdline_article_tit">
                    <a href="/news/001">첫 번째 뉴스</a>
                </div>
                <div class="cluster_text_headline">
                    <a href="/news/002">두 번째 뉴스</a>
                </div>
                <div class="list_body">
                    <div class="item">
                        <a href="/news/003">세 번째 뉴스</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
        articles = self.scraper._parse_headlines_from_html(mock_html, "정치")
        
        assert len(articles) >= 1
        assert all(isinstance(article, NewsArticle) for article in articles)
        assert all(article.category == "정치" for article in articles)

    @pytest.mark.asyncio
    async def test_scrape_category_invalid(self):
        """잘못된 카테고리 스크래핑 테스트"""
        with pytest.raises(ScrapingError):
            await self.scraper.scrape_category("잘못된카테고리")

    @pytest.mark.asyncio
    async def test_scrape_all_categories(self):
        """전체 카테고리 스크래핑 테스트"""
        mock_html = """
        <div class="hdline_article_tit">
            <a href="/news/001">테스트 뉴스</a>
        </div>
        """
        
        with patch.object(self.scraper, '_make_request') as mock_request:
            mock_request.return_value = mock_html
            
            categories = ["정치", "경제"]
            result = await self.scraper.scrape_all_categories(categories)
            
            assert isinstance(result, dict)
            assert "정치" in result
            assert "경제" in result
            assert all(isinstance(articles, list) for articles in result.values())


class TestScrapingUtilities:
    """스크래핑 유틸리티 함수 테스트"""

    def test_validate_category(self):
        """카테고리 검증 테스트"""
        assert validate_category("정치") == True
        assert validate_category("경제") == True
        assert validate_category("잘못된카테고리") == False

    def test_get_category_url(self):
        """카테고리 URL 생성 테스트"""
        url = get_category_url("정치")
        assert "news.naver.com" in url
        assert "100" in url  # 정치 카테고리 ID

        with pytest.raises(ValueError):
            get_category_url("잘못된카테고리")


class TestScraperNode:
    """LangGraph 스크래퍼 노드 테스트"""

    @pytest.mark.asyncio
    async def test_scraper_node_success(self):
        """스크래퍼 노드 성공 테스트"""
        initial_state = create_initial_state(["정치"])
        
        mock_scraped_data = {
            "정치": [
                NewsArticle(
                    title="테스트 뉴스",
                    url="https://news.naver.com/test",
                    category="정치"
                )
            ]
        }
        
        with patch('src.nodes.scraper.NaverNewsScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper_class.return_value = mock_scraper
            mock_scraper.scrape_all_categories.return_value = mock_scraped_data
            
            result = await scraper_node(initial_state)
            
            assert "raw_news" in result
            assert len(result["raw_news"]) == 1
            assert result["raw_news"][0]["category"] == "정치"
            assert result["total_articles_scraped"] == 1
            assert "scraping_duration" in result

    @pytest.mark.asyncio
    async def test_scraper_node_failure(self):
        """스크래퍼 노드 실패 테스트"""
        initial_state = create_initial_state(["정치"])
        
        with patch('src.nodes.scraper.NaverNewsScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper_class.return_value = mock_scraper
            mock_scraper.scrape_all_categories.side_effect = Exception("스크래핑 오류")
            
            result = await scraper_node(initial_state)
            
            assert len(result["errors"]) > 0
            assert "스크래핑 오류" in result["errors"][0]
            assert result["total_articles_scraped"] == 0

    @pytest.mark.asyncio
    async def test_scraper_node_empty_results(self):
        """스크래퍼 노드 빈 결과 테스트"""
        initial_state = create_initial_state(["정치"])
        
        mock_scraped_data = {"정치": []}  # 빈 결과
        
        with patch('src.nodes.scraper.NaverNewsScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper_class.return_value = mock_scraper
            mock_scraper.scrape_all_categories.return_value = mock_scraped_data
            
            result = await scraper_node(initial_state)
            
            assert result["total_articles_scraped"] == 0
            assert "스크래핑된 기사가 없습니다" in result["errors"]


class TestScrapingPerformance:
    """스크래핑 성능 테스트"""

    @pytest.mark.asyncio
    async def test_scraping_timeout(self):
        """스크래핑 타임아웃 테스트"""
        scraper = NaverNewsScraper(timeout=0.001)  # 매우 짧은 타임아웃
        
        # 실제 네트워크 요청은 타임아웃될 것
        result = await scraper._make_request("https://news.naver.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_scraping_performance(self):
        """동시 스크래핑 성능 테스트"""
        scraper = NaverNewsScraper(request_delay=0.01)
        
        mock_html = "<div class='hdline_article_tit'><a href='/test'>테스트</a></div>"
        
        with patch.object(scraper, '_make_request') as mock_request:
            mock_request.return_value = mock_html
            
            import time
            start_time = time.time()
            
            categories = ["정치", "경제", "사회"]
            result = await scraper.scrape_all_categories(categories)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 병렬 처리로 인해 순차 처리보다 빨라야 함
            assert duration < len(categories) * 0.5
            assert len(result) == len(categories)


# 테스트 픽스처
@pytest.fixture
def sample_news_html():
    """샘플 뉴스 HTML 반환"""
    return """
    <html>
        <head><title>네이버 뉴스</title></head>
        <body>
            <div class="hdline_article_tit">
                <a href="/news/main/001" data-clk="art_tit">
                    주요 정치 뉴스 제목
                </a>
            </div>
            <div class="cluster_text_headline">
                <a href="/news/main/002">경제 동향 분석</a>
            </div>
            <div class="list_body">
                <div class="item">
                    <a href="/news/main/003">사회 이슈 리포트</a>
                    <div class="summary">간단한 요약 내용입니다.</div>
                </div>
            </div>
            <ul class="type06_headline">
                <li>
                    <a href="/news/main/004">IT 기술 동향</a>
                </li>
            </ul>
        </body>
    </html>
    """


@pytest.fixture
def sample_news_articles():
    """샘플 뉴스 기사 목록 반환"""
    return [
        NewsArticle(
            title="첫 번째 테스트 뉴스",
            url="https://news.naver.com/news/001",
            category="정치",
            summary="첫 번째 뉴스 요약"
        ),
        NewsArticle(
            title="두 번째 테스트 뉴스",
            url="https://news.naver.com/news/002",
            category="정치",
            summary="두 번째 뉴스 요약"
        ),
        NewsArticle(
            title="세 번째 테스트 뉴스",
            url="https://news.naver.com/news/003",
            category="정치"
        )
    ]


# 통합 테스트
class TestScrapingIntegration:
    """스크래핑 통합 테스트"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_scraping_workflow(self, sample_news_html):
        """전체 스크래핑 워크플로우 테스트"""
        scraper = NaverNewsScraper(
            request_delay=0.1,
            max_articles_per_category=3
        )
        
        with patch.object(scraper, '_make_request') as mock_request:
            mock_request.return_value = sample_news_html
            
            # 전체 워크플로우 실행
            categories = ["정치", "경제"]
            result = await scraper.scrape_all_categories(categories)
            
            # 결과 검증
            assert len(result) == 2
            assert all(category in result for category in categories)
            
            for category, articles in result.items():
                assert isinstance(articles, list)
                for article in articles:
                    assert isinstance(article, NewsArticle)
                    assert article.category == category
                    assert article.title
                    assert article.url

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_scraper_node_integration(self):
        """스크래퍼 노드 통합 테스트"""
        # 환경변수 모킹
        with patch.dict('os.environ', {
            'USER_AGENT': 'Test Agent',
            'REQUEST_DELAY': '0.1'
        }):
            initial_state = create_initial_state(["정치"])
            
            mock_html = "<div class='hdline_article_tit'><a href='/test'>테스트</a></div>"
            
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                mock_response = MagicMock()
                mock_response.text = mock_html
                mock_response.encoding = 'utf-8'
                mock_response.raise_for_status = MagicMock()
                
                mock_client.get.return_value = mock_response
                
                result = await scraper_node(initial_state)
                
                # 상태 검증
                assert "raw_news" in result
                assert "scraping_duration" in result
                assert "total_articles_scraped" in result
                assert isinstance(result["scraping_duration"], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])