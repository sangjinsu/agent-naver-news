"""
네이버 뉴스 스크래핑 노드

이 모듈은 네이버 뉴스 웹사이트에서 헤드라인 뉴스를 스크래핑하는 기능을 제공합니다.
LangGraph 노드로 구현되어 있으며, 안정성과 성능을 고려한 설계입니다.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from ..models.schemas import (
    NAVER_NEWS_CATEGORIES,
    NAVER_NEWS_BASE_URL,
    NewsAgentState,
    NewsArticle,
    get_category_url,
    validate_category,
)


# 로거 설정
logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """스크래핑 관련 예외"""
    pass


class NaverNewsScraper:
    """
    네이버 뉴스 헤드라인 스크래퍼
    
    httpx와 BeautifulSoup를 사용하여 네이버 뉴스의 카테고리별 헤드라인을 수집합니다.
    Rate limiting, 에러 처리, 재시도 메커니즘을 포함합니다.
    """

    def __init__(
        self,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        request_delay: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        max_articles_per_category: int = 15,
    ):
        """
        스크래퍼 초기화
        
        Args:
            user_agent: HTTP User-Agent 헤더
            request_delay: 요청 간 지연 시간 (초)
            timeout: HTTP 요청 타임아웃 (초)
            max_retries: 최대 재시도 횟수
            max_articles_per_category: 카테고리당 최대 기사 수
        """
        self.user_agent = user_agent
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_articles_per_category = max_articles_per_category
        
        # HTTP 클라이언트 설정
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _make_request(self, url: str) -> Optional[str]:
        """
        HTTP 요청 수행 (재시도 메커니즘 포함)
        
        Args:
            url: 요청할 URL
            
        Returns:
            HTML 응답 텍스트 또는 None (실패 시)
        """
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    headers=self.headers,
                    timeout=self.timeout,
                    follow_redirects=True
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    # 응답 인코딩 확인
                    if response.encoding is None:
                        response.encoding = 'utf-8'
                    
                    logger.info(f"성공적으로 페이지를 가져왔습니다: {url}")
                    return response.text
                    
            except httpx.TimeoutException:
                logger.warning(f"타임아웃 발생 (시도 {attempt + 1}/{self.max_retries}): {url}")
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP 오류 {e.response.status_code} (시도 {attempt + 1}/{self.max_retries}): {url}")
            except Exception as e:
                logger.warning(f"요청 실패 (시도 {attempt + 1}/{self.max_retries}): {url} - {str(e)}")
            
            # 재시도 전 대기
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 지수 백오프
        
        logger.error(f"모든 재시도 실패: {url}")
        return None

    def _parse_article_from_element(self, element: Tag, category: str, base_url: str) -> Optional[NewsArticle]:
        """
        HTML 요소에서 뉴스 기사 정보 추출
        
        Args:
            element: BeautifulSoup 요소
            category: 뉴스 카테고리
            base_url: 기본 URL
            
        Returns:
            NewsArticle 객체 또는 None (파싱 실패 시)
        """
        try:
            # 제목과 링크 추출 - 여러 패턴 시도
            title_link = None
            title = ""
            url = ""
            
            # 패턴 0: 새로운 네이버 뉴스 구조 (2025년) - sa_text_title
            # 현재 요소가 이미 sa_text_title인 경우
            if element.name == 'a' and 'sa_text_title' in element.get('class', []):
                title_link = element
                # strong.sa_text_strong에서 제목 추출
                strong_element = element.find('strong', class_='sa_text_strong')
                if strong_element:
                    title = strong_element.get_text(strip=True)
                else:
                    title = element.get_text(strip=True)
                url = element.get('href', '')
            else:
                # 내부에서 sa_text_title 찾기
                sa_title_link = element.find('a', class_='sa_text_title')
                if sa_title_link:
                    title_link = sa_title_link
                    # strong.sa_text_strong에서 제목 추출
                    strong_element = sa_title_link.find('strong', class_='sa_text_strong')
                    if strong_element:
                        title = strong_element.get_text(strip=True)
                    else:
                        title = sa_title_link.get_text(strip=True)
                    url = sa_title_link.get('href', '')
            
            # 패턴 1: a 태그에서 직접 추출 (새로운 구조에서 이미 처리된 경우 스킵)
            if not title:
                title_link = element.find('a')
                if title_link:
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')
            
            # 패턴 2: .headline 클래스 시도
            if not title:
                headline = element.find(class_='headline')
                if headline and headline.find('a'):
                    title_link = headline.find('a')
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')
            
            # 패턴 3: data-clk 속성이 있는 링크 시도
            if not title:
                title_link = element.find('a', {'data-clk': True})
                if title_link:
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')
            
            # 제목이 없으면 스킵
            if not title or len(title.strip()) < 5:
                logger.debug(f"제목이 없거나 너무 짧음: '{title}'")
                return None
            
            # URL 정규화
            if url:
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = urljoin(base_url, url)
                elif not url.startswith('http'):
                    url = urljoin(base_url, url)
                logger.debug(f"URL 정규화 완료: {url}")
            else:
                logger.debug("URL이 없어서 스킵")
                return None
            
            # URL 유효성 검사
            parsed_url = urlparse(url)
            if not parsed_url.netloc:
                logger.debug(f"유효하지 않은 URL: {url}")
                return None
                
            # 네이버 뉴스 URL인지 확인
            if 'news.naver.com' not in url:
                logger.debug(f"네이버 뉴스가 아닌 URL: {url}")
                return None
            
            # 요약 텍스트 추출 시도 (새로운 구조 우선)
            summary = ""
            # 새로운 구조: sa_text_lede
            summary_element = element.find(class_='sa_text_lede')
            if summary_element:
                summary = summary_element.get_text(strip=True)
            else:
                # 기존 구조
                summary_element = element.find(class_=['summary', 'lead', 'desc'])
                if summary_element:
                    summary = summary_element.get_text(strip=True)
            
            return NewsArticle(
                title=title,
                url=url,
                summary=summary if summary else None,
                category=category
            )
            
        except Exception as e:
            logger.warning(f"기사 파싱 오류: {str(e)}")
            return None

    def _parse_headlines_from_html(self, html: str, category: str) -> List[NewsArticle]:
        """
        HTML에서 헤드라인 기사 목록 추출
        
        Args:
            html: HTML 문자열
            category: 뉴스 카테고리
            
        Returns:
            NewsArticle 객체 리스트
        """
        articles = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 다양한 선택자 패턴으로 헤드라인 요소 찾기 (2025년 현재 구조)
            selectors = [
                'a.sa_text_title',  # 현재 주요 뉴스 제목 링크
                'li.sa_item',  # 뉴스 아이템 전체
                '.sa_text_title',  # 텍스트 제목
                '.sa_thumb_link',  # 썸네일 링크
                # 백업 선택자 (이전 구조)
                '.hdline_article_tit',  # 주요 헤드라인
                '.cluster_text_headline a',  # 클러스터 헤드라인
                '.list_body .item',  # 리스트 아이템
                '.hdline_article',  # 헤드라인 기사
                '.news_area .news_tit a',  # 뉴스 영역
            ]
            
            elements_found = []
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"카테고리 '{category}'에서 선택자 '{selector}'로 {len(elements)}개 요소 발견")
                    elements_found.extend(elements)
                    
                    # 충분한 요소를 찾았으면 중단
                    if len(elements_found) >= self.max_articles_per_category * 2:
                        break
            
            # 중복 제거를 위한 URL 세트
            seen_urls = set()
            
            for element in elements_found:
                if len(articles) >= self.max_articles_per_category:
                    break
                
                article = self._parse_article_from_element(element, category, NAVER_NEWS_BASE_URL)
                
                if article and article.url not in seen_urls:
                    articles.append(article)
                    seen_urls.add(article.url)
                    logger.debug(f"기사 추가: {article.title[:50]}...")
            
            logger.info(f"카테고리 '{category}'에서 총 {len(articles)}개 기사 파싱 완료")
            
        except Exception as e:
            logger.error(f"HTML 파싱 오류 (카테고리: {category}): {str(e)}")
        
        return articles

    async def scrape_category(self, category: str) -> List[NewsArticle]:
        """
        특정 카테고리의 헤드라인 뉴스 스크래핑
        
        Args:
            category: 뉴스 카테고리
            
        Returns:
            NewsArticle 객체 리스트
            
        Raises:
            ScrapingError: 스크래핑 실패 시
        """
        if not validate_category(category):
            raise ScrapingError(f"지원되지 않는 카테고리: {category}")
        
        start_time = time.time()
        logger.info(f"카테고리 '{category}' 스크래핑 시작")
        
        try:
            url = get_category_url(category)
            html = await self._make_request(url)
            
            if html is None:
                raise ScrapingError(f"카테고리 '{category}' 페이지를 가져올 수 없습니다")
            
            articles = self._parse_headlines_from_html(html, category)
            
            duration = time.time() - start_time
            logger.info(f"카테고리 '{category}' 스크래핑 완료: {len(articles)}개 기사, {duration:.2f}초 소요")
            
            # Rate limiting을 위한 지연
            await asyncio.sleep(self.request_delay)
            
            return articles
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"카테고리 '{category}' 스크래핑 실패 ({duration:.2f}초): {str(e)}")
            raise ScrapingError(f"카테고리 '{category}' 스크래핑 실패: {str(e)}")

    async def scrape_all_categories(self, categories: List[str]) -> Dict[str, List[NewsArticle]]:
        """
        여러 카테고리의 뉴스를 병렬로 스크래핑
        
        Args:
            categories: 스크래핑할 카테고리 목록
            
        Returns:
            카테고리별 NewsArticle 딕셔너리
        """
        start_time = time.time()
        logger.info(f"{len(categories)}개 카테고리 스크래핑 시작: {categories}")
        
        # 병렬 처리를 위한 세마포어 (동시 요청 수 제한)
        semaphore = asyncio.Semaphore(3)  # 최대 3개 동시 요청
        
        async def scrape_with_semaphore(category: str) -> tuple[str, List[NewsArticle]]:
            async with semaphore:
                try:
                    articles = await self.scrape_category(category)
                    return category, articles
                except Exception as e:
                    logger.error(f"카테고리 '{category}' 스크래핑 오류: {str(e)}")
                    return category, []
        
        # 모든 카테고리 병렬 스크래핑
        tasks = [scrape_with_semaphore(category) for category in categories]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 정리
        scraped_data = {}
        total_articles = 0
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"스크래핑 태스크 오류: {str(result)}")
                continue
            
            category, articles = result
            scraped_data[category] = articles
            total_articles += len(articles)
        
        duration = time.time() - start_time
        logger.info(f"전체 스크래핑 완료: {total_articles}개 기사, {duration:.2f}초 소요")
        
        return scraped_data


# LangGraph 노드 함수
async def scraper_node(state: NewsAgentState) -> NewsAgentState:
    """
    LangGraph 스크래퍼 노드
    
    Args:
        state: 현재 에이전트 상태
        
    Returns:
        업데이트된 에이전트 상태
    """
    start_time = time.time()
    logger.info("스크래퍼 노드 실행 시작")
    
    try:
        # 설정값 로드 (환경변수에서)
        import os
        user_agent = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        request_delay = float(os.getenv("REQUEST_DELAY", "1.0"))
        
        # 스크래퍼 초기화
        scraper = NaverNewsScraper(
            user_agent=user_agent,
            request_delay=request_delay,
            max_articles_per_category=15
        )
        
        # 스크래핑 실행
        scraped_data = await scraper.scrape_all_categories(state["categories"])
        
        # 결과를 상태에 저장할 형태로 변환
        raw_news = []
        total_articles = 0
        
        for category, articles in scraped_data.items():
            category_data = {
                "category": category,
                "articles": [
                    {
                        "title": article.title,
                        "url": article.url,
                        "summary": article.summary,
                        "scraped_at": article.scraped_at.isoformat()
                    }
                    for article in articles
                ]
            }
            raw_news.append(category_data)
            total_articles += len(articles)
        
        duration = time.time() - start_time
        
        # 상태 업데이트
        updated_state = state.copy()
        updated_state["raw_news"] = raw_news
        updated_state["scraping_duration"] = duration
        updated_state["total_articles_scraped"] = total_articles
        
        if total_articles == 0:
            updated_state["errors"].append("스크래핑된 기사가 없습니다")
        
        logger.info(f"스크래퍼 노드 완료: {total_articles}개 기사, {duration:.2f}초")
        return updated_state
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"스크래핑 노드 오류: {str(e)}"
        logger.error(error_msg)
        
        updated_state = state.copy()
        updated_state["errors"].append(error_msg)
        updated_state["scraping_duration"] = duration
        updated_state["total_articles_scraped"] = 0
        
        return updated_state