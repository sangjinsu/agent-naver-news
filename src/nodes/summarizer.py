"""
OpenAI 기반 뉴스 요약 노드

이 모듈은 OpenAI GPT 모델을 사용하여 스크래핑된 뉴스를 한국어로 요약하는 기능을 제공합니다.
한국어 특화 프롬프트 엔지니어링과 비용 최적화 로직이 포함되어 있습니다.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..models.schemas import (
    CATEGORY_EMOJIS,
    NewsAgentState,
    get_category_emoji,
)


# 로거 설정
logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    """요약 관련 예외"""
    pass


class NewsSummarizerService:
    """
    OpenAI 기반 뉴스 요약 서비스
    
    GPT-4o-mini 또는 GPT-4o를 사용하여 한국어 뉴스 요약을 생성합니다.
    비용 효율성과 품질을 고려한 모델 선택 로직을 포함합니다.
    """

    # 시스템 프롬프트 (한국어 특화)
    SYSTEM_PROMPT = """당신은 전문적인 한국 뉴스 에디터입니다. 
다음 역할을 수행해야 합니다:

1. 주어진 뉴스 목록을 분석하여 가장 중요한 뉴스 3-5개를 선별
2. 각 뉴스의 핵심 내용을 명확하고 간결하게 요약
3. 전체적인 트렌드와 시사점을 파악하여 '오늘의 포인트' 제시
4. 한국 독자들이 이해하기 쉬운 언어와 표현 사용
5. 객관적이고 균형잡힌 시각으로 정보 전달

출력 형식을 정확히 지켜주세요."""

    # 카테고리별 특화 프롬프트
    CATEGORY_PROMPTS = {
        "정치": """정치 뉴스 요약 시 다음 사항에 주목하세요:
- 정책 변화와 그 영향
- 정당 간 주요 이슈와 입장 차이
- 국정 운영과 관련된 중요 결정
- 선거나 정치적 변화의 의미""",
        
        "경제": """경제 뉴스 요약 시 다음 사항에 주목하세요:
- 주요 경제 지표의 변화와 의미
- 기업과 산업계의 중요한 움직임
- 금융 시장의 동향과 전망
- 일반 국민 생활에 미치는 영향""",
        
        "사회": """사회 뉴스 요약 시 다음 사항에 주목하세요:
- 사회 현상과 이슈의 배경
- 제도나 정책 변화가 시민에게 미치는 영향
- 사회 갈등과 그 해결 방안
- 문화적, 사회적 변화의 의미""",
        
        "생활/문화": """생활/문화 뉴스 요약 시 다음 사항에 주목하세요:
- 일상생활과 직접 관련된 정보
- 문화 트렌드와 새로운 현상
- 건강, 교육, 여가 관련 실용 정보
- 라이프스타일 변화와 그 의미""",
        
        "IT/과학": """IT/과학 뉴스 요약 시 다음 사항에 주목하세요:
- 기술 혁신과 그 사회적 영향
- 과학적 발견과 연구 성과
- 디지털 전환과 새로운 서비스
- 미래 기술 동향과 전망""",
        
        "세계": """세계 뉴스 요약 시 다음 사항에 주목하세요:
- 국제 정세 변화와 한국에 미치는 영향
- 주요 국가들의 정책과 외교 관계
- 글로벌 경제와 문화 동향
- 국제적 이슈와 그 의미"""
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 1000,
        max_retries: int = 3,
    ):
        """
        요약 서비스 초기화
        
        Args:
            api_key: OpenAI API 키
            model: 사용할 모델 (gpt-4o-mini, gpt-4o, gpt-3.5-turbo)
            temperature: 생성 온도 (0.0-2.0)
            max_tokens: 최대 토큰 수
            max_retries: 최대 재시도 횟수
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        
        # ChatOpenAI 인스턴스 생성
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=60.0,
        )
        
        logger.info(f"뉴스 요약 서비스 초기화: 모델={model}, 온도={temperature}")

    def _build_prompt(self, category: str, articles: List[Dict]) -> str:
        """
        카테고리와 기사 목록으로부터 프롬프트 생성
        
        Args:
            category: 뉴스 카테고리
            articles: 기사 목록
            
        Returns:
            완성된 프롬프트
        """
        # 카테고리별 특화 지침
        category_guidance = self.CATEGORY_PROMPTS.get(category, "")
        
        # 기사 목록 포맷팅
        articles_text = ""
        for i, article in enumerate(articles, 1):
            title = article.get('title', '제목 없음')
            summary = article.get('summary', '')
            url = article.get('url', '')
            
            articles_text += f"{i}. 제목: {title}\n"
            if summary:
                articles_text += f"   요약: {summary}\n"
            articles_text += f"   링크: {url}\n\n"
        
        # 카테고리 이모지
        emoji = get_category_emoji(category)
        
        prompt = f"""카테고리: {emoji} {category}

{category_guidance}

뉴스 목록:
{articles_text}

다음 형식으로 정확히 출력해주세요:

### 주요 뉴스

1. **[첫 번째 중요 뉴스 제목]**
   - 핵심 내용을 2-3문장으로 명확하게 요약
   - 배경과 의미를 포함하여 설명

2. **[두 번째 중요 뉴스 제목]**
   - 핵심 내용을 2-3문장으로 명확하게 요약
   - 배경과 의미를 포함하여 설명

[3-5개 뉴스까지 동일한 형식으로 계속]

### 오늘의 포인트

- {category} 분야의 주요 트렌드나 중요한 시사점을 3-4개 항목으로 정리
- 각 항목은 한 문장으로 간결하게 표현
- 전체적인 흐름과 의미를 파악할 수 있도록 구성

중요: 마크다운 형식을 정확히 지키고, 한국어로만 작성해주세요."""

        return prompt

    async def _summarize_with_retry(self, prompt: str, category: str) -> str:
        """
        재시도 메커니즘이 포함된 요약 생성
        
        Args:
            prompt: 요약 프롬프트
            category: 카테고리 (로깅용)
            
        Returns:
            생성된 요약 텍스트
            
        Raises:
            SummarizationError: 요약 생성 실패 시
        """
        for attempt in range(self.max_retries):
            try:
                messages = [
                    SystemMessage(content=self.SYSTEM_PROMPT),
                    HumanMessage(content=prompt)
                ]
                
                response = await self.llm.ainvoke(messages)
                summary = response.content.strip()
                
                if not summary:
                    raise ValueError("빈 응답 반환")
                
                logger.info(f"카테고리 '{category}' 요약 완료 (시도 {attempt + 1})")
                return summary
                
            except Exception as e:
                logger.warning(f"요약 생성 실패 (시도 {attempt + 1}/{self.max_retries}, 카테고리: {category}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # 지수 백오프
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise SummarizationError(f"카테고리 '{category}' 요약 생성 실패: {str(e)}")

    def _validate_summary(self, summary: str, category: str) -> bool:
        """
        생성된 요약의 품질 검증
        
        Args:
            summary: 검증할 요약 텍스트
            category: 카테고리
            
        Returns:
            검증 통과 여부
        """
        # 기본 검증 조건들
        checks = [
            len(summary) >= 100,  # 최소 길이
            "### 주요 뉴스" in summary,  # 필수 섹션
            "### 오늘의 포인트" in summary,  # 필수 섹션
            summary.count("**") >= 2,  # 최소 1개 이상의 굵은 글씨
            len(summary.split('\n')) >= 5,  # 최소 구조
        ]
        
        passed = sum(checks)
        total = len(checks)
        
        if passed < total * 0.8:  # 80% 이상 통과해야 함
            logger.warning(f"카테고리 '{category}' 요약 품질 검증 실패: {passed}/{total}")
            return False
        
        logger.debug(f"카테고리 '{category}' 요약 품질 검증 통과: {passed}/{total}")
        return True

    async def summarize_category(self, category: str, articles: List[Dict]) -> str:
        """
        특정 카테고리의 뉴스 기사들을 요약
        
        Args:
            category: 뉴스 카테고리
            articles: 기사 목록
            
        Returns:
            마크다운 형식의 요약 텍스트
            
        Raises:
            SummarizationError: 요약 생성 실패 시
        """
        if not articles:
            logger.warning(f"카테고리 '{category}'에 요약할 기사가 없습니다")
            return f"### {get_category_emoji(category)} {category}\n\n요약할 뉴스가 없습니다.\n"
        
        start_time = time.time()
        logger.info(f"카테고리 '{category}' 요약 시작: {len(articles)}개 기사")
        
        try:
            # 프롬프트 생성
            prompt = self._build_prompt(category, articles)
            
            # 요약 생성
            summary = await self._summarize_with_retry(prompt, category)
            
            # 품질 검증
            if not self._validate_summary(summary, category):
                logger.warning(f"카테고리 '{category}' 요약 품질이 기준에 미달, 그대로 반환")
            
            duration = time.time() - start_time
            logger.info(f"카테고리 '{category}' 요약 완료: {len(summary)}자, {duration:.2f}초")
            
            return summary
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"카테고리 '{category}' 요약 실패 ({duration:.2f}초): {str(e)}"
            logger.error(error_msg)
            
            # fallback 요약 생성
            fallback = self._generate_fallback_summary(category, articles)
            return fallback

    def _generate_fallback_summary(self, category: str, articles: List[Dict]) -> str:
        """
        AI 요약 실패 시 기본 요약 생성
        
        Args:
            category: 카테고리
            articles: 기사 목록
            
        Returns:
            기본 요약 텍스트
        """
        emoji = get_category_emoji(category)
        summary = f"### {emoji} {category}\n\n"
        summary += "### 주요 뉴스\n\n"
        
        # 상위 5개 기사만 표시
        for i, article in enumerate(articles[:5], 1):
            title = article.get('title', '제목 없음')
            summary += f"{i}. **{title}**\n"
            
            if article.get('summary'):
                summary += f"   - {article['summary']}\n"
            summary += "\n"
        
        summary += "### 오늘의 포인트\n\n"
        summary += f"- {category} 분야에서 {len(articles)}개의 뉴스가 보도되었습니다\n"
        summary += "- 자세한 내용은 개별 기사를 참고해 주세요\n"
        
        return summary

    async def summarize_all_categories(self, raw_news_data: List[Dict]) -> List[Dict]:
        """
        모든 카테고리의 뉴스를 병렬로 요약
        
        Args:
            raw_news_data: 카테고리별 원본 뉴스 데이터
            
        Returns:
            카테고리별 요약 결과 리스트
        """
        start_time = time.time()
        logger.info(f"{len(raw_news_data)}개 카테고리 요약 시작")
        
        # 병렬 처리를 위한 세마포어 (API 속도 제한 고려)
        semaphore = asyncio.Semaphore(2)  # 최대 2개 동시 요청
        
        async def summarize_with_semaphore(category_data: Dict) -> Dict:
            async with semaphore:
                category = category_data["category"]
                articles = category_data["articles"]
                
                try:
                    summary = await self.summarize_category(category, articles)
                    return {
                        "category": category,
                        "summary": summary,
                        "article_count": len(articles),
                        "success": True
                    }
                except Exception as e:
                    logger.error(f"카테고리 '{category}' 요약 오류: {str(e)}")
                    fallback = self._generate_fallback_summary(category, articles)
                    return {
                        "category": category,
                        "summary": fallback,
                        "article_count": len(articles),
                        "success": False,
                        "error": str(e)
                    }
        
        # 모든 카테고리 병렬 요약
        tasks = [summarize_with_semaphore(data) for data in raw_news_data]
        results = await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r["success"])
        total_articles = sum(r["article_count"] for r in results)
        
        logger.info(f"전체 요약 완료: {success_count}/{len(results)} 성공, {total_articles}개 기사, {duration:.2f}초")
        
        return results


# LangGraph 노드 함수
async def summarizer_node(state: NewsAgentState) -> NewsAgentState:
    """
    LangGraph 요약 노드
    
    Args:
        state: 현재 에이전트 상태
        
    Returns:
        업데이트된 에이전트 상태
    """
    start_time = time.time()
    logger.info("요약 노드 실행 시작")
    
    try:
        # 환경변수에서 설정 로드
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        if not api_key:
            raise SummarizationError("OPENAI_API_KEY가 설정되지 않았습니다")
        
        # 요약 서비스 초기화
        summarizer = NewsSummarizerService(
            api_key=api_key,
            model=model,
            temperature=0.3,
            max_tokens=1000
        )
        
        # 스크래핑된 뉴스 데이터 확인
        raw_news = state.get("raw_news", [])
        if not raw_news:
            raise SummarizationError("요약할 뉴스 데이터가 없습니다")
        
        # 요약 실행
        summaries = await summarizer.summarize_all_categories(raw_news)
        
        duration = time.time() - start_time
        
        # 상태 업데이트
        updated_state = state.copy()
        updated_state["summaries"] = summaries
        updated_state["summarization_duration"] = duration
        
        # 실패한 요약이 있으면 에러에 추가
        failed_summaries = [s for s in summaries if not s["success"]]
        if failed_summaries:
            for failed in failed_summaries:
                error_msg = f"카테고리 '{failed['category']}' 요약 실패: {failed.get('error', '알 수 없는 오류')}"
                updated_state["errors"].append(error_msg)
        
        success_count = len([s for s in summaries if s["success"]])
        logger.info(f"요약 노드 완료: {success_count}/{len(summaries)} 성공, {duration:.2f}초")
        
        return updated_state
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"요약 노드 오류: {str(e)}"
        logger.error(error_msg)
        
        updated_state = state.copy()
        updated_state["errors"].append(error_msg)
        updated_state["summarization_duration"] = duration
        updated_state["summaries"] = []
        
        return updated_state