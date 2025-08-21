"""
요약 모듈 단위 테스트

이 테스트는 OpenAI 기반 뉴스 요약 기능을 검증합니다.
실제 OpenAI API 호출 대신 모킹을 사용하여 안정적인 테스트를 제공합니다.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List

from src.nodes.summarizer import (
    NewssummarizerService,
    summarizer_node,
    SummarizationError
)
from src.models.schemas import (
    NewsAgentState,
    create_initial_state,
    get_category_emoji
)


class TestNewsSummarizerService:
    """NewssummarizerService 클래스 테스트"""

    def setup_method(self):
        """각 테스트 메서드 실행 전 설정"""
        self.service = NewssummarizerService(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=500,
            max_retries=2
        )

    def test_service_initialization(self):
        """서비스 초기화 테스트"""
        assert self.service.api_key == "test-key"
        assert self.service.model == "gpt-4o-mini"
        assert self.service.temperature == 0.3
        assert self.service.max_tokens == 500
        assert self.service.max_retries == 2

    def test_build_prompt(self):
        """프롬프트 생성 테스트"""
        articles = [
            {
                "title": "테스트 뉴스 제목 1",
                "summary": "테스트 요약 1",
                "url": "https://test1.com"
            },
            {
                "title": "테스트 뉴스 제목 2", 
                "summary": "테스트 요약 2",
                "url": "https://test2.com"
            }
        ]
        
        prompt = self.service._build_prompt("정치", articles)
        
        assert "정치" in prompt
        assert "테스트 뉴스 제목 1" in prompt
        assert "테스트 뉴스 제목 2" in prompt
        assert "### 주요 뉴스" in prompt
        assert "### 오늘의 포인트" in prompt
        assert get_category_emoji("정치") in prompt

    def test_build_prompt_empty_articles(self):
        """빈 기사 목록으로 프롬프트 생성 테스트"""
        prompt = self.service._build_prompt("경제", [])
        
        assert "경제" in prompt
        assert "### 주요 뉴스" in prompt
        assert "### 오늘의 포인트" in prompt

    def test_validate_summary_success(self):
        """요약 검증 성공 테스트"""
        valid_summary = """
### 주요 뉴스

1. **테스트 제목**
   - 테스트 내용

### 오늘의 포인트

- 주요 시사점
"""
        
        assert self.service._validate_summary(valid_summary, "정치") == True

    def test_validate_summary_failure(self):
        """요약 검증 실패 테스트"""
        invalid_summary = "너무 짧은 요약"
        
        assert self.service._validate_summary(invalid_summary, "정치") == False

    @pytest.mark.asyncio
    async def test_summarize_with_retry_success(self):
        """재시도 요약 성공 테스트"""
        mock_response = MagicMock()
        mock_response.content = """
### 주요 뉴스

1. **테스트 뉴스**
   - 테스트 내용입니다.

### 오늘의 포인트

- 중요한 포인트
"""
        
        with patch.object(self.service.llm, 'ainvoke', return_value=mock_response):
            result = await self.service._summarize_with_retry("test prompt", "정치")
            
            assert "### 주요 뉴스" in result
            assert "테스트 뉴스" in result

    @pytest.mark.asyncio
    async def test_summarize_with_retry_failure(self):
        """재시도 요약 실패 테스트"""
        with patch.object(self.service.llm, 'ainvoke', side_effect=Exception("API 오류")):
            with pytest.raises(SummarizationError):
                await self.service._summarize_with_retry("test prompt", "정치")

    @pytest.mark.asyncio
    async def test_summarize_category_success(self):
        """카테고리 요약 성공 테스트"""
        articles = [
            {
                "title": "정치 뉴스 1",
                "summary": "정치 요약 1",
                "url": "https://politics1.com"
            }
        ]
        
        mock_response = MagicMock()
        mock_response.content = """
### 주요 뉴스

1. **정치 뉴스 1**
   - 정치 관련 내용입니다.

### 오늘의 포인트

- 정치적 시사점
"""
        
        with patch.object(self.service.llm, 'ainvoke', return_value=mock_response):
            result = await self.service.summarize_category("정치", articles)
            
            assert "정치 뉴스 1" in result
            assert "### 주요 뉴스" in result
            assert "### 오늘의 포인트" in result

    @pytest.mark.asyncio
    async def test_summarize_category_empty_articles(self):
        """빈 기사 목록 요약 테스트"""
        result = await self.service.summarize_category("정치", [])
        
        assert "요약할 뉴스가 없습니다" in result
        assert get_category_emoji("정치") in result

    def test_generate_fallback_summary(self):
        """대체 요약 생성 테스트"""
        articles = [
            {"title": "뉴스 1", "summary": "요약 1", "url": "url1"},
            {"title": "뉴스 2", "summary": "요약 2", "url": "url2"}
        ]
        
        fallback = self.service._generate_fallback_summary("정치", articles)
        
        assert "뉴스 1" in fallback
        assert "뉴스 2" in fallback
        assert "### 주요 뉴스" in fallback
        assert "### 오늘의 포인트" in fallback
        assert get_category_emoji("정치") in fallback

    @pytest.mark.asyncio
    async def test_summarize_all_categories(self):
        """전체 카테고리 요약 테스트"""
        raw_news_data = [
            {
                "category": "정치",
                "articles": [
                    {"title": "정치 뉴스", "summary": "정치 요약", "url": "url1"}
                ]
            },
            {
                "category": "경제", 
                "articles": [
                    {"title": "경제 뉴스", "summary": "경제 요약", "url": "url2"}
                ]
            }
        ]
        
        mock_response = MagicMock()
        mock_response.content = """
### 주요 뉴스

1. **테스트 뉴스**
   - 테스트 내용

### 오늘의 포인트

- 주요 포인트
"""
        
        with patch.object(self.service.llm, 'ainvoke', return_value=mock_response):
            results = await self.service.summarize_all_categories(raw_news_data)
            
            assert len(results) == 2
            assert all(result["success"] for result in results)
            assert any(result["category"] == "정치" for result in results)
            assert any(result["category"] == "경제" for result in results)


class TestSummarizerNode:
    """LangGraph 요약 노드 테스트"""

    @pytest.mark.asyncio
    async def test_summarizer_node_success(self):
        """요약 노드 성공 테스트"""
        state = {
            "raw_news": [
                {
                    "category": "정치",
                    "articles": [
                        {
                            "title": "정치 뉴스",
                            "summary": "정치 요약",
                            "url": "https://politics.com"
                        }
                    ]
                }
            ],
            "summaries": [],
            "errors": []
        }
        
        mock_summary_result = [
            {
                "category": "정치",
                "summary": "### 주요 뉴스\n1. **정치 뉴스** - 정치 내용",
                "article_count": 1,
                "success": True
            }
        ]
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.nodes.summarizer.NewssummarizerService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                mock_service.summarize_all_categories.return_value = mock_summary_result
                
                result = await summarizer_node(state)
                
                assert "summaries" in result
                assert len(result["summaries"]) == 1
                assert result["summaries"][0]["success"] == True
                assert "summarization_duration" in result

    @pytest.mark.asyncio
    async def test_summarizer_node_missing_api_key(self):
        """API 키 누락 테스트"""
        state = {
            "raw_news": [],
            "summaries": [],
            "errors": []
        }
        
        with patch.dict('os.environ', {}, clear=True):
            result = await summarizer_node(state)
            
            assert len(result["errors"]) > 0
            assert "OPENAI_API_KEY" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_summarizer_node_no_raw_news(self):
        """원본 뉴스 없음 테스트"""
        state = {
            "raw_news": [],
            "summaries": [],
            "errors": []
        }
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            result = await summarizer_node(state)
            
            assert len(result["errors"]) > 0
            assert "요약할 뉴스 데이터가 없습니다" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_summarizer_node_partial_failure(self):
        """부분 실패 테스트"""
        state = {
            "raw_news": [
                {
                    "category": "정치",
                    "articles": [{"title": "뉴스1", "url": "url1"}]
                },
                {
                    "category": "경제",
                    "articles": [{"title": "뉴스2", "url": "url2"}]
                }
            ],
            "summaries": [],
            "errors": []
        }
        
        mock_summary_result = [
            {
                "category": "정치",
                "summary": "정치 요약",
                "article_count": 1,
                "success": True
            },
            {
                "category": "경제",
                "summary": "경제 대체 요약",
                "article_count": 1,
                "success": False,
                "error": "API 호출 실패"
            }
        ]
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.nodes.summarizer.NewssummarizerService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                mock_service.summarize_all_categories.return_value = mock_summary_result
                
                result = await summarizer_node(state)
                
                assert len(result["summaries"]) == 2
                assert len(result["errors"]) > 0
                assert any("경제" in error for error in result["errors"])


class TestPromptEngineering:
    """프롬프트 엔지니어링 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.service = NewssummarizerService(
            api_key="test-key",
            model="gpt-4o-mini"
        )

    def test_category_specific_prompts(self):
        """카테고리별 특화 프롬프트 테스트"""
        articles = [{"title": "테스트", "summary": "요약", "url": "url"}]
        
        # 각 카테고리별 프롬프트 확인
        categories = ["정치", "경제", "사회", "생활/문화", "IT/과학", "세계"]
        
        for category in categories:
            prompt = self.service._build_prompt(category, articles)
            
            # 카테고리별 특화 지침 포함 확인
            assert category in prompt
            if category in self.service.CATEGORY_PROMPTS:
                # 일부 특화 내용 포함 확인
                assert len(prompt) > 500  # 기본 프롬프트보다 길어야 함

    def test_prompt_structure(self):
        """프롬프트 구조 테스트"""
        articles = [
            {"title": "뉴스1", "summary": "요약1", "url": "url1"},
            {"title": "뉴스2", "summary": "요약2", "url": "url2"}
        ]
        
        prompt = self.service._build_prompt("정치", articles)
        
        # 필수 구성요소 확인
        assert "카테고리:" in prompt
        assert "뉴스 목록:" in prompt
        assert "### 주요 뉴스" in prompt
        assert "### 오늘의 포인트" in prompt
        assert "한국어로만 작성" in prompt
        
        # 기사 정보 포함 확인
        assert "뉴스1" in prompt
        assert "뉴스2" in prompt

    def test_prompt_length_management(self):
        """프롬프트 길이 관리 테스트"""
        # 많은 기사로 테스트
        articles = [
            {"title": f"뉴스 제목 {i}", "summary": f"요약 {i}", "url": f"url{i}"}
            for i in range(20)
        ]
        
        prompt = self.service._build_prompt("정치", articles)
        
        # 프롬프트가 합리적인 길이인지 확인 (너무 길지 않아야 함)
        assert len(prompt) < 10000  # 10KB 제한
        assert "뉴스 제목 1" in prompt  # 첫 번째 기사 포함
        assert "뉴스 제목 19" in prompt  # 마지막 기사 포함


class TestSummarizationPerformance:
    """요약 성능 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_summarization(self):
        """동시 요약 성능 테스트"""
        service = NewssummarizerService(
            api_key="test-key",
            concurrent_requests=2
        )
        
        raw_news_data = [
            {
                "category": f"카테고리{i}",
                "articles": [{"title": f"뉴스{i}", "url": f"url{i}"}]
            }
            for i in range(4)
        ]
        
        mock_response = MagicMock()
        mock_response.content = "### 주요 뉴스\n1. **테스트** - 내용\n### 오늘의 포인트\n- 포인트"
        
        with patch.object(service.llm, 'ainvoke', return_value=mock_response):
            import time
            start_time = time.time()
            
            results = await service.summarize_all_categories(raw_news_data)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 병렬 처리로 인해 빨라야 함
            assert duration < 2.0  # 2초 이내
            assert len(results) == 4

    @pytest.mark.asyncio
    async def test_summarization_timeout_handling(self):
        """요약 타임아웃 처리 테스트"""
        service = NewssummarizerService(
            api_key="test-key",
            timeout=0.001,  # 매우 짧은 타임아웃
            max_retries=1
        )
        
        articles = [{"title": "테스트", "summary": "요약", "url": "url"}]
        
        with patch.object(service.llm, 'ainvoke', side_effect=asyncio.TimeoutError()):
            try:
                await service.summarize_category("정치", articles)
                assert False, "타임아웃 예외가 발생해야 함"
            except SummarizationError:
                pass  # 예상된 동작


# 통합 테스트
class TestSummarizationIntegration:
    """요약 통합 테스트"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_summarization_workflow(self):
        """전체 요약 워크플로우 테스트"""
        # 실제와 유사한 뉴스 데이터
        raw_news_data = [
            {
                "category": "정치",
                "articles": [
                    {
                        "title": "국정감사에서 드러난 정부 정책의 문제점",
                        "summary": "야당이 정부 정책의 허점을 집중 추궁했다",
                        "url": "https://news.naver.com/politics/001"
                    },
                    {
                        "title": "여야 대립 속 예산안 심사 난항",
                        "summary": "내년도 예산안을 둘러싼 여야 갈등이 심화되고 있다",
                        "url": "https://news.naver.com/politics/002"
                    }
                ]
            },
            {
                "category": "경제",
                "articles": [
                    {
                        "title": "중앙은행 기준금리 동결 결정",
                        "summary": "통화정책위원회가 기준금리를 현행 유지하기로 했다",
                        "url": "https://news.naver.com/economy/001"
                    }
                ]
            }
        ]
        
        service = NewssummarizerService(
            api_key="test-key",
            model="gpt-4o-mini"
        )
        
        # 실제와 유사한 응답 모킹
        mock_responses = [
            """### 주요 뉴스

1. **국정감사에서 드러난 정부 정책의 문제점**
   - 야당이 정부 정책의 허점을 집중 추궁하며 정책 개선을 요구했습니다.
   - 국정감사를 통해 여러 부처의 예산 집행과 정책 효과에 대한 문제점이 지적되었습니다.

2. **여야 대립 속 예산안 심사 난항**
   - 내년도 예산안을 둘러싼 여야 간 갈등이 심화되면서 국회 예산 심사가 지연되고 있습니다.
   - 복지 예산과 국방비 증액을 둘러싼 입장 차이가 주요 쟁점으로 떠올랐습니다.

### 오늘의 포인트

- 국정감사를 통해 정부 정책의 실효성 검증이 이뤄지고 있음
- 예산안 처리 지연으로 내년 정부 운영에 차질 우려
- 여야 간 정치적 대립이 민생 현안 해결에 영향을 미칠 가능성""",
            
            """### 주요 뉴스

1. **중앙은행 기준금리 동결 결정**
   - 한국은행 통화정책위원회가 기준금리를 현행 3.5%로 유지하기로 결정했습니다.
   - 인플레이션 안정화와 경제 성장률 둔화를 종합적으로 고려한 결과입니다.

### 오늘의 포인트

- 물가 안정세를 유지하면서 경제 활력 제고가 중요한 과제
- 글로벌 경제 불확실성 속에서 신중한 통화정책 기조 유지"""
        ]
        
        with patch.object(service.llm, 'ainvoke') as mock_ainvoke:
            mock_ainvoke.side_effect = [
                MagicMock(content=response) for response in mock_responses
            ]
            
            results = await service.summarize_all_categories(raw_news_data)
            
            # 결과 검증
            assert len(results) == 2
            
            politics_result = next(r for r in results if r["category"] == "정치")
            economy_result = next(r for r in results if r["category"] == "경제")
            
            assert politics_result["success"] == True
            assert economy_result["success"] == True
            
            assert "국정감사" in politics_result["summary"]
            assert "기준금리" in economy_result["summary"]
            
            assert politics_result["article_count"] == 2
            assert economy_result["article_count"] == 1


# 테스트 픽스처
@pytest.fixture
def sample_articles():
    """샘플 기사 데이터 반환"""
    return [
        {
            "title": "정부 신정책 발표, 경제 활성화 기대",
            "summary": "정부가 새로운 경제 정책을 발표하며 경제 활성화에 대한 기대감이 높아지고 있다",
            "url": "https://news.naver.com/001"
        },
        {
            "title": "중소기업 지원 방안 구체화",
            "summary": "중소기업을 위한 세제 혜택과 금융 지원 방안이 구체적으로 마련되었다",
            "url": "https://news.naver.com/002"
        },
        {
            "title": "디지털 전환 가속화 정책 추진",
            "summary": "기업의 디지털 전환을 지원하기 위한 정책이 본격 추진된다",
            "url": "https://news.naver.com/003"
        }
    ]


@pytest.fixture
def mock_openai_response():
    """모킹된 OpenAI 응답 반환"""
    return """### 주요 뉴스

1. **정부 신정책 발표, 경제 활성화 기대**
   - 정부가 발표한 새로운 경제 정책으로 시장에서 긍정적인 반응을 보이고 있습니다.
   - 특히 중소기업과 스타트업 지원 방안이 주목받고 있습니다.

2. **중소기업 지원 방안 구체화**
   - 세제 혜택 확대와 저리 대출 지원을 통해 중소기업의 자금난 해소가 기대됩니다.
   - 고용 창출 효과도 동반될 것으로 예상됩니다.

3. **디지털 전환 가속화 정책 추진**
   - 4차 산업혁명 시대에 맞춘 기업의 디지털 전환을 적극 지원합니다.
   - AI와 빅데이터 활용 역량 강화에 중점을 둡니다.

### 오늘의 포인트

- 정부의 적극적인 경제 정책으로 성장 동력 확보 기대
- 중소기업 중심의 지원으로 고용 안정화 효과 전망
- 디지털 전환을 통한 산업 경쟁력 강화 추진"""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])