"""
네이버 뉴스 헤드라인 요약 에이전트 메인 실행 스크립트

이 스크립트는 전체 뉴스 수집 및 요약 워크플로우를 실행합니다.
명령행 인터페이스와 강건한 에러 핸들링을 제공합니다.
"""

import argparse
import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

from .agents.graph import NewsAgent
from .models.schemas import DEFAULT_CATEGORIES, validate_category
from .utils.formatter import display_news_report


class NewsAgentError(Exception):
    """뉴스 에이전트 관련 예외"""
    pass


class ConfigurationError(NewsAgentError):
    """설정 관련 예외"""
    pass


class ValidationError(NewsAgentError):
    """입력 검증 예외"""
    pass


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    로깅 시스템 설정
    
    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        log_file: 로그 파일 경로 (없으면 콘솔만 출력)
    """
    # 로그 레벨 설정
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 로그 포맷 설정
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 핸들러 설정
    handlers = [RichHandler(console=Console(stderr=True), show_time=False)]
    
    if log_file:
        # 로그 파일 디렉토리 생성
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # 루트 로거 설정
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        handlers=handlers,
        force=True
    )
    
    # httpx 로그 레벨 조정 (너무 verbose함)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def validate_environment() -> None:
    """
    필수 환경변수 및 설정 검증
    
    Raises:
        ConfigurationError: 설정이 올바르지 않은 경우
    """
    # OpenAI API 키 확인
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ConfigurationError(
            "OPENAI_API_KEY 환경변수가 설정되지 않았습니다. "
            ".env 파일을 확인하거나 환경변수를 설정해주세요."
        )
    
    if not openai_key.startswith("sk-"):
        raise ConfigurationError(
            "OPENAI_API_KEY 형식이 올바르지 않습니다. "
            "'sk-'로 시작하는 유효한 OpenAI API 키를 사용해주세요."
        )
    
    # 모델 확인
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    valid_models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    if model not in valid_models:
        raise ConfigurationError(
            f"지원되지 않는 모델입니다: {model}. "
            f"지원 모델: {', '.join(valid_models)}"
        )
    
    # 출력 디렉토리 확인 및 생성
    output_dir = os.getenv("OUTPUT_DIR", "./output/reports")
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise ConfigurationError(f"출력 디렉토리 생성 실패: {output_dir} - {str(e)}")


def validate_categories(categories: List[str]) -> List[str]:
    """
    카테고리 목록 검증
    
    Args:
        categories: 검증할 카테고리 목록
        
    Returns:
        검증된 카테고리 목록
        
    Raises:
        ValidationError: 유효하지 않은 카테고리가 있는 경우
    """
    if not categories:
        return DEFAULT_CATEGORIES.copy()
    
    invalid_categories = [cat for cat in categories if not validate_category(cat)]
    if invalid_categories:
        raise ValidationError(
            f"지원되지 않는 카테고리: {', '.join(invalid_categories)}. "
            f"지원 카테고리: {', '.join(DEFAULT_CATEGORIES)}"
        )
    
    return categories


def parse_arguments() -> argparse.Namespace:
    """
    명령행 인수 파싱
    
    Returns:
        파싱된 인수
    """
    parser = argparse.ArgumentParser(
        description="네이버 뉴스 헤드라인 요약 에이전트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
사용 예시:
  %(prog)s                           # 모든 카테고리 요약
  %(prog)s --categories 정치 경제       # 특정 카테고리만 요약
  %(prog)s --no-save                 # 파일 저장하지 않고 터미널에만 출력
  %(prog)s --debug --log-file app.log # 디버그 모드로 로그 파일에 기록

지원 카테고리: {', '.join(DEFAULT_CATEGORIES)}
        """
    )
    
    # 카테고리 선택
    parser.add_argument(
        "--categories", "-c",
        nargs="+",
        choices=DEFAULT_CATEGORIES,
        help="요약할 뉴스 카테고리 (기본값: 전체)"
    )
    
    # 출력 옵션
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="파일로 저장하지 않고 터미널에만 출력"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        help="출력 디렉토리 경로 (기본값: ./output/reports)"
    )
    
    parser.add_argument(
        "--filename", "-f",
        help="출력 파일명 (기본값: 자동 생성)"
    )
    
    # 실행 옵션
    parser.add_argument(
        "--checkpointer",
        choices=["memory", "sqlite", "none"],
        default="memory",
        help="체크포인터 유형 (기본값: memory)"
    )
    
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="스트리밍 모드 비활성화"
    )
    
    parser.add_argument(
        "--thread-id",
        help="특정 스레드 ID 사용 (체크포인팅용)"
    )
    
    # 로깅 옵션
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="로그 레벨 (기본값: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        help="로그 파일 경로"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="디버그 모드 활성화 (--log-level DEBUG와 동일)"
    )
    
    # 설정 파일
    parser.add_argument(
        "--env-file",
        default=".env",
        help="환경변수 파일 경로 (기본값: .env)"
    )
    
    # 버전 정보
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="%(prog)s 0.1.0"
    )
    
    return parser.parse_args()


async def run_news_agent(
    categories: List[str],
    checkpointer: str = "memory",
    enable_streaming: bool = True,
    thread_id: Optional[str] = None,
    debug: bool = False
) -> dict:
    """
    뉴스 에이전트 실행
    
    Args:
        categories: 처리할 카테고리 목록
        checkpointer: 체크포인터 유형
        enable_streaming: 스트리밍 활성화 여부
        thread_id: 스레드 ID
        debug: 디버그 모드
        
    Returns:
        실행 결과 상태
        
    Raises:
        NewsAgentError: 실행 중 오류 발생 시
    """
    logger = logging.getLogger(__name__)
    logger.info(f"뉴스 에이전트 실행 시작: {len(categories)}개 카테고리")
    
    try:
        # 에이전트 생성
        if checkpointer == "none":
            checkpointer = None
        
        agent = NewsAgent(
            checkpointer=checkpointer,
            enable_streaming=enable_streaming,
            debug=debug
        )
        
        # 실행
        result = await agent.run(
            categories=categories,
            thread_id=thread_id
        )
        
        logger.info("뉴스 에이전트 실행 완료")
        return result
        
    except Exception as e:
        logger.error(f"뉴스 에이전트 실행 실패: {str(e)}")
        if debug:
            logger.debug(f"상세 오류:\n{traceback.format_exc()}")
        raise NewsAgentError(f"뉴스 에이전트 실행 실패: {str(e)}")


async def main_async() -> int:
    """
    비동기 메인 함수
    
    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    console = Console()
    
    try:
        # 명령행 인수 파싱
        args = parse_arguments()
        
        # 디버그 모드 처리
        if args.debug:
            args.log_level = "DEBUG"
        
        # 로깅 설정
        setup_logging(args.log_level, args.log_file)
        logger = logging.getLogger(__name__)
        
        # 환경변수 로드
        env_file = args.env_file
        if Path(env_file).exists():
            load_dotenv(env_file)
            logger.info(f"환경변수 파일 로드: {env_file}")
        else:
            logger.warning(f"환경변수 파일을 찾을 수 없습니다: {env_file}")
        
        # 출력 디렉토리 설정
        if args.output_dir:
            os.environ["OUTPUT_DIR"] = args.output_dir
        
        # 환경 검증
        validate_environment()
        logger.info("환경 설정 검증 완료")
        
        # 카테고리 검증
        categories = validate_categories(args.categories)
        logger.info(f"처리할 카테고리: {', '.join(categories)}")
        
        # 뉴스 에이전트 실행
        result = await run_news_agent(
            categories=categories,
            checkpointer=args.checkpointer,
            enable_streaming=not args.no_streaming,
            thread_id=args.thread_id,
            debug=args.debug
        )
        
        # 결과 출력 및 저장
        saved_path = display_news_report(
            state=result,
            save_file=not args.no_save,
            console=console
        )
        
        # 성공 메시지
        total_articles = result.get("total_articles_scraped", 0)
        logger.info(f"실행 완료: {total_articles}개 기사 처리")
        
        if saved_path:
            logger.info(f"리포트 저장됨: {saved_path}")
        
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자에 의해 중단되었습니다.[/yellow]")
        return 1
        
    except (ConfigurationError, ValidationError) as e:
        console.print(f"[red]설정 오류: {str(e)}[/red]")
        return 1
        
    except NewsAgentError as e:
        console.print(f"[red]실행 오류: {str(e)}[/red]")
        return 1
        
    except Exception as e:
        console.print(f"[red]예상하지 못한 오류: {str(e)}[/red]")
        if args.debug:
            console.print(f"[dim]상세 정보:\n{traceback.format_exc()}[/dim]")
        return 1


def main() -> int:
    """
    메인 진입점
    
    Returns:
        종료 코드
    """
    try:
        # Windows에서 asyncio 이벤트 루프 정책 설정
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # 비동기 메인 함수 실행
        return asyncio.run(main_async())
        
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        return 1
    except Exception as e:
        print(f"치명적 오류: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())