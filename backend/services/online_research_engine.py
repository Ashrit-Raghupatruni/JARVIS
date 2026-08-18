"""
JARVIS AI OS — Online Research & Live Web Extraction Engine.
============================================================
Performs real HTTP web searches, fetches source page HTML, extracts text content,
and synthesizes structured summaries with URLs and citations.
Fails closed with honest error reports if search or URL fetching fails.
"""

import json
import urllib.request
import urllib.parse
import re
from typing import Dict, Any, List, Optional
from loguru import logger


class OnlineResearchEngine:
    """Live Online Search & Page Content Extractor Engine."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def search_web(self, query: str, max_results: int = 4) -> Dict[str, Any]:
        """
        Perform live web search query and return top result snippets and source URLs.
        """
        logger.info("OnlineResearchEngine: Searching web for query: '{}'", query)
        q_enc = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={q_enc}"

        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Extract result snippets and URLs via regex
            results = []
            # Match DuckDuckGo HTML results: <a class="result__a" href="...">title</a> ... <a class="result__snippet">snippet</a>
            matches = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html)
            snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html)

            for idx, (href, raw_title) in enumerate(matches[:max_results]):
                # Clean HTML tags
                title = re.sub(r'<[^>]+>', '', raw_title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[idx]).strip() if idx < len(snippets) else ""
                
                # Unquote DDG redirect URL if present
                if "uddg=" in href:
                    parsed_url = urllib.parse.unquote(href.split("uddg=")[-1].split("&")[0])
                else:
                    parsed_url = href

                if title and parsed_url.startswith("http"):
                    results.append({
                        "title": title,
                        "url": parsed_url,
                        "snippet": snippet
                    })

            if not results:
                return {
                    "status": "warning",
                    "query": query,
                    "results": [],
                    "message": f"No web search results returned for '{query}'."
                }

            logger.info("OnlineResearchEngine: Retrieved {} live web result(s).", len(results))
            return {
                "status": "success",
                "query": query,
                "count": len(results),
                "results": results
            }

        except Exception as e:
            logger.error("OnlineResearchEngine web search error: {}", e)
            return {
                "status": "error",
                "query": query,
                "error": str(e),
                "message": f"Web search failed: {e}"
            }

    def extract_url_content(self, target_url: str) -> Dict[str, Any]:
        """
        Fetch HTML page content from a target URL, extract clean text, and return summary data.
        """
        logger.info("OnlineResearchEngine: Extracting page content from URL: '{}'", target_url)
        try:
            req = urllib.request.Request(target_url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            page_title = title_match.group(1).strip() if title_match else target_url

            # Remove scripts, styles, and extra whitespace
            clean_text = re.sub(r'<(script|style).*?>.*?</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
            clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
            clean_text = ' '.join(clean_text.split())

            # Truncate text content for LLM context window
            text_sample = clean_text[:2000]

            return {
                "status": "success",
                "url": target_url,
                "title": page_title,
                "content_sample": text_sample,
                "char_count": len(clean_text)
            }

        except Exception as e:
            logger.error("OnlineResearchEngine URL extraction error: {}", e)
            return {
                "status": "error",
                "url": target_url,
                "error": str(e),
                "message": f"Failed to extract URL content: {e}"
            }


# Global Singleton Research Engine
online_research_engine = OnlineResearchEngine()
