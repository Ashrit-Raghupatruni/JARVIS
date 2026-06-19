"""
Screen analysis service for JARVIS.

Provides screenshot capture, OCR text extraction, and GPT-4o Vision
analysis for understanding what's displayed on screen.
"""

import base64
import io
import platform
from typing import Optional

import numpy as np
from loguru import logger
from PIL import Image, ImageGrab

from backend.config import get_settings


class ScreenService:
    """Service for screen capture, OCR, and visual analysis."""

    def __init__(self):
        self._tesseract_available = False
        self._ocr_engine = None
        self._openai_client = None
        self.selected_monitor: Optional[int | str] = None
        settings = get_settings()

        # Try to set up pytesseract
        try:
            import pytesseract

            if settings.TESSERACT_PATH:
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
            # Quick test
            pytesseract.get_tesseract_version()
            self._ocr_engine = pytesseract
            self._tesseract_available = True
            logger.info("Tesseract OCR initialized successfully")
        except Exception as e:
            logger.warning(f"Tesseract OCR not available: {e}. OCR features will be limited.")

        # Set up OpenAI client for vision
        try:
            from openai import AsyncOpenAI

            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI Vision client initialized")
        except Exception as e:
            logger.warning(f"OpenAI client not available for vision: {e}")

    def take_screenshot(self, region: Optional[tuple] = None) -> Image.Image:
        """
        Capture a screenshot of the entire screen or a specific region.

        Args:
            region: Optional tuple (left, top, right, bottom) for a screen region.

        Returns:
            PIL Image of the screenshot.
        """
        try:
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            elif self.selected_monitor is not None:
                monitors = self.get_monitors()
                target = None
                
                if self.selected_monitor == "active":
                    try:
                        win_info = self.get_active_window_info()
                        if win_info and "position" in win_info:
                            pos = win_info["position"]
                            cx = (pos["left"] + pos["right"]) // 2
                            cy = (pos["top"] + pos["bottom"]) // 2
                            for m in monitors:
                                if m["left"] <= cx <= m["right"] and m["top"] <= cy <= m["bottom"]:
                                    target = m
                                    break
                    except Exception as ex:
                        logger.warning(f"Failed to detect active monitor: {ex}")
                
                if not target:
                    # Match by integer index
                    try:
                        idx = int(self.selected_monitor)
                        for m in monitors:
                            if m.get("index") == idx:
                                target = m
                                break
                    except (ValueError, TypeError):
                        pass
                
                if target and "left" in target:
                    bbox = (target["left"], target["top"], target["right"], target["bottom"])
                    screenshot = ImageGrab.grab(bbox=bbox)
                    logger.debug(f"Screenshot captured for monitor {self.selected_monitor}: {screenshot.size}")
                else:
                    logger.warning(f"Selected monitor {self.selected_monitor} not found, falling back to all screens")
                    screenshot = ImageGrab.grab(all_screens=True)
            else:
                screenshot = ImageGrab.grab(all_screens=True)
            logger.debug(f"Screenshot captured: {screenshot.size}")
            return screenshot
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            raise

    def take_active_window_screenshot(self) -> Image.Image:
        """Capture a screenshot of the currently active window."""
        try:
            import win32gui

            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                logger.warning("No active window found, capturing full screen")
                return self.take_screenshot()

            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            # Ensure valid dimensions
            if right <= left or bottom <= top:
                logger.warning("Invalid window dimensions, capturing full screen")
                return self.take_screenshot()

            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            title = win32gui.GetWindowText(hwnd)
            logger.debug(f"Active window screenshot captured: '{title}' {screenshot.size}")
            return screenshot
        except ImportError:
            logger.warning("pywin32 not available, capturing full screen")
            return self.take_screenshot()
        except Exception as e:
            logger.error(f"Failed to capture active window: {e}")
            return self.take_screenshot()

    def extract_text(self, image: Image.Image) -> str:
        """
        Extract text from an image using OCR.

        Args:
            image: PIL Image to extract text from.

        Returns:
            Extracted text string.
        """
        if not self._tesseract_available:
            return "[OCR not available] Tesseract is not installed. Please install it from https://github.com/UB-Mannheim/tesseract/wiki"

        try:
            # Preprocess for better OCR results
            processed = self._preprocess_for_ocr(image)
            text = self._ocr_engine.image_to_string(processed, config="--psm 3")
            text = text.strip()
            logger.debug(f"OCR extracted {len(text)} characters")
            return text if text else "[No text detected on screen]"
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return f"[OCR error] {str(e)}"

    def _preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR accuracy."""
        # Convert to grayscale
        gray = image.convert("L")

        # Increase contrast
        img_array = np.array(gray)
        # Simple contrast stretching
        p_low, p_high = np.percentile(img_array, (1, 99))
        if p_high > p_low:
            img_array = np.clip((img_array - p_low) * 255.0 / (p_high - p_low), 0, 255).astype(
                np.uint8
            )

        return Image.fromarray(img_array)

    async def analyze_with_vision(self, image: Image.Image, question: str) -> str:
        """
        Analyze a screenshot using Gemini 1.5 Flash Vision, with automatic fallback
        to OpenAI GPT-4o Vision.

        Args:
            image: PIL Image to analyze.
            question: Question to ask about the image.

        Returns:
            AI-generated analysis of the image.
        """
        settings = get_settings()

        # Try Google Gemini Vision first
        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                # Convert PIL image to bytes
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                img_bytes = buffer.getvalue()

                # Set up generative AI model
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel(
                    model_name=settings.GEMINI_MODEL or "gemini-1.5-flash",
                    system_instruction=(
                        "You are JARVIS, an AI desktop assistant analyzing a screenshot. "
                        "Describe what you see accurately and concisely. If there are errors, "
                        "warnings, or notable UI elements, highlight them. Be helpful and direct."
                    )
                )

                logger.info("Analyzing screen using Google Gemini Vision...")
                response = await model.generate_content_async(
                    contents=[
                        question,
                        {"mime_type": "image/png", "data": img_bytes}
                    ],
                    generation_config={"max_output_tokens": 1024}
                )
                result = response.text
                logger.info(f"Gemini Vision analysis completed: {len(result)} chars")
                return result
            except Exception as e:
                logger.warning(f"Gemini Vision analysis failed: {e}. Falling back to OpenAI...")

        # Fallback to OpenAI Vision
        if not self._openai_client:
            return "[Vision analysis unavailable] Neither Gemini nor OpenAI client is configured."

        try:
            base64_image = self.image_to_base64(image)

            logger.info("Analyzing screen using OpenAI GPT-4o Vision...")
            response = await self._openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL or "gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are JARVIS, an AI desktop assistant analyzing a screenshot. "
                            "Describe what you see accurately and concisely. If there are errors, "
                            "warnings, or notable UI elements, highlight them. Be helpful and direct."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=1024,
            )

            result = response.choices[0].message.content
            logger.info(f"OpenAI Vision analysis completed: {len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"OpenAI Vision analysis failed: {e}")
            return f"[Vision analysis error] {str(e)}"


    def get_active_window_info(self) -> dict:
        """Get information about the currently active window."""
        try:
            import win32gui
            import win32process

            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            return {
                "title": title,
                "handle": hwnd,
                "pid": pid,
                "position": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
                "size": {"width": rect[2] - rect[0], "height": rect[3] - rect[1]},
            }
        except Exception as e:
            logger.error(f"Failed to get active window info: {e}")
            return {"title": "Unknown", "error": str(e)}

    def get_monitors(self) -> list[dict]:
        """Get information about all connected monitors."""
        monitors = []
        try:
            import win32api

            for i, monitor in enumerate(win32api.EnumDisplayMonitors()):
                handle, _, rect = monitor
                info = {
                    "index": i,
                    "handle": int(handle),
                    "left": rect[0],
                    "top": rect[1],
                    "right": rect[2],
                    "bottom": rect[3],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                    "primary": rect[0] == 0 and rect[1] == 0,
                }
                monitors.append(info)
        except ImportError:
            # Fallback: get primary monitor info from PIL
            screen = ImageGrab.grab()
            monitors.append(
                {
                    "index": 0,
                    "width": screen.width,
                    "height": screen.height,
                    "primary": True,
                }
            )
        except Exception as e:
            logger.error(f"Failed to enumerate monitors: {e}")

        return monitors

    @staticmethod
    def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
        """Convert a PIL Image to a base64-encoded string."""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def base64_to_image(base64_str: str) -> Image.Image:
        """Convert a base64-encoded string back to a PIL Image."""
        image_data = base64.b64decode(base64_str)
        return Image.open(io.BytesIO(image_data))
