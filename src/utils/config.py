"""
설정 관리 및 유틸리티 모듈

이 모듈은 뉴스 에이전트의 모든 설정을 중앙에서 관리하고
환경변수, 기본값, 검증 등을 처리합니다.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass
class ScrapingConfig:
    """스크래핑 관련 설정"""
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    request_delay: float = 1.0
    timeout: float = 30.0
    max_retries: int = 3
    max_articles_per_category: int = 15
    concurrent_requests: int = 3


@dataclass
class OpenAIConfig:
    """OpenAI 관련 설정"""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1000
    max_retries: int = 3
    timeout: float = 60.0
    concurrent_requests: int = 2


@dataclass
class OutputConfig:
    """출력 관련 설정"""
    output_dir: str = "./output/reports"
    include_metadata: bool = True
    include_stats: bool = True
    save_file: bool = True
    auto_cleanup_days: int = 30


@dataclass
class LoggingConfig:
    """로깅 관련 설정"""
    level: str = "INFO"
    file_path: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class GraphConfig:
    """LangGraph 관련 설정"""
    checkpointer: str = "memory"  # "memory", "sqlite", "none"
    enable_streaming: bool = True
    debug: bool = False
    thread_id_prefix: str = "news_thread"
    max_retries_scraping: int = 2
    max_retries_summarization: int = 1


@dataclass
class NewsAgentConfig:
    """뉴스 에이전트 전체 설정"""
    scraping: ScrapingConfig = field(default_factory=ScrapingConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    
    # 메타 정보
    version: str = "0.1.0"
    created_at: datetime = field(default_factory=datetime.now)
    categories: List[str] = field(default_factory=lambda: [
        "정치", "경제", "사회", "생활/문화", "IT/과학", "세계"
    ])


class ConfigManager:
    """
    설정 관리자
    
    환경변수와 기본값을 조합하여 설정을 관리하고
    런타임에 설정 변경을 지원합니다.
    """

    def __init__(self, env_file: Optional[str] = None, auto_load: bool = True):
        """
        설정 관리자 초기화
        
        Args:
            env_file: 환경변수 파일 경로
            auto_load: 자동으로 설정 로드 여부
        """
        self.env_file = env_file or ".env"
        self._config: Optional[NewsAgentConfig] = None
        self._validated: bool = False
        
        if auto_load:
            self.load_config()

    def load_config(self) -> NewsAgentConfig:
        """
        설정 로드 및 생성
        
        Returns:
            로드된 설정 객체
        """
        # 환경변수 파일 로드
        if Path(self.env_file).exists():
            load_dotenv(self.env_file)
        
        # 기본 설정 생성
        config = NewsAgentConfig()
        
        # 환경변수에서 설정 오버라이드
        self._load_scraping_config(config.scraping)
        self._load_openai_config(config.openai)
        self._load_output_config(config.output)
        self._load_logging_config(config.logging)
        self._load_graph_config(config.graph)
        
        self._config = config
        return config

    def _load_scraping_config(self, config: ScrapingConfig) -> None:
        """스크래핑 설정 로드"""
        config.user_agent = os.getenv("USER_AGENT", config.user_agent)
        config.request_delay = float(os.getenv("REQUEST_DELAY", config.request_delay))
        config.timeout = float(os.getenv("SCRAPING_TIMEOUT", config.timeout))
        config.max_retries = int(os.getenv("SCRAPING_MAX_RETRIES", config.max_retries))
        config.max_articles_per_category = int(os.getenv("MAX_ARTICLES_PER_CATEGORY", config.max_articles_per_category))
        config.concurrent_requests = int(os.getenv("SCRAPING_CONCURRENT_REQUESTS", config.concurrent_requests))

    def _load_openai_config(self, config: OpenAIConfig) -> None:
        """OpenAI 설정 로드"""
        config.api_key = os.getenv("OPENAI_API_KEY", config.api_key)
        config.model = os.getenv("OPENAI_MODEL", config.model)
        config.temperature = float(os.getenv("OPENAI_TEMPERATURE", config.temperature))
        config.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", config.max_tokens))
        config.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", config.max_retries))
        config.timeout = float(os.getenv("OPENAI_TIMEOUT", config.timeout))
        config.concurrent_requests = int(os.getenv("OPENAI_CONCURRENT_REQUESTS", config.concurrent_requests))

    def _load_output_config(self, config: OutputConfig) -> None:
        """출력 설정 로드"""
        config.output_dir = os.getenv("OUTPUT_DIR", config.output_dir)
        config.include_metadata = os.getenv("INCLUDE_METADATA", "true").lower() == "true"
        config.include_stats = os.getenv("INCLUDE_STATS", "true").lower() == "true"
        config.save_file = os.getenv("SAVE_FILE", "true").lower() == "true"
        config.auto_cleanup_days = int(os.getenv("AUTO_CLEANUP_DAYS", config.auto_cleanup_days))

    def _load_logging_config(self, config: LoggingConfig) -> None:
        """로깅 설정 로드"""
        config.level = os.getenv("LOG_LEVEL", config.level).upper()
        config.file_path = os.getenv("LOG_FILE")
        config.max_file_size = int(os.getenv("LOG_MAX_FILE_SIZE", config.max_file_size))
        config.backup_count = int(os.getenv("LOG_BACKUP_COUNT", config.backup_count))

    def _load_graph_config(self, config: GraphConfig) -> None:
        """그래프 설정 로드"""
        config.checkpointer = os.getenv("GRAPH_CHECKPOINTER", config.checkpointer)
        config.enable_streaming = os.getenv("GRAPH_STREAMING", "true").lower() == "true"
        config.debug = os.getenv("GRAPH_DEBUG", "false").lower() == "true"
        config.thread_id_prefix = os.getenv("GRAPH_THREAD_PREFIX", config.thread_id_prefix)
        config.max_retries_scraping = int(os.getenv("GRAPH_MAX_RETRIES_SCRAPING", config.max_retries_scraping))
        config.max_retries_summarization = int(os.getenv("GRAPH_MAX_RETRIES_SUMMARIZATION", config.max_retries_summarization))

    @property
    def config(self) -> NewsAgentConfig:
        """현재 설정 반환"""
        if self._config is None:
            self.load_config()
        return self._config

    def validate_config(self) -> List[str]:
        """
        설정 유효성 검사
        
        Returns:
            검증 오류 메시지 목록 (빈 리스트면 성공)
        """
        errors = []
        config = self.config
        
        # OpenAI 설정 검증
        if not config.openai.api_key:
            errors.append("OPENAI_API_KEY가 설정되지 않았습니다")
        elif not config.openai.api_key.startswith("sk-"):
            errors.append("OPENAI_API_KEY 형식이 올바르지 않습니다")
        
        valid_models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        if config.openai.model not in valid_models:
            errors.append(f"지원되지 않는 모델: {config.openai.model}")
        
        if not 0.0 <= config.openai.temperature <= 2.0:
            errors.append("OpenAI temperature는 0.0-2.0 범위여야 합니다")
        
        if config.openai.max_tokens < 100:
            errors.append("OpenAI max_tokens는 최소 100 이상이어야 합니다")
        
        # 스크래핑 설정 검증
        if config.scraping.request_delay < 0:
            errors.append("스크래핑 요청 지연은 0 이상이어야 합니다")
        
        if config.scraping.timeout < 1:
            errors.append("스크래핑 타임아웃은 1초 이상이어야 합니다")
        
        if config.scraping.max_articles_per_category < 1:
            errors.append("카테고리당 최대 기사 수는 1개 이상이어야 합니다")
        
        # 출력 설정 검증
        try:
            Path(config.output.output_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"출력 디렉토리 생성 실패: {config.output.output_dir} - {str(e)}")
        
        # 로깅 설정 검증
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if config.logging.level not in valid_log_levels:
            errors.append(f"지원되지 않는 로그 레벨: {config.logging.level}")
        
        # 그래프 설정 검증
        valid_checkpointers = ["memory", "sqlite", "none"]
        if config.graph.checkpointer not in valid_checkpointers:
            errors.append(f"지원되지 않는 체크포인터: {config.graph.checkpointer}")
        
        self._validated = len(errors) == 0
        return errors

    def is_valid(self) -> bool:
        """설정이 유효한지 확인"""
        if not self._validated:
            errors = self.validate_config()
            return len(errors) == 0
        return True

    def get_summary(self) -> Dict[str, Any]:
        """설정 요약 정보 반환"""
        config = self.config
        
        return {
            "version": config.version,
            "openai_model": config.openai.model,
            "categories_count": len(config.categories),
            "max_articles_per_category": config.scraping.max_articles_per_category,
            "output_dir": config.output.output_dir,
            "checkpointer": config.graph.checkpointer,
            "log_level": config.logging.level,
            "validated": self._validated
        }

    def update_setting(self, path: str, value: Any) -> None:
        """
        런타임에 설정값 업데이트
        
        Args:
            path: 설정 경로 (예: "openai.temperature")
            value: 새로운 값
        """
        config = self.config
        parts = path.split(".")
        
        if len(parts) != 2:
            raise ValueError("설정 경로는 'section.key' 형식이어야 합니다")
        
        section, key = parts
        
        if not hasattr(config, section):
            raise ValueError(f"존재하지 않는 설정 섹션: {section}")
        
        section_obj = getattr(config, section)
        
        if not hasattr(section_obj, key):
            raise ValueError(f"존재하지 않는 설정 키: {section}.{key}")
        
        setattr(section_obj, key, value)
        self._validated = False  # 재검증 필요

    def export_env_template(self, file_path: str = ".env.template") -> None:
        """
        환경변수 템플릿 파일 생성
        
        Args:
            file_path: 템플릿 파일 경로
        """
        template = """# 네이버 뉴스 헤드라인 요약 에이전트 환경 설정

# OpenAI API 설정 (필수)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_TOKENS=1000
OPENAI_MAX_RETRIES=3
OPENAI_TIMEOUT=60.0
OPENAI_CONCURRENT_REQUESTS=2

# 웹 스크래핑 설정
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REQUEST_DELAY=1.0
SCRAPING_TIMEOUT=30.0
SCRAPING_MAX_RETRIES=3
MAX_ARTICLES_PER_CATEGORY=15
SCRAPING_CONCURRENT_REQUESTS=3

# 출력 설정
OUTPUT_DIR=./output/reports
INCLUDE_METADATA=true
INCLUDE_STATS=true
SAVE_FILE=true
AUTO_CLEANUP_DAYS=30

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE=
LOG_MAX_FILE_SIZE=10485760
LOG_BACKUP_COUNT=5

# LangGraph 설정
GRAPH_CHECKPOINTER=memory
GRAPH_STREAMING=true
GRAPH_DEBUG=false
GRAPH_THREAD_PREFIX=news_thread
GRAPH_MAX_RETRIES_SCRAPING=2
GRAPH_MAX_RETRIES_SUMMARIZATION=1
"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(template)


# 전역 설정 관리자 인스턴스
_config_manager: Optional[ConfigManager] = None


def get_config_manager(env_file: Optional[str] = None) -> ConfigManager:
    """
    전역 설정 관리자 인스턴스 반환
    
    Args:
        env_file: 환경변수 파일 경로
        
    Returns:
        ConfigManager 인스턴스
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager(env_file)
    
    return _config_manager


def get_config(env_file: Optional[str] = None) -> NewsAgentConfig:
    """
    현재 설정 반환 편의 함수
    
    Args:
        env_file: 환경변수 파일 경로
        
    Returns:
        NewsAgentConfig 인스턴스
    """
    return get_config_manager(env_file).config


def validate_environment(env_file: Optional[str] = None) -> List[str]:
    """
    환경 설정 검증 편의 함수
    
    Args:
        env_file: 환경변수 파일 경로
        
    Returns:
        검증 오류 목록
    """
    return get_config_manager(env_file).validate_config()


def create_env_template(file_path: str = ".env.template") -> None:
    """
    환경변수 템플릿 생성 편의 함수
    
    Args:
        file_path: 템플릿 파일 경로
    """
    get_config_manager().export_env_template(file_path)


# 유틸리티 함수들
def ensure_directory(path: Union[str, Path]) -> Path:
    """
    디렉토리 존재 확인 및 생성
    
    Args:
        path: 디렉토리 경로
        
    Returns:
        Path 객체
    """
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_output_filename(
    prefix: str = "news_summary",
    timestamp: Optional[datetime] = None,
    extension: str = "md"
) -> str:
    """
    출력 파일명 생성
    
    Args:
        prefix: 파일명 접두사
        timestamp: 타임스탬프 (없으면 현재 시각)
        extension: 파일 확장자
        
    Returns:
        생성된 파일명
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    time_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}_{time_str}.{extension}"


def cleanup_old_files(
    directory: Union[str, Path],
    pattern: str = "*.md",
    keep_days: int = 30
) -> int:
    """
    오래된 파일 정리
    
    Args:
        directory: 대상 디렉토리
        pattern: 파일 패턴
        keep_days: 보관할 일수
        
    Returns:
        삭제된 파일 수
    """
    import time
    
    directory = Path(directory)
    if not directory.exists():
        return 0
    
    cutoff_time = time.time() - (keep_days * 24 * 60 * 60)
    deleted_count = 0
    
    for file_path in directory.glob(pattern):
        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
            try:
                file_path.unlink()
                deleted_count += 1
            except OSError:
                continue
    
    return deleted_count