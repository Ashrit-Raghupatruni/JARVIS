"""
JARVIS AI OS — Phase 1 Capability Expansion Test Suite.
Tests:
- Centralized Prompt Transformation Pipeline (summarization, style, keywords, sentiment)
- ResearchSkill sentiment & entity extraction tools
- DeveloperSkill AST docstrings and Text-to-SQL engine with read-only AST safety validation
- ProductivitySkill Markdown note-taking and marketing copywriting tools
- Response-Length Discipline prompt configurations
"""

import os
import sys
import pytest
import tempfile
import sqlite3
from pathlib import Path

from backend.services.prompt_pipeline import TransformationEngine, transformation_engine
from backend.services.skills.research_skill import ResearchSkill
from backend.services.skills.developer_skill import DeveloperSkill
from backend.services.skills.productivity_skill import ProductivitySkill
from backend.services.developer_assistant import DeveloperAssistantService
from backend.services.productivity_service import ProductivityService


@pytest.mark.asyncio
async def test_prompt_pipeline_summarization():
    engine = TransformationEngine()
    long_text = (
        "JARVIS AI OS is a local-first voice-controlled desktop environment for Windows. "
        "It features a multi-agent planner using LangGraph and Prash SLM for ultra-fast intent execution. "
        "The system incorporates desktop automation via native UI Automation and OCR self-healing fallback. "
        "Furthermore, JARVIS includes biometric face authentication and Ed25519 asymmetric mobile pairing. "
        "Memory is stored locally using ChromaDB vector database and SQLite for conversations."
    )

    # Bullet points mode
    bullets = await engine.summarize_text(long_text, mode="bullet_points", length="concise")
    assert bullets.summary != ""
    assert bullets.original_word_count > bullets.summary_word_count
    assert len(bullets.key_takeaways) >= 1

    # One sentence mode
    one_sent = await engine.summarize_text(long_text, mode="one_sentence", length="concise")
    assert one_sent.summary != ""
    assert "\n" not in one_sent.summary.strip()


@pytest.mark.asyncio
async def test_prompt_pipeline_style_transformation():
    engine = TransformationEngine()
    draft = "we need to fix the bug in the code fast because users are complaining about crashes."

    exec_style = await engine.transform_style(draft, target_style="executive", tone="professional")
    assert exec_style.transformed_text != ""
    assert exec_style.target_style == "executive"
    assert len(exec_style.applied_rules) >= 1


@pytest.mark.asyncio
async def test_prompt_pipeline_keywords_and_entities():
    engine = TransformationEngine()
    content = "Contact support@jarvis.ai before September 15, 2026 for a 20% discount on NVIDIA RTX 4090 integration. Visit https://jarvis.ai."

    res = await engine.extract_keywords_and_entities(content, top_k=5)
    assert len(res.keywords) >= 1
    entity_types = {e.category for e in res.entities}
    assert "EMAIL" in entity_types
    assert "URL" in entity_types
    assert "METRIC" in entity_types or "DATE" in entity_types


@pytest.mark.asyncio
async def test_prompt_pipeline_sentiment_analysis():
    engine = TransformationEngine()

    pos_text = "The new release is amazing! Performance is super fast, secure, and reliable."
    pos_res = await engine.analyze_sentiment(pos_text)
    assert pos_res.sentiment == "positive"
    assert pos_res.score > 0.0

    neg_text = "The application is broken and slow. We encountered a critical error and crash."
    neg_res = await engine.analyze_sentiment(neg_text)
    assert neg_res.sentiment == "negative"
    assert neg_res.score < 0.0


@pytest.mark.asyncio
async def test_research_skill_transformation_tools():
    skill = ResearchSkill()

    # Test Sentiment tool
    s_res = await skill.execute_tool("analyze_sentiment", {"text": "Great work on the update!"})
    assert s_res.get("sentiment") == "positive"

    # Test Keyword tool
    k_res = await skill.execute_tool("extract_keywords_and_entities", {"text": "Meeting at test@example.com about latency"})
    assert "keywords" in k_res
    assert "entities" in k_res

    # Test Summarize tool
    sum_res = await skill.execute_tool("summarize_content", {"text": "Line one text. Line two details. Line three conclusions."})
    assert "summary" in sum_res


@pytest.mark.asyncio
async def test_developer_skill_docstrings_and_sql():
    skill = DeveloperSkill()

    # 1. Test AST docstring generation
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write("""
def calculate_metrics(data_points, factor=1.5):
    return [x * factor for x in data_points]

class MetricProcessor:
    def process(self):
        pass
""")
        temp_path = tf.name

    try:
        doc_res = await skill.execute_tool("generate_docstrings", {"file_path": temp_path})
        assert doc_res.get("status") == "success"
        assert doc_res.get("documented_items_count") == 3
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # 2. Test Text-to-SQL Query Generation
    sql_gen = await skill.execute_tool("generate_sql_query", {"user_query": "count total records in users table"})
    assert sql_gen.get("status") == "query_generated"
    assert "SELECT" in sql_gen.get("generated_sql", "").upper()

    # 3. Test Safe SQL Execution with SQLite DB
    with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as db_f:
        db_path = db_f.name

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT);")
        cursor.execute("INSERT INTO users (username, role) VALUES ('admin', 'superadmin'), ('ashrit', 'engineer');")
        conn.commit()
        conn.close()

        # Valid SELECT query
        exec_res = await skill.execute_tool("execute_safe_sql_query", {
            "sql_query": "SELECT username, role FROM users;",
            "db_path": db_path
        })
        assert exec_res.get("status") == "success"
        assert exec_res.get("row_count") == 2
        assert exec_res.get("columns") == ["username", "role"]

        # Destructive query rejection (Fail-Closed AST Guard)
        bad_res = await skill.execute_tool("execute_safe_sql_query", {
            "sql_query": "DROP TABLE users;",
            "db_path": db_path
        })
        assert bad_res.get("status") == "forbidden"
        assert "destructive" in bad_res.get("error", "").lower()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.asyncio
async def test_productivity_skill_notes_and_copywriting():
    with tempfile.TemporaryDirectory() as temp_dir:
        prod_svc = ProductivityService(data_dir=Path(temp_dir))
        skill = ProductivitySkill(productivity_service=prod_svc)

        # 1. Take note
        note_res = await skill.execute_tool("take_note", {
            "title": "Roadmap Ideas",
            "content": "Explore lightweight YOLOv8-nano for local object recognition.",
            "tags": ["ai", "roadmap"]
        })
        assert note_res.get("status") == "note_saved"
        assert os.path.exists(note_res.get("file_path"))

        # 2. List notes
        list_res = await skill.execute_tool("list_notes", {})
        assert list_res.get("count") == 1
        assert list_res.get("notes")[0]["title"] == "Roadmap Ideas"

        # 3. Search notes
        search_res = await skill.execute_tool("search_notes", {"query": "YOLOv8"})
        assert search_res.get("count") == 1
        assert "YOLOv8" in search_res.get("results")[0]["snippet"]

        # 4. Draft copy
        copy_res = await skill.execute_tool("draft_copy", {
            "goal": "Launch autonomous desktop AI",
            "target_audience": "Developers & Power Users",
            "channel": "email",
            "tone": "persuasive"
        })
        assert "headline" in copy_res
        assert "value_propositions" in copy_res
        assert len(copy_res["value_propositions"]) >= 3
