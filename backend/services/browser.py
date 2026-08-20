"""
Browser automation service for JARVIS.

Provides web browsing capabilities using Playwright: opening URLs,
searching the web, interacting with page elements, and extracting content.
"""

import asyncio
from typing import Optional

from loguru import logger
from PIL import Image
import io


class BrowserService:
    """Service for browser automation using Playwright."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._started = False

    async def start(self) -> None:
        """Initialize the Playwright browser instance."""
        if self._started:
            logger.debug("Browser already started")
            return

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()
            self._started = True
            logger.info("Browser service started (Chromium)")
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise RuntimeError(
                f"Browser startup failed: {e}. Run 'playwright install chromium' first."
            )

    async def stop(self) -> None:
        """Shut down the browser and Playwright."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            self._started = False
            logger.info("Browser service stopped")
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")

    async def _ensure_started(self) -> None:
        """Ensure the browser is running before performing actions."""
        if not self._started or not self._page:
            await self.start()

    async def open_url(self, url: str) -> str:
        """
        Navigate to a URL.

        Args:
            url: The URL to open. If no scheme, adds https://.

        Returns:
            Status message.
        """
        await self._ensure_started()
        try:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await self._page.title()
            logger.info(f"Navigated to: {url} — Title: {title}")
            return f"Opened {url} — Page title: '{title}'"
        except Exception as e:
            logger.error(f"Failed to open URL '{url}': {e}")
            return f"Failed to open {url}: {str(e)}"

    async def search_web(self, query: str) -> str:
        """
        Search the web using Google, falling back to DuckDuckGo if Playwright fails.

        Args:
            query: Search query string.

        Returns:
            Search results summary.
        """
        try:
            await self._ensure_started()
            search_url = f"https://www.google.com/search?q={query}"
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

            # Wait for search results to load
            await self._page.wait_for_selector("div#search", timeout=5000)

            # Extract top search results
            results = await self._page.evaluate("""
                () => {
                    const items = document.querySelectorAll('div#search .g');
                    const results = [];
                    for (let i = 0; i < Math.min(items.length, 5); i++) {
                        const titleEl = items[i].querySelector('h3');
                        const linkEl = items[i].querySelector('a');
                        const snippetEl = items[i].querySelector('.VwiC3b, .IsZvec');
                        if (titleEl && linkEl) {
                            results.push({
                                title: titleEl.textContent || '',
                                url: linkEl.href || '',
                                snippet: snippetEl ? snippetEl.textContent : ''
                            });
                        }
                    }
                    return results;
                }
            """)

            if results:
                summary_lines = [f"Search results for '{query}':"]
                for i, r in enumerate(results, 1):
                    summary_lines.append(f"{i}. {r['title']}")
                    if r.get("snippet"):
                        summary_lines.append(f"   {r['snippet'][:150]}")
                    summary_lines.append(f"   URL: {r['url']}")
                summary = "\n".join(summary_lines)
                logger.info(f"Web search completed: {len(results)} results for '{query}'")
                return summary
        except Exception as e:
            logger.warning(f"Google search via Playwright failed: {e}. Falling back to DuckDuckGo HTML search...")

        # Fallback using DuckDuckGo HTML search (lightweight HTTP request)
        try:
            import urllib.request
            import urllib.parse
            import re

            url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )
            
            def fetch_ddg():
                with urllib.request.urlopen(req, timeout=8) as response:
                    return response.read().decode("utf-8")
                    
            html = await asyncio.to_thread(fetch_ddg)
            
            results = []
            blocks = re.findall(r'<div class="result__body">.*?</div>\s*</div>', html, re.DOTALL)
            for block in blocks[:5]:
                title_match = re.search(r'<a class="result__url"[^>]*>(.*?)</a>', block, re.DOTALL)
                snippet_match = re.search(r'<a class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)
                href_match = re.search(r'href="([^"]+)"', block)
                if title_match and href_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
                    href = href_match.group(1)
                    if "uddg=" in href:
                        href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet
                    })
            
            if results:
                summary_lines = [f"Search results for '{query}' (via DuckDuckGo fallback):"]
                for i, r in enumerate(results, 1):
                    summary_lines.append(f"{i}. {r['title']}")
                    if r.get("snippet"):
                        summary_lines.append(f"   {r['snippet'][:150]}")
                    summary_lines.append(f"   URL: {r['url']}")
                summary = "\n".join(summary_lines)
                logger.info(f"DuckDuckGo fallback search completed: {len(results)} results for '{query}'")
                return summary
        except Exception as ex:
            logger.error(f"DuckDuckGo fallback search failed: {ex}")
            
        return f"Search failed. Google Playwright search and DuckDuckGo fallback search both encountered errors."

    async def get_page_content(self) -> str:
        """
        Extract the main text content of the current page.

        Returns:
            Page text content (truncated to 3000 chars).
        """
        await self._ensure_started()
        try:
            content = await self._page.evaluate("""
                () => {
                    // Try to get main content first
                    const main = document.querySelector('main, article, [role="main"]');
                    const target = main || document.body;
                    return target.innerText || target.textContent || '';
                }
            """)
            content = content.strip()
            if len(content) > 3000:
                content = content[:3000] + "\n... [truncated]"

            title = await self._page.title()
            url = self._page.url
            logger.debug(f"Extracted {len(content)} chars from {url}")
            return f"Page: {title}\nURL: {url}\n\nContent:\n{content}"
        except Exception as e:
            logger.error(f"Failed to extract page content: {e}")
            return f"Failed to extract content: {str(e)}"

    async def click_element(self, selector: str) -> str:
        """
        Click an element on the page.

        Args:
            selector: CSS selector or text to locate the element.

        Returns:
            Status message.
        """
        await self._ensure_started()
        try:
            # Try CSS selector first
            try:
                await self._page.click(selector, timeout=5000)
                logger.info(f"Clicked element: {selector}")
                return f"Clicked element matching '{selector}'"
            except Exception:
                pass

            # Try text-based matching
            element = self._page.get_by_text(selector, exact=False).first
            await element.click(timeout=5000)
            logger.info(f"Clicked element by text: {selector}")
            return f"Clicked element with text '{selector}'"
        except Exception as e:
            logger.error(f"Failed to click '{selector}': {e}")
            return f"Could not find or click element '{selector}': {str(e)}"

    async def fill_input(self, selector: str, value: str) -> str:
        """
        Fill an input field on the page.

        Args:
            selector: CSS selector or label text for the input.
            value: Value to type into the field.

        Returns:
            Status message.
        """
        await self._ensure_started()
        try:
            # Try CSS selector first
            try:
                await self._page.fill(selector, value, timeout=5000)
                logger.info(f"Filled input '{selector}' with value")
                return f"Filled input '{selector}' with '{value[:50]}...'" if len(value) > 50 else f"Filled input '{selector}' with '{value}'"
            except Exception:
                pass

            # Try label-based matching
            element = self._page.get_by_label(selector).first
            await element.fill(value, timeout=5000)
            return f"Filled input labeled '{selector}'"
        except Exception as e:
            logger.error(f"Failed to fill input '{selector}': {e}")
            return f"Could not fill input '{selector}': {str(e)}"

    async def navigate(self, action: str) -> str:
        """
        Navigate the browser (back, forward, refresh).

        Args:
            action: Navigation action — 'back', 'forward', or 'refresh'.

        Returns:
            Status message.
        """
        await self._ensure_started()
        try:
            action = action.lower().strip()
            if action == "back":
                await self._page.go_back(timeout=10000)
            elif action == "forward":
                await self._page.go_forward(timeout=10000)
            elif action in ("refresh", "reload"):
                await self._page.reload(timeout=10000)
            else:
                return f"Unknown navigation action: '{action}'. Use 'back', 'forward', or 'refresh'."

            title = await self._page.title()
            logger.info(f"Browser navigated: {action} — Title: {title}")
            return f"Navigated {action} — Now on: '{title}'"
        except Exception as e:
            logger.error(f"Navigation '{action}' failed: {e}")
            return f"Navigation failed: {str(e)}"

    async def take_page_screenshot(self) -> Optional[Image.Image]:
        """Take a screenshot of the current browser page."""
        await self._ensure_started()
        try:
            screenshot_bytes = await self._page.screenshot(type="png", full_page=False)
            image = Image.open(io.BytesIO(screenshot_bytes))
            logger.debug(f"Browser screenshot captured: {image.size}")
            return image
        except Exception as e:
            logger.error(f"Browser screenshot failed: {e}")
            return None

    async def get_current_url(self) -> str:
        """Get the current page URL."""
        if self._page:
            return self._page.url
        return ""

    async def get_current_title(self) -> str:
        """Get the current page title."""
        if self._page:
            return await self._page.title()
        return ""

    async def play_music(self, query: str) -> str:
        """Search YouTube for the query, find the first video, and open it in the default browser."""
        import urllib.parse
        import webbrowser

        logger.info(f"Requested to play music: {query}")
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        try:
            await self._ensure_started()
            page = await self._context.new_page()
            await page.goto(search_url, wait_until="domcontentloaded", timeout=12000)
            
            await page.wait_for_selector("a#video-title", timeout=6000)
            video_url = await page.evaluate("""
                () => {
                    const linkEl = document.querySelector('a#video-title');
                    return linkEl ? linkEl.href : null;
                }
            """)
            await page.close()

            if video_url:
                logger.info(f"Opening YouTube video in default browser: {video_url}")
                webbrowser.open(video_url)
                return f"Playing '{query}' on YouTube: {video_url}"
        except Exception as e:
            logger.warning(f"Failed to extract direct YouTube video link headlessly: {e}. Opening search results page directly.")

        try:
            webbrowser.open(search_url)
            return f"Opened YouTube search results for '{query}' in your default browser."
        except Exception as e:
            logger.error(f"Failed to open YouTube search URL: {e}")
            return f"Error trying to play music: {e}"

    async def summarize_current_page(self) -> str:
        """Extract main body text and return clean summary payload."""
        await self._ensure_started()
        try:
            content = await self.extract_page_content()
            title = await self._page.title()
            url = self._page.url
            clean_text = content[:2000] if len(content) > 2000 else content
            return f"Page Title: '{title}' ({url})\nExcerpt:\n{clean_text}"
        except Exception as e:
            logger.error(f"Page summarization failed: {e}")
            return f"Error extracting page text: {e}"

    async def deep_research(self, topic: str, max_pages: int = 3) -> str:
        """Perform autonomous deep research across multiple web pages."""
        await self._ensure_started()
        logger.info("Starting deep research on topic: '{}' (pages={})", topic, max_pages)
        results = [f"=== DEEP RESEARCH REPORT: {topic.upper()} ==="]
        
        try:
            search_summary = await self.search_web(topic)
            results.append(f"\n--- Search Summary ---\n{search_summary[:1000]}")
            
            links = await self._page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href^="http"]'))
                    .map(a => a.href)
                    .filter(h => !h.includes('google.com') && !h.includes('youtube.com'))
                    .slice(0, 3)
            """)
            
            for i, link in enumerate(links[:max_pages]):
                try:
                    await self._page.goto(link, wait_until="domcontentloaded", timeout=10000)
                    title = await self._page.title()
                    text = await self.extract_page_content()
                    results.append(f"\n--- Page {i+1}: {title} ({link}) ---\n{text[:800]}")
                except Exception as p_err:
                    logger.warning(f"Could not load research page {link}: {p_err}")

            return "\n".join(results)
        except Exception as e:
            logger.error(f"Deep research failed for '{topic}': {e}")
            return f"Deep research failed: {e}"

    async def perceive_page_state(self) -> dict:
        """
        Perceive current page structure: title, URL, and interactive elements.
        Used by the Autonomous Web Agent perceive-decide-act-observe loop.
        """
        if not self._page:
            return {
                "url": "about:blank",
                "title": "No Active Page",
                "interactive_elements": [],
                "interactive_elements_count": 0
            }

        try:
            # Inject lightweight element visual indexing script
            elements_data = await self._page.evaluate("""
                () => {
                    const selectors = 'a, button, input, select, textarea, [role="button"], [role="link"]';
                    const nodes = Array.from(document.querySelectorAll(selectors));
                    return nodes.slice(0, 50).map((el, index) => {
                        const rect = el.getBoundingClientRect();
                        return {
                            index: index + 1,
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.value || el.placeholder || el.ariaLabel || '').trim().substring(0, 50),
                            visible: rect.width > 0 && rect.height > 0,
                            bbox: [Math.round(rect.left), Math.round(rect.top), Math.round(rect.width), Math.round(rect.height)]
                        };
                    }).filter(e => e.visible && e.text.length > 0);
                }
            """)

            title = await self._page.title()
            url = self._page.url

            return {
                "url": url,
                "title": title,
                "interactive_elements": elements_data,
                "interactive_elements_count": len(elements_data)
            }
        except Exception as e:
            logger.error(f"Failed to perceive page state: {e}")
            return {
                "url": self._page.url if self._page else "",
                "title": "Error",
                "interactive_elements": [],
                "interactive_elements_count": 0,
                "error": str(e)
            }

    async def run_browser_agent(self, task: str, max_steps: int = 5) -> str:
        """
        Autonomous Web Agent Loop: Perceive -> Decide -> Act -> Observe.
        Runs a multi-step natural language browser navigation task using LLM-driven decision making & native Playwright actions.
        """
        if not self._page or not self._started:
            await self.start()

        logger.info(f"🌐 Starting Autonomous Web Agent Loop for task: '{task}'")
        action_log = [f"Task: {task}"]

        # Retrieve LLM service instance with robust fallback
        llm_service = None
        try:
            from backend.services.manager import ServiceManager
            llm_service = ServiceManager.get_instance("llm_service")
            if not llm_service:
                from backend.services.llm import LLMService
                llm_service = LLMService()
        except Exception:
            pass

        for step in range(1, max_steps + 1):
            # 1. PERCEIVE
            perception = await self.perceive_page_state()
            current_url = perception.get("url", "")
            current_title = perception.get("title", "")
            elements = perception.get("interactive_elements", [])

            # Format elements list for LLM decision context
            elements_str_list = []
            for idx, el in enumerate(elements[:30], 1):
                elements_str_list.append(f"[{idx}] <{el.get('tag')}> '{el.get('text')}'")
            elements_formatted = "\n".join(elements_str_list) if elements_str_list else "No interactive elements detected."

            page_text = await self.get_page_content()
            text_excerpt = page_text[:1200] if page_text else ""

            action_log.append(f"\nStep {step}: On '{current_title}' ({current_url})")

            # 2. DECIDE (LLM-driven)
            decision = None
            if llm_service and hasattr(llm_service, "simple_completion"):
                prompt = f"""You are the Browser Autonomous Agent for JARVIS. Your goal is to fulfill the user's task on the web.

USER TASK: "{task}"

CURRENT STATE:
- URL: {current_url}
- Page Title: {current_title}

INTERACTIVE ELEMENTS:
{elements_formatted}

PAGE TEXT EXCERPT:
{text_excerpt[:800]}

PREVIOUS STEPS:
{chr(10).join(action_log[-4:])}

Respond strictly in valid JSON format with your next action:
{{
    "thought": "Reasoning about current state and what to do next to progress toward the user task",
    "action": "navigate" | "click" | "fill" | "extract" | "finish",
    "element_index": 1,
    "text": "text to type if action is fill, OR URL if action is navigate",
    "answer": "Final comprehensive answer if action is finish"
}}
"""
                try:
                    res_raw = await llm_service.simple_completion(prompt)
                    import json, re
                    json_match = re.search(r"\{.*\}", res_raw, re.DOTALL)
                    if json_match:
                        decision = json.loads(json_match.group(0))
                except Exception as llm_err:
                    logger.debug(f"LLM browser decision parsing failed: {llm_err}")

            # Fallback heuristic decision if LLM unavailable or failed to parse
            if not decision:
                lower_task = task.lower()
                if step == 1 and current_url in ("about:blank", "", "https://www.google.com", "chrome://newtab"):
                    query = task.replace("search for", "").replace("search", "").strip()
                    decision = {
                        "action": "navigate",
                        "text": f"https://en.wikipedia.org/wiki/Special:Search?search={query}",
                        "thought": f"Navigating to search for '{query}'"
                    }
                elif any(kw in lower_task for kw in ["founding year", "history", "details", "extract", "tell me"]):
                    decision = {
                        "action": "extract",
                        "thought": "Extracting information from page text to answer user task"
                    }
                elif elements:
                    decision = {
                        "action": "click",
                        "element_index": 1,
                        "thought": "Clicking primary interactive element"
                    }
                else:
                    decision = {
                        "action": "finish",
                        "answer": text_excerpt[:1000],
                        "thought": "Task completion threshold reached"
                    }

            action_type = str(decision.get("action", "finish")).lower().strip()
            thought = decision.get("thought", "")
            action_log.append(f"Thought: {thought}")

            # 3. ACT (Real Playwright execution)
            if action_type in ("navigate", "goto"):
                target_url = str(decision.get("text", "")).strip()
                if not target_url.startswith("http"):
                    target_url = f"https://www.google.com/search?q={target_url}"
                await self.open_url(target_url)
                action_log.append(f"Action: Navigated to '{target_url}'")

            elif action_type == "click":
                elem_idx = int(decision.get("element_index", 1)) - 1
                if 0 <= elem_idx < len(elements):
                    target_el = elements[elem_idx]
                    bbox = target_el.get("bbox")
                    if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
                        click_x = bbox[0] + (bbox[2] / 2)
                        click_y = bbox[1] + (bbox[3] / 2)
                        await self._page.mouse.click(click_x, click_y)
                    else:
                        tag_name = target_el.get("tag", "button")
                        el_text = target_el.get("text", "")
                        try:
                            await self._page.click(f"{tag_name}:has-text('{el_text}')")
                        except Exception:
                            await self._page.mouse.click(100, 100)
                    action_log.append(f"Action: Clicked element [{elem_idx+1}] <{target_el.get('tag')}> '{target_el.get('text')}'")
                else:
                    action_log.append(f"Action: Element index {elem_idx+1} out of bounds")

            elif action_type in ("fill", "type"):
                elem_idx = int(decision.get("element_index", 1)) - 1
                fill_text = str(decision.get("text", ""))
                if 0 <= elem_idx < len(elements):
                    target_el = elements[elem_idx]
                    tag_name = target_el.get("tag", "input")
                    el_text = target_el.get("text", "")
                    try:
                        await self._page.fill(f"{tag_name}:has-text('{el_text}')", fill_text)
                    except Exception:
                        await self._page.keyboard.type(fill_text)
                    action_log.append(f"Action: Typed '{fill_text}' into element [{elem_idx+1}] <{target_el.get('tag')}>")
                else:
                    await self._page.keyboard.type(fill_text)
                    action_log.append(f"Action: Typed '{fill_text}' via keyboard")

            elif action_type == "extract":
                full_text = await self.get_page_content()
                action_log.append(f"Action: Extracted page content ({len(full_text)} chars)")
                summary = full_text[:1500] if full_text else "No content extracted."
                action_log.append(f"\n✓ Task Completed: {summary}")
                return "\n".join(action_log)

            elif action_type == "finish":
                ans = decision.get("answer", text_excerpt[:1500])
                action_log.append(f"\n✓ Task Completed: {ans}")
                return "\n".join(action_log)

            # 4. OBSERVE
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            await asyncio.sleep(1.0)

        summary_out = "\n".join(action_log)
        return summary_out

    @property
    def is_started(self) -> bool:
        return self._started
