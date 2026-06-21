"""
News, World Monitor, Morning Digest, and Deep Research Skill for JARVIS.
"""

import asyncio
import re
import xml.etree.ElementTree as ET
import webbrowser
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger


SEED_FEEDS = [
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://www.cnbc.com/id/100727362/device/rss/rss.html',
    'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://www.aljazeera.com/xml/rss/all.xml'
]

FINANCE_SEED_FEEDS = [
    'https://www.cnbc.com/id/10000664/device/rss/rss.html',       # CNBC Finance
    'https://feeds.bloomberg.com/markets/news.rss',                # Bloomberg Markets
    'https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best',  # Reuters
    'https://feeds.marketwatch.com/marketwatch/topstories/',       # MarketWatch
    'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',  # NYT Business
]


async def fetch_and_parse_feed(client: httpx.AsyncClient, url: str) -> List[Dict[str, Any]]:
    """Helper function to handle a single RSS feed request and parse its XML."""
    try:
        response = await client.get(url, headers={'User-Agent': 'Friday-AI/1.0'}, timeout=5.0)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        # Extract source name from URL
        source_name = url.split('.')[1].upper()
        
        feed_items = []
        # Get top 5 items per feed
        items = root.findall(".//item")[:5]
        for item in items:
            title = item.findtext("title")
            description = item.findtext("description")
            link = item.findtext("link")
            
            if description:
                description = re.sub('<[^<]+?>', '', description).strip()

            feed_items.append({
                "source": source_name,
                "title": title,
                "summary": description[:200] + "..." if description else "",
                "link": link
            })
        return feed_items
    except Exception as e:
        logger.debug(f"Feed error for {url}: {e}")
        return []


class NewsSkill(BaseSkill):
    """Enables JARVIS to fetch world news, open world monitors, compile morning digests, and conduct deep research."""

    def __init__(self, browser_service=None, automation_service=None, memory_service=None) -> None:
        self.browser = browser_service
        self.automation = automation_service
        self.memory = memory_service

    # ── Friday Features ──────────────────────────────────────────────────

    @skill_tool(
        name="get_world_news",
        description="Fetches the latest global headlines from major news outlets (BBC, CNBC, NYTimes, AlJazeera) in parallel.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    async def get_world_news(self) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            tasks = [fetch_and_parse_feed(client, url) for url in SEED_FEEDS]
            results_of_lists = await asyncio.gather(*tasks)
            all_articles = [item for sublist in results_of_lists for item in sublist]

        if not all_articles:
            return "The global news grid is unresponsive, sir. I'm unable to pull headlines."

        report = ["### GLOBAL NEWS BRIEFING (LIVE)\n"]
        for entry in all_articles[:12]:
            report.append(f"**[{entry['source']}]** {entry['title']}")
            report.append(f"{entry['summary']}")
            report.append(f"Link: {entry['link']}\n")

        return "\n".join(report)

    @skill_tool(
        name="get_world_finance_news",
        description="Fetches the latest finance and market headlines from major financial outlets (CNBC, Bloomberg, Reuters, MarketWatch) in parallel.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    async def get_world_finance_news(self) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            tasks = [fetch_and_parse_feed(client, url) for url in FINANCE_SEED_FEEDS]
            results_of_lists = await asyncio.gather(*tasks)
            all_articles = [item for sublist in results_of_lists for item in sublist]

        if not all_articles:
            return "The financial feeds are unresponsive right now, sir. I can't pull market headlines."

        report = ["### FINANCE BRIEFING (LIVE)\n"]
        for entry in all_articles[:12]:
            report.append(f"**[{entry['source']}]** {entry['title']}")
            report.append(f"{entry['summary']}")
            report.append(f"Link: {entry['link']}\n")

        return "\n".join(report)

    @skill_tool(
        name="open_world_monitor",
        description="Opens the World Monitor dashboard (worldmonitor.app) in the system's default web browser.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def open_world_monitor(self) -> str:
        url = "https://worldmonitor.app/"
        try:
            webbrowser.open(url)
            return "Displaying the World Monitor on your primary screen now, sir."
        except Exception as e:
            return f"I'm unable to initialize the visual monitor: {str(e)}"

    @skill_tool(
        name="open_finance_world_monitor",
        description="Opens the Finance World Monitor dashboard (finance.worldmonitor.app) in the system's default web browser.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def open_finance_world_monitor(self) -> str:
        url = "https://finance.worldmonitor.app/"
        try:
            webbrowser.open(url)
            return "Displaying the Finance World Monitor on your primary screen now, sir."
        except Exception as e:
            return f"I'm unable to initialize the finance monitor: {str(e)}"

    # ── OpenJarvis Features ──────────────────────────────────────────────

    @skill_tool(
        name="morning_digest",
        description="Generates a daily morning briefing digest summarizing weather, news, system resources, and calendar events.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    async def morning_digest(self) -> str:
        logger.info("Compiling daily morning digest briefing...")
        digest = ["# 🌅 MORNING BRIEFING & DIGEST\n"]
        
        # 1. Date and Greeting
        now = datetime.now()
        digest.append(f"Good morning! Today is {now.strftime('%A, %B %d, %Y')}. Here is your briefing.\n")

        # 2. Calendar (List upcoming events)
        digest.append("## 📅 CALENDAR EVENTS")
        try:
            # Dynamically look for list_calendar_events tool in registry or list calendar
            registry = self.automation.planner_agent.skills_registry if self.automation and hasattr(self.automation, 'planner_agent') else None
            if registry and "CommunicationSkill" in registry.skills:
                events = registry.skills["CommunicationSkill"].list_calendar_events()
                digest.append(events)
            else:
                digest.append("No active calendar events found for today.")
        except Exception as e:
            digest.append(f"Could not retrieve calendar events: {e}")
        digest.append("")

        # 3. System Stats
        digest.append("## 🖥️ SYSTEM STATUS")
        try:
            import psutil
            cpu = psutil.cpu_percent()
            vmem = psutil.virtual_memory()
            digest.append(f"- CPU Usage: {cpu}%")
            digest.append(f"- RAM Usage: {vmem.percent}% ({vmem.used / (1024**3):.1f} GB used / {vmem.total / (1024**3):.1f} GB total)")
        except Exception:
            digest.append("System monitoring metrics currently unavailable.")
        digest.append("")

        # 4. News Headlines
        digest.append("## 🌐 WORLD NEWS HEADLINES")
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
                tasks = [fetch_and_parse_feed(client, url) for url in SEED_FEEDS[:2]]
                results_of_lists = await asyncio.gather(*tasks)
                all_articles = [item for sublist in results_of_lists for item in sublist]
                if all_articles:
                    for entry in all_articles[:5]:
                        digest.append(f"- **[{entry['source']}]** {entry['title']}")
                else:
                    digest.append("Unable to connect to news feeds.")
        except Exception:
            digest.append("News feed retrieval timed out.")
        
        return "\n".join(digest)

    @skill_tool(
        name="deep_research",
        description="Performs multi-step, multi-hop web research on a specific topic, gathering info and generating a summary with citations.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research query or topic to investigate."}
            },
            "required": ["query"]
        }
    )
    async def deep_research(self, query: str) -> str:
        logger.info(f"Starting deep research on query: {query}")
        
        # Step 1: Initial search
        if not self.browser:
            return "Browser service is not initialized. Deep research is unavailable."
            
        search_results = await self.browser.search_web(query)
        
        # Step 2: Extract top links from search results using regex
        urls = re.findall(r'URL:\s*(https?://[^\s\)]+)', search_results)
        
        report = [
            f"# 🔬 DEEP RESEARCH REPORT: {query.upper()}",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "## 🔍 Primary Findings & Synthesized Summary",
        ]
        
        # Step 3: Fetch content from top 2 URLs to build deep context
        fetched_contents = []
        for url in urls[:2]:
            try:
                logger.info(f"Deep research: scraping {url}")
                async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
                    res = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                    if res.status_code == 200:
                        text = re.sub('<[^<]+?>', '', res.text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        fetched_contents.append((url, text[:1500]))
            except Exception as e:
                logger.debug(f"Scraping error for {url}: {e}")

        # Step 4: Compile report content
        if not fetched_contents:
            report.append("No deep web page details could be retrieved. Fallback to basic search index results:\n")
            report.append(search_results)
            return "\n".join(report)

        report.append(f"We analyzed search results and scraped key references to compile this summary on '{query}':\n")
        
        for i, (url, content) in enumerate(fetched_contents, 1):
            snippet = content[:500].replace('\n', ' ')
            report.append(f"### [Citation {i}] ({url})")
            report.append(f"... {snippet} ...\n")

        report.append("\n## 📋 References & Sources")
        for i, url in enumerate(urls[:5], 1):
            report.append(f"{i}. [{url.split('//')[1].split('/')[0]}]({url})")

        return "\n".join(report)
