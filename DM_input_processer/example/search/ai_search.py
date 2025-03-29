from typing import List, Dict, Optional, Any, Union
import asyncio
from dataclasses import dataclass
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from .search import UnifiedSearcher, SearchResult
from ..config import config
from ..scraper import WebScraper, ScrapedContent

@dataclass
class AISearchResult:
    """Container for AI-enhanced search results."""
    query: str
    summary: str
    sources: List[Dict[str, Any]]
    timestamp: datetime = datetime.now()
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        timestamp_str = self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        md = [
            f"# Search Results: {self.query}\n",
            f"*Generated on: {timestamp_str}*\n",
            f"## Summary\n{self.summary}\n",
            "## Sources\n"
        ]
        for i, source in enumerate(self.sources, 1):
            title = source.get('title', 'Untitled')
            url = source.get('url', '')
            snippet = source.get('snippet', '')
            source_type = source.get('source', 'Unknown')
            md.append(f"### {i}. {title}")
            if url:
                md.append(f"**URL:** {url}")
            if source_type:
                md.append(f"**Source:** {source_type}")
            if snippet:
                md.append(f"**Snippet:** {snippet}")
            md.append("")
        return "\n".join(md)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "query": self.query,
            "summary": self.summary,
            "sources": self.sources,
            "timestamp": self.timestamp.isoformat()
        }

class AISearcher:
    """
    AI-powered search functionality.
    Combines search results with AI analysis for any type of query.
    Enhanced with scraping capability for deeper insights.
    """
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        searcher: Optional[UnifiedSearcher] = None,
        scraper: Optional[WebScraper] = None,
        max_results: int = 10,
        max_pages_to_scrape: int = 3
    ):
        api_base = config.get("api", "base_url")
        api_key = config.get("api", "api_key")
        model = config.get("api", "model")
        self.llm = llm or ChatOpenAI(
            base_url=api_base,
            api_key=api_key,
            model=model,
            temperature=0.4,
            max_tokens=4096
        )
        self.searcher = searcher or UnifiedSearcher(max_results=max_results)
        self.scraper = scraper or WebScraper()
        self.max_results = max_results
        self.max_pages_to_scrape = max_pages_to_scrape
    
    async def search(
        self, 
        query: str,
        engines: Optional[List[str]] = None,
        detailed: bool = False,
        enable_scraping: bool = True
    ) -> AISearchResult:
        """
        Perform AI-enhanced search with content scraping for deeper insights.
        
        Args:
            query: Search query (can be about any topic)
            engines: List of search engines to use
            detailed: Whether to generate a detailed analysis
            enable_scraping: Whether to scrape content from top results
            
        Returns:
            AISearchResult object
        """
        timestamp = datetime.now()
        current_datetime = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        search_results = await self.searcher.search(query, engines)
        
        # Build content text with date information if available
        content_text = ""
        sources = []
        urls_to_scrape = []
        
        # First pass - process all search results and identify URLs to scrape
        for result in search_results:
            if isinstance(result, SearchResult):
                date = getattr(result, 'date', 'N/A')
                content_text += (
                    f"\nSource: {result.source}\n"
                    f"Title: {result.title}\n"
                    f"URL: {result.url}\n"
                    f"Date: {date}\n"
                    f"Snippet: {result.snippet}\n"
                )
                sources.append(result.to_dict())
                
                if enable_scraping and len(urls_to_scrape) < self.max_pages_to_scrape:
                    urls_to_scrape.append(result.url)
                    
            elif isinstance(result, dict):
                date = result.get('date', 'N/A')
                content_text += (
                    f"\nSource: {result.get('source', 'Unknown')}\n"
                    f"Title: {result.get('title', 'Untitled')}\n"
                    f"URL: {result.get('url', '')}\n"
                    f"Date: {date}\n"
                    f"Snippet: {result.get('snippet', '')}\n"
                )
                sources.append(result)
                
                if enable_scraping and result.get('url') and len(urls_to_scrape) < self.max_pages_to_scrape:
                    urls_to_scrape.append(result.get('url'))
        
        # If scraping is enabled, get deeper content from the top results
        if enable_scraping and urls_to_scrape:
            print(f"Scraping {len(urls_to_scrape)} pages for deeper insights...")
            scraped_results = await self.scraper.scrape_urls(urls_to_scrape, dynamic=True)
            
            # Process scraped content
            for scraped in scraped_results:
                if scraped.is_successful():
                    # Extract main content
                    main_content = await self.scraper.extract_main_content(scraped)
                    
                    # Add a separator between search results and scraped content
                    content_text += "\n" + "-" * 40 + "\n"
                    content_text += f"SCRAPED CONTENT FROM: {scraped.url}\n"
                    content_text += f"TITLE: {scraped.title}\n\n"
                    
                    # Add a preview of the main content (up to 1500 chars to avoid overloading)
                    content_preview = main_content[:1500]
                    if len(main_content) > 1500:
                        content_preview += "...(content truncated)..."
                    
                    content_text += content_preview + "\n"
        
        # --- Multi-stage Prompting Implementation for Refined LLM Output ---
        individual_summaries = []
        # Stage 1: Summarize each search result individually.
        for result in search_results:
            if isinstance(result, SearchResult):
                result_text = (
                    f"Source: {result.source}\n"
                    f"Title: {result.title}\n"
                    f"URL: {result.url}\n"
                    f"Snippet: {result.snippet}"
                )
            else:
                result_text = (
                    f"Source: {result.get('source', 'Unknown')}\n"
                    f"Title: {result.get('title', 'Untitled')}\n"
                    f"URL: {result.get('url', '')}\n"
                    f"Snippet: {result.get('snippet', '')}"
                )
            
            stage1_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a summarization engine. Summarize the following search result in a concise manner."),
                ("user", result_text)
            ])
            summary_output = await (stage1_prompt | self.llm).ainvoke({})
            individual_summaries.append(summary_output.content)
        
        # Stage 2: Combine individual summaries into a coherent narrative.
        combined_text = "\n".join(individual_summaries)
        stage2_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI that creates coherent narratives from multiple summaries."),
            ("user", f"Combine the following summaries into a coherent narrative:\n{combined_text}")
        ])
        combined_summary = await (stage2_prompt | self.llm).ainvoke({})
        
        # Stage 3: Refine the output with structured markdown formatting and contextual guidelines.
        stage3_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI that refines narratives. Please output your answer in a structured markdown format with clear sections: Key Findings, Address any conflicting information and note if any data is based on recent search results."),
            ("user", f"Refine the following narrative for tone, detail, and accuracy:\n{combined_summary.content}")
        ])
        final_output = await (stage3_prompt | self.llm).ainvoke({})
        
        return AISearchResult(
            query=query,
            summary=final_output.content,
            sources=sources,
            timestamp=timestamp
        )
    
    def search_sync(
        self, 
        query: str,
        engines: Optional[List[str]] = None,
        detailed: bool = False,
        enable_scraping: bool = True
    ) -> AISearchResult:
        """Synchronous version of search method."""
        return asyncio.run(self.search(query, engines, detailed, enable_scraping))
