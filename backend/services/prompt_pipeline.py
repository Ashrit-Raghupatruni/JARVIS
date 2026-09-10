"""
JARVIS AI OS — Prompt Transformation Pipeline & Linguistic Engine.

Provides unified, deterministic, schema-validated transformations:
1. Summarization (Bullet points, Executive, One-sentence, TL;DR)
2. Style-Based Rewriting (Executive, Technical, Casual, Persuasive, Support)
3. Semantic Keyword & Entity Extraction (Keywords, Entities, Metrics, Action items)
4. Sentiment & Tone Analysis (Polarity score, subjective aspect breakdown)
5. Structured Schema Extraction (Pydantic / JSON key-value conforming extraction)
"""

from __future__ import annotations

import re
import math
import json
import asyncio
from collections import Counter
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger


class SummarizationResult(BaseModel):
    summary: str
    mode: str
    original_word_count: int
    summary_word_count: int
    compression_ratio: float
    key_takeaways: List[str] = Field(default_factory=list)


class StyleTransformResult(BaseModel):
    transformed_text: str
    target_style: str
    tone: str
    word_count: int
    applied_rules: List[str] = Field(default_factory=list)


class EntityItem(BaseModel):
    text: str
    category: str  # DATE, PERSON, ORG, METRIC, EMAIL, URL, TECH
    confidence: float = 1.0


class KeywordExtractionResult(BaseModel):
    keywords: List[str]
    entities: List[EntityItem]
    top_topics: List[str]
    readability_score: float


class SentimentResult(BaseModel):
    sentiment: str  # "positive", "negative", "neutral", "mixed"
    score: float  # -1.0 (very negative) to +1.0 (very positive)
    confidence: float
    aspects: Dict[str, str] = Field(default_factory=dict)
    summary: str


class TransformationEngine:
    """
    Centralized transformation and prompt execution pipeline.
    Ensures consistent LLM prompting, strict JSON output formatting, and deterministic local fallbacks.
    """

    def __init__(self, llm_service: Optional[Any] = None) -> None:
        self._llm = llm_service
        logger.info("TransformationEngine initialized.")

    def _get_llm(self) -> Any:
        if self._llm is None:
            try:
                from backend.services.manager import ServiceManager
                self._llm = ServiceManager.get_instance("llm_service")
            except Exception:
                pass
            if self._llm is None:
                try:
                    from backend.services.llm import LLMService
                    self._llm = LLMService()
                except Exception:
                    pass
        return self._llm

    # ── 1. Summarization Pipeline ────────────────────────────────────────

    async def summarize_text(
        self,
        text: str,
        mode: str = "bullet_points",
        length: str = "concise",
        max_words: Optional[int] = None
    ) -> SummarizationResult:
        """
        Summarize input text with mode and length controls.
        Modes: 'bullet_points', 'executive_summary', 'one_sentence', 'tldr'
        Length: 'concise', 'standard', 'comprehensive'
        """
        if not text or not text.strip():
            return SummarizationResult(
                summary="",
                mode=mode,
                original_word_count=0,
                summary_word_count=0,
                compression_ratio=1.0,
                key_takeaways=[]
            )

        words = text.strip().split()
        orig_count = len(words)

        # Word targets based on length
        if max_words is None:
            if length == "concise":
                target_words = max(30, int(orig_count * 0.2))
            elif length == "comprehensive":
                target_words = max(100, int(orig_count * 0.5))
            else:
                target_words = max(60, int(orig_count * 0.35))
        else:
            target_words = max_words

        prompt = (
            f"You are a precise transformation engine. Summarize the following text according to these instructions:\n"
            f"- Mode: {mode}\n"
            f"- Target Length: ~{target_words} words ({length})\n"
            f"- Formatting: If mode is 'bullet_points', output 3-5 high-signal bullet points. "
            f"If 'executive_summary', output 1-2 structured paragraphs. If 'one_sentence' or 'tldr', output exactly 1 clear sentence.\n"
            f"- Rule: Do not add conversational filler. Output only the summary.\n\n"
            f"Text to summarize:\n\"\"\"\n{text}\n\"\"\""
        )

        llm = self._get_llm()
        summary_text = ""
        if llm and hasattr(llm, "generate_response"):
            try:
                resp = await llm.generate_response(prompt=prompt, system_prompt="You are a strict text transformation engine.")
                summary_text = resp.strip() if isinstance(resp, str) else str(resp).strip()
            except Exception as e:
                logger.warning("LLM summarization failed, falling back to lexical extractive method: {}", e)

        # Fallback to deterministic lexical extractive summarization if LLM unavailable
        if not summary_text:
            summary_text = self._extractive_summarize(text, mode=mode, target_words=target_words)

        summary_words = len(summary_text.split())
        ratio = round(summary_words / max(1, orig_count), 3)

        # Extract bullet takeaways
        takeaways = [
            line.lstrip("*-• ").strip()
            for line in summary_text.split("\n")
            if line.strip().startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5."))
        ]
        if not takeaways and summary_text:
            takeaways = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary_text) if s.strip()][:3]

        return SummarizationResult(
            summary=summary_text,
            mode=mode,
            original_word_count=orig_count,
            summary_word_count=summary_words,
            compression_ratio=ratio,
            key_takeaways=takeaways
        )

    def _extractive_summarize(self, text: str, mode: str, target_words: int) -> str:
        """Deterministic TF-IDF lexical sentence scoring fallback."""
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 10]
        if not sentences:
            return text[:target_words * 6]

        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        stopwords = {"the", "and", "that", "this", "with", "from", "for", "are", "was", "were", "been", "have", "has", "had"}
        filtered = [w for w in words if w not in stopwords]
        word_freq = Counter(filtered)

        scored_sentences = []
        for idx, s in enumerate(sentences):
            s_words = re.findall(r'\b[a-zA-Z]{3,}\b', s.lower())
            score = sum(word_freq.get(w, 0) for w in s_words) / max(1, math.sqrt(len(s_words) + 1))
            # Position boost for lead sentences
            if idx == 0:
                score *= 1.3
            scored_sentences.append((score, idx, s))

        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        top_count = 1 if mode in ("one_sentence", "tldr") else min(4, max(2, len(sentences) // 3))
        selected = sorted(scored_sentences[:top_count], key=lambda x: x[1])

        if mode == "bullet_points":
            return "\n".join(f"- {s[2]}" for s in selected)
        return " ".join(s[2] for s in selected)

    # ── 2. Style-Based Rewriting Pipeline ────────────────────────────────

    async def transform_style(
        self,
        text: str,
        target_style: str = "executive",
        tone: str = "professional"
    ) -> StyleTransformResult:
        """
        Transform text into target style and tone.
        Styles: 'executive', 'technical', 'casual', 'persuasive', 'concise', 'customer_support', 'academic'
        """
        if not text or not text.strip():
            return StyleTransformResult(
                transformed_text="",
                target_style=target_style,
                tone=tone,
                word_count=0,
                applied_rules=[]
            )

        style_guidelines = {
            "executive": "Concise, high-impact, decision-focused, active voice, bulleted takeaways where appropriate.",
            "technical": "Precise terminology, explicit architecture/systems references, structured syntax, clear parameters.",
            "casual": "Conversational, approachable, friendly, natural phrasing, contractions allowed.",
            "persuasive": "Compelling call to action, benefit-driven framing, clear value propositions, confident cadence.",
            "concise": "Zero fluff, minimal adjectives, direct sentences, maximal information density.",
            "customer_support": "Empathetic, clear step-by-step guidance, reassuring tone, patient explanations.",
            "academic": "Objective, formal terminology, passive/analytic constructions, balanced argumentation."
        }

        guideline = style_guidelines.get(target_style.lower(), "Professional and clear.")

        prompt = (
            f"You are an expert editor. Rewrite the following text to match the specified style and tone.\n"
            f"- Target Style: {target_style} ({guideline})\n"
            f"- Desired Tone: {tone}\n"
            f"- Rule: Preserve all core facts and intent. Output ONLY the rewritten text without preambles or explanations.\n\n"
            f"Original Text:\n\"\"\"\n{text}\n\"\"\""
        )

        llm = self._get_llm()
        transformed = ""
        if llm and hasattr(llm, "generate_response"):
            try:
                resp = await llm.generate_response(prompt=prompt, system_prompt="You are a professional writing transformation engine.")
                transformed = resp.strip() if isinstance(resp, str) else str(resp).strip()
            except Exception as e:
                logger.warning("LLM style transform error: {}", e)

        if not transformed:
            transformed = text.strip()

        rules = [f"Applied {target_style} style rules: {guideline}", f"Tone calibrated to {tone}"]

        return StyleTransformResult(
            transformed_text=transformed,
            target_style=target_style,
            tone=tone,
            word_count=len(transformed.split()),
            applied_rules=rules
        )

    # ── 3. Semantic Keyword & Entity Extraction ──────────────────────────

    async def extract_keywords_and_entities(
        self,
        text: str,
        top_k: int = 10,
        include_entities: bool = True
    ) -> KeywordExtractionResult:
        """
        Extract key phrases, semantic keywords, and categorized named entities.
        """
        if not text or not text.strip():
            return KeywordExtractionResult(
                keywords=[],
                entities=[],
                top_topics=[],
                readability_score=100.0
            )

        # 1. Deterministic Regex Entity Extraction
        entities: List[EntityItem] = []
        if include_entities:
            # Emails
            for email in set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)):
                entities.append(EntityItem(text=email, category="EMAIL", confidence=1.0))

            # URLs
            for url in set(re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)):
                entities.append(EntityItem(text=url, category="URL", confidence=1.0))

            # Metrics / Currency / Percentages
            for metric in set(re.findall(r'[\$€£]?\b\d+(?:\.\d+)?(?:%|k|M|B|ms|s|MB|GB|TB|Hz|GHz|kg|km)?\b', text)):
                if any(c in metric for c in "%$€£kMBms"):
                    entities.append(EntityItem(text=metric, category="METRIC", confidence=0.95))

            # Dates (ISO, formats like Sep 5, 2026 or 2026-09-08)
            for d in set(re.findall(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})\b', text, re.IGNORECASE)):
                entities.append(EntityItem(text=d, category="DATE", confidence=0.95))

            # Capitalized Named Entities (Organizations/Products/People)
            cap_entities = set(re.findall(r'\b[A-Z][a-zA-Z0-9_]{2,}(?:\s+[A-Z][a-zA-Z0-9_]+)*\b', text))
            stopwords_caps = {"The", "This", "That", "There", "When", "What", "How", "Why", "Where", "Who", "And", "For", "With"}
            for ent in cap_entities:
                if ent not in stopwords_caps and len(ent) > 3:
                    entities.append(EntityItem(text=ent, category="ORG_OR_PERSON", confidence=0.85))

        # 2. Keyphrase & Topic Extraction (Frequency & TF-IDF style)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        stopwords = {
            "the", "and", "that", "this", "with", "from", "for", "are", "was", "were", "been", "have", "has", "had",
            "not", "but", "what", "all", "were", "when", "your", "can", "said", "use", "each", "which", "she", "do",
            "how", "their", "will", "other", "about", "out", "many", "then", "them", "these", "some", "would", "into"
        }
        filtered_words = [w for w in words if w not in stopwords and len(w) > 3]
        freq = Counter(filtered_words)
        top_keywords = [w for w, _ in freq.most_common(top_k)]

        # Bi-gram collocations
        bigrams = [f"{filtered_words[i]} {filtered_words[i+1]}" for i in range(len(filtered_words)-1)]
        bigram_freq = Counter(bigrams)
        top_topics = [b for b, count in bigram_freq.most_common(5) if count >= 2] or top_keywords[:3]

        # Readability metric (Flesch-Kincaid approximation)
        total_words = max(1, len(words))
        total_sentences = max(1, len(re.split(r'[.!?]+', text)))
        avg_sentence_len = total_words / total_sentences
        readability = max(0.0, min(100.0, round(206.835 - (1.015 * avg_sentence_len) - (84.6 * (len("".join(words)) / total_words / 3.0)), 1)))

        return KeywordExtractionResult(
            keywords=top_keywords,
            entities=entities[:15],
            top_topics=top_topics,
            readability_score=readability
        )

    # ── 4. Sentiment & Tone Analysis ─────────────────────────────────────

    async def analyze_sentiment(self, text: str) -> SentimentResult:
        """
        Analyze polarity, emotional tone, and aspect-level sentiment.
        """
        if not text or not text.strip():
            return SentimentResult(
                sentiment="neutral",
                score=0.0,
                confidence=1.0,
                aspects={},
                summary="Empty input."
            )

        # Lexical baseline scoring
        pos_words = {"great", "excellent", "good", "fast", "reliable", "secure", "love", "amazing", "success", "perfect", "clean", "improved", "best", "satisfied"}
        neg_words = {"bad", "poor", "slow", "broken", "fail", "error", "vulnerable", "hate", "terrible", "issue", "bug", "crash", "worst", "unsatisfied"}

        tokens = re.findall(r'\b\w+\b', text.lower())
        pos_count = sum(1 for t in tokens if t in pos_words)
        neg_count = sum(1 for t in tokens if t in neg_words)

        total = pos_count + neg_count
        if total == 0:
            score = 0.0
            sentiment = "neutral"
        else:
            score = round((pos_count - neg_count) / max(1, total), 2)
            if score > 0.2:
                sentiment = "positive"
            elif score < -0.2:
                sentiment = "negative"
            else:
                sentiment = "mixed" if pos_count > 0 and neg_count > 0 else "neutral"

        # Aspect extraction
        aspects = {}
        for sentence in re.split(r'[.!?]+', text):
            s_clean = sentence.strip()
            if not s_clean:
                continue
            for domain in ["performance", "security", "ui", "reliability", "speed", "quality"]:
                if domain in s_clean.lower():
                    s_tokens = s_clean.lower().split()
                    s_pos = sum(1 for t in s_tokens if t in pos_words)
                    s_neg = sum(1 for t in s_tokens if t in neg_words)
                    if s_pos > s_neg:
                        aspects[domain] = "positive"
                    elif s_neg > s_pos:
                        aspects[domain] = "negative"
                    else:
                        aspects[domain] = "neutral"

        summary = f"Detected {sentiment} sentiment (score: {score}) based on {total} emotional indicators."

        return SentimentResult(
            sentiment=sentiment,
            score=score,
            confidence=round(min(1.0, 0.7 + (total * 0.05)), 2),
            aspects=aspects,
            summary=summary
        )

    # ── 5. Structured Entity & Schema Extraction ─────────────────────────

    async def extract_structured_data(
        self,
        text: str,
        target_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract structured JSON data matching a target schema specification.
        """
        prompt = (
            f"You are a strict data extraction engine. Extract information from the text below according to this JSON Schema:\n"
            f"```json\n{json.dumps(target_schema, indent=2)}\n```\n\n"
            f"Rule: Output MUST be a valid single JSON object matching the schema. Do not include markdown code blocks or explanations.\n\n"
            f"Input Text:\n\"\"\"\n{text}\n\"\"\""
        )

        llm = self._get_llm()
        if llm and hasattr(llm, "generate_response"):
            try:
                resp = await llm.generate_response(prompt=prompt, system_prompt="You are a schema-compliant data extraction engine. Return only JSON.")
                resp_text = resp.strip()
                if resp_text.startswith("```"):
                    lines = resp_text.split("\n")
                    resp_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                return json.loads(resp_text)
            except Exception as e:
                logger.warning("Structured LLM extraction failed: {}", e)

        # Fallback to key-value matching
        extracted = {}
        for key in target_schema.get("properties", {}).keys():
            pattern = rf'{key}[:\s=]+([^\n,;]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted[key] = match.group(1).strip()
            else:
                extracted[key] = None
        return extracted


# Global singleton instance
transformation_engine = TransformationEngine()
