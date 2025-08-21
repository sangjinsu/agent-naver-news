"""
설정 관리 모듈 단위 테스트

이 테스트는 설정 관리 시스템의 기능을 검증합니다.
환경변수 로딩, 검증, 업데이트 등의 기능을 테스트합니다.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from src.utils.config import (
    ConfigManager,
    NewsAgentConfig,
    ScrapingConfig,
    OpenAIConfig,
    OutputConfig,
    LoggingConfig,
    GraphConfig,
    get_config_manager,
    get_config,
    validate_environment,
    create_env_template,
    ensure_directory,
    get_output_filename,
    cleanup_old_files
)


class TestConfigDataClasses:
    """설정 데이터 클래스 테스트"""

    def test_scraping_config_defaults(self):
        """스크래핑 설정 기본값 테스트"""
        config = ScrapingConfig()
        
        assert "Mozilla" in config.user_agent
        assert config.request_delay == 1.0
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.max_articles_per_category == 15
        assert config.concurrent_requests == 3

    def test_openai_config_defaults(self):
        """OpenAI 설정 기본값 테스트"""
        config = OpenAIConfig()
        
        assert config.api_key == ""
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.3
        assert config.max_tokens == 1000
        assert config.max_retries == 3
        assert config.timeout == 60.0
        assert config.concurrent_requests == 2

    def test_output_config_defaults(self):
        """출력 설정 기본값 테스트"""
        config = OutputConfig()
        
        assert config.output_dir == "./output/reports"
        assert config.include_metadata == True
        assert config.include_stats == True
        assert config.save_file == True
        assert config.auto_cleanup_days == 30

    def test_logging_config_defaults(self):
        """로깅 설정 기본값 테스트"""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.file_path is None
        assert "%(asctime)s" in config.format
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.backup_count == 5

    def test_graph_config_defaults(self):
        """그래프 설정 기본값 테스트"""
        config = GraphConfig()
        
        assert config.checkpointer == "memory"
        assert config.enable_streaming == True
        assert config.debug == False
        assert config.thread_id_prefix == "news_thread"
        assert config.max_retries_scraping == 2
        assert config.max_retries_summarization == 1

    def test_news_agent_config_creation(self):
        """뉴스 에이전트 설정 생성 테스트"""
        config = NewsAgentConfig()
        
        assert isinstance(config.scraping, ScrapingConfig)
        assert isinstance(config.openai, OpenAIConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.graph, GraphConfig)
        assert config.version == "0.1.0"
        assert len(config.categories) == 6


class TestConfigManager:
    """ConfigManager 클래스 테스트"""

    def setup_method(self):
        """각 테스트 메서드 실행 전 설정"""
        # 임시 환경변수 파일 생성
        self.temp_dir = tempfile.mkdtemp()
        self.env_file = os.path.join(self.temp_dir, ".env.test")
        
        with open(self.env_file, 'w') as f:
            f.write("""
OPENAI_API_KEY=sk-test123456789
OPENAI_MODEL=gpt-4o
REQUEST_DELAY=2.0
OUTPUT_DIR=/tmp/test_output
LOG_LEVEL=DEBUG
""")

    def teardown_method(self):
        """각 테스트 메서드 실행 후 정리"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_config_manager_initialization(self):
        """설정 관리자 초기화 테스트"""
        manager = ConfigManager(env_file=self.env_file, auto_load=False)
        
        assert manager.env_file == self.env_file
        assert manager._config is None
        assert manager._validated == False

    def test_load_config_from_env_file(self):
        """환경변수 파일에서 설정 로드 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        config = manager.config
        
        assert config.openai.api_key == "sk-test123456"
        assert config.openai.model == "gpt-4o"
        assert config.scraping.request_delay == 2.0
        assert config.output.output_dir == "/tmp/test_output"
        assert config.logging.level == "DEBUG"

    def test_load_config_missing_env_file(self):
        """존재하지 않는 환경변수 파일 처리 테스트"""
        manager = ConfigManager(env_file="nonexistent.env")
        config = manager.config
        
        # 기본값이 사용되어야 함
        assert config.openai.model == "gpt-4o-mini"
        assert config.scraping.request_delay == 1.0

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-env123456',
        'OPENAI_TEMPERATURE': '0.7',
        'MAX_ARTICLES_PER_CATEGORY': '20'
    })
    def test_load_config_from_environment_variables(self):
        """환경변수에서 설정 로드 테스트"""
        manager = ConfigManager(env_file="nonexistent.env")
        config = manager.config
        
        assert config.openai.api_key == "sk-env123456"
        assert config.openai.temperature == 0.7
        assert config.scraping.max_articles_per_category == 20

    def test_validate_config_success(self):
        """설정 검증 성공 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        
        # 유효한 출력 디렉토리로 변경
        manager.config.output.output_dir = self.temp_dir
        
        errors = manager.validate_config()
        assert len(errors) == 0
        assert manager.is_valid() == True

    def test_validate_config_missing_api_key(self):
        """API 키 누락 검증 테스트"""
        manager = ConfigManager(env_file="nonexistent.env")
        manager.config.openai.api_key = ""
        
        errors = manager.validate_config()
        assert len(errors) > 0
        assert any("OPENAI_API_KEY" in error for error in errors)

    def test_validate_config_invalid_api_key_format(self):
        """잘못된 API 키 형식 검증 테스트"""
        manager = ConfigManager(env_file="nonexistent.env")
        manager.config.openai.api_key = "invalid-key"
        
        errors = manager.validate_config()
        assert len(errors) > 0
        assert any("형식이 올바르지 않습니다" in error for error in errors)

    def test_validate_config_invalid_model(self):
        """잘못된 모델 검증 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        manager.config.openai.model = "invalid-model"
        
        errors = manager.validate_config()
        assert len(errors) > 0
        assert any("지원되지 않는 모델" in error for error in errors)

    def test_validate_config_invalid_temperature(self):
        """잘못된 온도 값 검증 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        manager.config.openai.temperature = 3.0  # 범위 초과
        
        errors = manager.validate_config()
        assert len(errors) > 0
        assert any("temperature는 0.0-2.0 범위" in error for error in errors)

    def test_get_summary(self):
        """설정 요약 정보 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        summary = manager.get_summary()
        
        assert "version" in summary
        assert "openai_model" in summary
        assert "categories_count" in summary
        assert summary["categories_count"] == 6
        assert summary["openai_model"] == "gpt-4o"

    def test_update_setting(self):
        """런타임 설정 업데이트 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        
        # 설정 업데이트
        manager.update_setting("openai.temperature", 0.5)
        assert manager.config.openai.temperature == 0.5
        
        # 검증 상태 리셋 확인
        assert manager._validated == False

    def test_update_setting_invalid_path(self):
        """잘못된 설정 경로 업데이트 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        
        with pytest.raises(ValueError, match="section.key"):
            manager.update_setting("invalid", 0.5)
        
        with pytest.raises(ValueError, match="존재하지 않는 설정 섹션"):
            manager.update_setting("invalid.key", 0.5)
        
        with pytest.raises(ValueError, match="존재하지 않는 설정 키"):
            manager.update_setting("openai.invalid", 0.5)

    def test_export_env_template(self):
        """환경변수 템플릿 생성 테스트"""
        manager = ConfigManager(env_file=self.env_file)
        template_file = os.path.join(self.temp_dir, ".env.template")
        
        manager.export_env_template(template_file)
        
        assert os.path.exists(template_file)
        
        with open(template_file, 'r') as f:
            content = f.read()
            
        assert "OPENAI_API_KEY=" in content
        assert "OPENAI_MODEL=" in content
        assert "REQUEST_DELAY=" in content
        assert "OUTPUT_DIR=" in content


class TestGlobalConfigFunctions:
    """전역 설정 함수 테스트"""

    def test_get_config_manager_singleton(self):
        """설정 관리자 싱글톤 테스트"""
        # 전역 변수 초기화
        import src.utils.config
        src.utils.config._config_manager = None
        
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        assert manager1 is manager2

    def test_get_config_function(self):
        """설정 반환 함수 테스트"""
        config = get_config()
        assert isinstance(config, NewsAgentConfig)

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test123'})
    def test_validate_environment_success(self):
        """환경 검증 성공 테스트"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 임시 출력 디렉토리 설정
            with patch.dict(os.environ, {'OUTPUT_DIR': temp_dir}):
                errors = validate_environment()
                assert len(errors) == 0

    def test_validate_environment_failure(self):
        """환경 검증 실패 테스트"""
        with patch.dict(os.environ, {}, clear=True):
            errors = validate_environment()
            assert len(errors) > 0

    def test_create_env_template_function(self):
        """환경변수 템플릿 생성 함수 테스트"""
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = os.path.join(temp_dir, ".env.template")
            
            create_env_template(template_path)
            
            assert os.path.exists(template_path)
            
            with open(template_path, 'r') as f:
                content = f.read()
                
            assert "OPENAI_API_KEY=" in content


class TestUtilityFunctions:
    """유틸리티 함수 테스트"""

    def test_ensure_directory(self):
        """디렉토리 생성 보장 테스트"""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = os.path.join(temp_dir, "test", "nested", "directory")
            
            result = ensure_directory(new_dir)
            
            assert os.path.exists(new_dir)
            assert os.path.isdir(new_dir)
            assert result == Path(new_dir)

    def test_get_output_filename(self):
        """출력 파일명 생성 테스트"""
        from datetime import datetime
        
        # 기본 파일명
        filename = get_output_filename()
        assert filename.startswith("news_summary_")
        assert filename.endswith(".md")
        
        # 커스텀 파일명
        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        filename = get_output_filename(
            prefix="test",
            timestamp=timestamp,
            extension="txt"
        )
        assert filename == "test_2024-01-15_14-30-00.txt"

    def test_cleanup_old_files(self):
        """오래된 파일 정리 테스트"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 테스트 파일 생성
            import time
            
            # 최근 파일
            recent_file = os.path.join(temp_dir, "recent.md")
            with open(recent_file, 'w') as f:
                f.write("recent")
            
            # 오래된 파일 (임의로 과거 시간 설정)
            old_file = os.path.join(temp_dir, "old.md")
            with open(old_file, 'w') as f:
                f.write("old")
            
            # 파일 수정 시간을 과거로 설정
            old_time = time.time() - (40 * 24 * 60 * 60)  # 40일 전
            os.utime(old_file, (old_time, old_time))
            
            # 정리 실행 (30일 보관)
            deleted_count = cleanup_old_files(temp_dir, "*.md", 30)
            
            assert deleted_count == 1
            assert os.path.exists(recent_file)
            assert not os.path.exists(old_file)

    def test_cleanup_old_files_nonexistent_directory(self):
        """존재하지 않는 디렉토리 정리 테스트"""
        deleted_count = cleanup_old_files("/nonexistent/directory")
        assert deleted_count == 0


class TestConfigurationScenarios:
    """설정 시나리오 테스트"""

    def test_development_environment_config(self):
        """개발 환경 설정 테스트"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-dev123',
            'OPENAI_MODEL': 'gpt-3.5-turbo',
            'LOG_LEVEL': 'DEBUG',
            'GRAPH_DEBUG': 'true',
            'REQUEST_DELAY': '0.5'
        }):
            config = get_config()
            
            assert config.openai.model == "gpt-3.5-turbo"
            assert config.logging.level == "DEBUG"
            assert config.graph.debug == True
            assert config.scraping.request_delay == 0.5

    def test_production_environment_config(self):
        """프로덕션 환경 설정 테스트"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-prod123',
            'OPENAI_MODEL': 'gpt-4o',
            'LOG_LEVEL': 'WARNING',
            'GRAPH_DEBUG': 'false',
            'REQUEST_DELAY': '2.0',
            'GRAPH_CHECKPOINTER': 'sqlite'
        }):
            config = get_config()
            
            assert config.openai.model == "gpt-4o"
            assert config.logging.level == "WARNING"
            assert config.graph.debug == False
            assert config.scraping.request_delay == 2.0
            assert config.graph.checkpointer == "sqlite"

    def test_config_override_priority(self):
        """설정 오버라이드 우선순위 테스트"""
        # 환경변수 파일 생성
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENAI_MODEL=gpt-4o-mini\nREQUEST_DELAY=1.5\n")
            env_file = f.name
        
        try:
            # 환경변수가 파일 설정을 오버라이드해야 함
            with patch.dict(os.environ, {
                'OPENAI_MODEL': 'gpt-4o',
                'REQUEST_DELAY': '3.0'
            }):
                manager = ConfigManager(env_file=env_file)
                config = manager.config
                
                # 환경변수 값이 우선되어야 함
                assert config.openai.model == "gpt-4o"
                assert config.scraping.request_delay == 3.0
        finally:
            os.unlink(env_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])