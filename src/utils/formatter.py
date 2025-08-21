"""
마크다운 포맷터 및 Rich 기반 출력 유틸리티

이 모듈은 뉴스 요약 결과를 다양한 형식으로 포맷팅하고 
Rich 라이브러리를 사용한 아름다운 터미널 출력을 제공합니다.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich import box

from ..models.schemas import (
    CATEGORY_EMOJIS,
    NewsAgentState,
    get_category_emoji,
)


class NewsMarkdownFormatter:
    """
    뉴스 요약 마크다운 포맷터
    
    구조화되고 읽기 쉬운 마크다운 형식으로 뉴스 요약을 포맷팅합니다.
    """

    def __init__(self, include_metadata: bool = True, include_stats: bool = True):
        """
        포맷터 초기화
        
        Args:
            include_metadata: 메타데이터 포함 여부
            include_stats: 통계 정보 포함 여부
        """
        self.include_metadata = include_metadata
        self.include_stats = include_stats

    def format_header(self, timestamp: Optional[datetime] = None) -> str:
        """
        마크다운 헤더 생성
        
        Args:
            timestamp: 생성 시각 (없으면 현재 시각 사용)
            
        Returns:
            마크다운 헤더 텍스트
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        header = """# 📰 네이버 뉴스 헤드라인 요약

"""
        
        if self.include_metadata:
            header += f"""> **생성 시각**: {timestamp.strftime('%Y년 %m월 %d일 %H시 %M분')}  
> **데이터 출처**: 네이버 뉴스  
> **생성 방식**: AI 자동 요약  

---

"""
        
        return header

    def format_category_summary(self, summary_data: Dict) -> str:
        """
        카테고리별 요약 포맷팅
        
        Args:
            summary_data: 카테고리 요약 데이터
            
        Returns:
            포맷팅된 마크다운 텍스트
        """
        category = summary_data.get("category", "알 수 없음")
        summary_text = summary_data.get("summary", "")
        article_count = summary_data.get("article_count", 0)
        success = summary_data.get("success", False)
        
        # 카테고리 헤더
        emoji = get_category_emoji(category)
        formatted = f"## {emoji} {category}\n\n"
        
        if success and summary_text:
            # AI 요약이 성공한 경우
            formatted += summary_text + "\n\n"
        else:
            # 요약 실패 또는 데이터 없음
            if article_count > 0:
                formatted += f"⚠️ **알림**: 이 카테고리의 요약을 생성할 수 없었습니다.\n"
                formatted += f"- 수집된 기사: {article_count}개\n"
                formatted += "- 원인: AI 요약 생성 실패\n\n"
            else:
                formatted += f"📭 **알림**: 이 카테고리에서 수집된 기사가 없습니다.\n\n"
        
        return formatted

    def format_statistics(self, state: NewsAgentState) -> str:
        """
        통계 정보 포맷팅
        
        Args:
            state: 에이전트 상태
            
        Returns:
            통계 정보 마크다운
        """
        if not self.include_stats:
            return ""
        
        total_articles = state.get("total_articles_scraped", 0)
        scraping_duration = state.get("scraping_duration", 0)
        summarization_duration = state.get("summarization_duration", 0)
        formatting_duration = state.get("formatting_duration", 0)
        
        total_duration = scraping_duration + summarization_duration + formatting_duration
        
        summaries = state.get("summaries", [])
        successful_summaries = sum(1 for s in summaries if s.get("success", False))
        
        stats = f"""---

## 📊 생성 통계

### 처리 결과
- **총 수집 기사**: {total_articles:,}개
- **처리 카테고리**: {len(summaries)}개
- **성공한 요약**: {successful_summaries}/{len(summaries)}개
- **성공률**: {(successful_summaries/max(len(summaries), 1)*100):.1f}% (요약 기준)

### 처리 시간
- **뉴스 수집**: {scraping_duration:.2f}초
- **AI 요약**: {summarization_duration:.2f}초
- **포맷팅**: {formatting_duration:.2f}초
- **전체 시간**: {total_duration:.2f}초

### 성능 지표
- **기사당 처리 시간**: {(total_duration/max(total_articles, 1)):.3f}초
- **카테고리당 요약 시간**: {(summarization_duration/max(len(summaries), 1)):.2f}초

"""
        
        # 에러가 있으면 추가
        errors = state.get("errors", [])
        if errors:
            stats += "### ⚠️ 발생한 문제\n\n"
            for i, error in enumerate(errors, 1):
                stats += f"{i}. {error}\n"
            stats += "\n"
        
        return stats

    def format_footer(self) -> str:
        """
        마크다운 푸터 생성
        
        Returns:
            푸터 텍스트
        """
        return """---

## 📋 이용 안내

- **데이터 출처**: 네이버 뉴스 (https://news.naver.com)
- **요약 방식**: OpenAI GPT 모델을 활용한 AI 자동 요약
- **업데이트**: 실행 시점 기준 최신 헤드라인
- **문의사항**: 시스템 관련 문의는 개발팀에 연락

---

*이 리포트는 네이버 뉴스 헤드라인 요약 에이전트에 의해 자동 생성되었습니다.*  
*생성 시각: {}*
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def format_full_report(self, state: NewsAgentState) -> str:
        """
        전체 뉴스 리포트 포맷팅
        
        Args:
            state: 에이전트 상태
            
        Returns:
            완성된 마크다운 리포트
        """
        report = ""
        
        # 헤더
        timestamp_str = state.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
        except ValueError:
            timestamp = datetime.now()
        
        report += self.format_header(timestamp)
        
        # 카테고리별 요약
        summaries = state.get("summaries", [])
        if summaries:
            for summary_data in summaries:
                report += self.format_category_summary(summary_data)
        else:
            report += "## ⚠️ 알림\n\n요약된 뉴스가 없습니다.\n\n"
        
        # 통계 정보
        report += self.format_statistics(state)
        
        # 푸터
        report += self.format_footer()
        
        return report


class RichNewsDisplay:
    """
    Rich 라이브러리를 사용한 터미널 뉴스 출력
    
    색상, 테이블, 프로그레스 바 등을 활용한 시각적으로 풍부한 출력을 제공합니다.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Rich 디스플레이 초기화
        
        Args:
            console: Rich Console 인스턴스 (없으면 새로 생성)
        """
        self.console = console or Console()

    def show_startup_banner(self):
        """시작 배너 출력"""
        banner = """
[bold blue]📰 네이버 뉴스 헤드라인 요약 에이전트[/bold blue]

[dim]LangGraph 0.6+ 기반 AI 뉴스 수집 및 요약 시스템[/dim]
"""
        
        panel = Panel(
            banner,
            title="[bold green]News Agent[/bold green]",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()

    def show_progress(self, total_steps: int = 3) -> Progress:
        """
        진행 상황 표시를 위한 Progress 객체 생성
        
        Args:
            total_steps: 전체 단계 수
            
        Returns:
            Progress 객체
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        )
        
        return progress

    def show_summary_table(self, summaries: List[Dict]):
        """
        요약 결과를 테이블로 출력
        
        Args:
            summaries: 카테고리별 요약 결과
        """
        table = Table(
            title="📊 카테고리별 요약 결과",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("카테고리", style="cyan", no_wrap=True)
        table.add_column("상태", justify="center")
        table.add_column("기사 수", justify="right", style="green")
        table.add_column("요약 길이", justify="right", style="blue")
        
        for summary in summaries:
            category = summary.get("category", "알 수 없음")
            success = summary.get("success", False)
            article_count = summary.get("article_count", 0)
            summary_text = summary.get("summary", "")
            
            # 이모지 추가
            emoji = get_category_emoji(category)
            category_display = f"{emoji} {category}"
            
            # 상태 표시
            status = "✅ 성공" if success else "❌ 실패"
            status_style = "green" if success else "red"
            
            # 요약 길이
            summary_length = len(summary_text) if summary_text else 0
            
            table.add_row(
                category_display,
                Text(status, style=status_style),
                str(article_count),
                f"{summary_length:,}자"
            )
        
        self.console.print(table)
        self.console.print()

    def show_statistics(self, state: NewsAgentState):
        """
        실행 통계 출력
        
        Args:
            state: 에이전트 상태
        """
        total_articles = state.get("total_articles_scraped", 0)
        scraping_duration = state.get("scraping_duration", 0)
        summarization_duration = state.get("summarization_duration", 0)
        formatting_duration = state.get("formatting_duration", 0)
        
        total_duration = scraping_duration + summarization_duration + formatting_duration
        
        stats_text = f"""
[bold]처리 통계[/bold]

📰 수집 기사: [green]{total_articles:,}개[/green]
⏱️ 총 소요 시간: [blue]{total_duration:.2f}초[/blue]
🔄 스크래핑: [yellow]{scraping_duration:.2f}초[/yellow]
🤖 AI 요약: [magenta]{summarization_duration:.2f}초[/magenta]
📝 포맷팅: [cyan]{formatting_duration:.2f}초[/cyan]

📈 성능: [green]{(total_articles/max(total_duration, 0.001)):.1f}기사/초[/green]
"""
        
        panel = Panel(
            stats_text,
            title="[bold green]실행 결과[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(panel)

    def show_errors(self, errors: List[str]):
        """
        에러 목록 출력
        
        Args:
            errors: 에러 메시지 목록
        """
        if not errors:
            return
        
        error_text = "\n".join(f"• {error}" for error in errors)
        
        panel = Panel(
            error_text,
            title="[bold red]⚠️ 발생한 문제[/bold red]",
            border_style="red",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()

    def display_markdown_report(self, markdown_content: str):
        """
        마크다운 리포트 출력
        
        Args:
            markdown_content: 마크다운 텍스트
        """
        # 헤더 제거 (터미널에서는 간소화)
        lines = markdown_content.split('\n')
        filtered_lines = []
        skip_until_content = True
        
        for line in lines:
            if skip_until_content and line.startswith('## '):
                skip_until_content = False
            
            if not skip_until_content:
                filtered_lines.append(line)
        
        filtered_content = '\n'.join(filtered_lines)
        
        # 마크다운 렌더링
        md = Markdown(filtered_content)
        self.console.print(md)

    def show_completion_message(self, output_path: Optional[str] = None):
        """
        완료 메시지 출력
        
        Args:
            output_path: 저장된 파일 경로
        """
        message = "[bold green]✅ 뉴스 요약이 완료되었습니다![/bold green]"
        
        if output_path:
            message += f"\n\n📁 저장 위치: [cyan]{output_path}[/cyan]"
        
        panel = Panel(
            message,
            title="[bold green]완료[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(panel)


class NewsReportSaver:
    """
    뉴스 리포트 파일 저장 관리자
    """

    def __init__(self, output_dir: str = "./output/reports"):
        """
        저장 관리자 초기화
        
        Args:
            output_dir: 출력 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_markdown_report(
        self,
        content: str,
        filename: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        마크다운 리포트 저장
        
        Args:
            content: 마크다운 내용
            filename: 파일명 (없으면 자동 생성)
            timestamp: 타임스탬프 (없으면 현재 시각)
            
        Returns:
            저장된 파일 경로
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if filename is None:
            filename = f"{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}_news_summary.md"
        
        file_path = self.output_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)

    def get_latest_reports(self, limit: int = 5) -> List[str]:
        """
        최근 리포트 파일 목록 반환
        
        Args:
            limit: 반환할 파일 수
            
        Returns:
            파일 경로 목록 (최신순)
        """
        md_files = list(self.output_dir.glob("*.md"))
        md_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        return [str(f) for f in md_files[:limit]]

    def cleanup_old_reports(self, keep_days: int = 30):
        """
        오래된 리포트 파일 정리
        
        Args:
            keep_days: 보관할 일수
        """
        import time
        
        cutoff_time = time.time() - (keep_days * 24 * 60 * 60)
        
        for file_path in self.output_dir.glob("*.md"):
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()


# 편의 함수들
def format_news_report(state: NewsAgentState, **kwargs) -> str:
    """
    뉴스 리포트 포맷팅 편의 함수
    
    Args:
        state: 에이전트 상태
        **kwargs: 포맷터 옵션
        
    Returns:
        마크다운 리포트
    """
    formatter = NewsMarkdownFormatter(**kwargs)
    return formatter.format_full_report(state)


def display_news_report(
    state: NewsAgentState,
    save_file: bool = True,
    show_progress: bool = True,
    console: Optional[Console] = None
) -> Optional[str]:
    """
    뉴스 리포트 출력 및 저장 편의 함수
    
    Args:
        state: 에이전트 상태
        save_file: 파일 저장 여부
        show_progress: 진행 상황 표시 여부
        console: Rich Console 인스턴스
        
    Returns:
        저장된 파일 경로 (저장한 경우)
    """
    display = RichNewsDisplay(console)
    
    # 시작 배너
    display.show_startup_banner()
    
    # 요약 테이블
    summaries = state.get("summaries", [])
    if summaries:
        display.show_summary_table(summaries)
    
    # 통계 정보
    display.show_statistics(state)
    
    # 에러 표시
    errors = state.get("errors", [])
    if errors:
        display.show_errors(errors)
    
    # 마크다운 리포트 생성 및 출력
    formatter = NewsMarkdownFormatter()
    markdown_content = formatter.format_full_report(state)
    display.display_markdown_report(markdown_content)
    
    # 파일 저장
    saved_path = None
    if save_file:
        saver = NewsReportSaver()
        saved_path = saver.save_markdown_report(markdown_content)
        display.show_completion_message(saved_path)
    else:
        display.show_completion_message()
    
    return saved_path