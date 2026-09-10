"""
Research Skill for FastMCP & Skill Registry integration.
Exposes tools: research report generation, PDF analysis, fact claim verification,
sentiment analysis, semantic keyword & entity extraction, text summarization, style rewriting,
and biological & chemical science tools (formula parsing, equation balancing, PubChem compound lookup).
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.research_agent import ResearchAgentService
from backend.services.prompt_pipeline import transformation_engine
from backend.services.science_service import science_service


class ResearchSkill(BaseSkill):
    """Skill exposing Research Agent tools, linguistic transformations, and scientific intelligence."""

    name = "ResearchSkill"
    description = "Research reports, PDF parsing, fact verification, sentiment analysis, entity extraction, text transformations, and chemoinformatics/biology tools."

    def __init__(self, research_service: Optional[ResearchAgentService] = None):
        self.research_service = research_service or ResearchAgentService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "generate_research_report",
                "description": "Synthesize research topic findings into a structured markdown report with citations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Research subject query."}
                    },
                    "required": ["topic"]
                }
            },
            {
                "name": "analyze_pdf_document",
                "description": "Extract text, headings, and structure from a local PDF document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pdf_path": {"type": "string", "description": "Path to local PDF file."}
                    },
                    "required": ["pdf_path"]
                }
            },
            {
                "name": "verify_fact_claim",
                "description": "Evaluate a claim or fact statement against reference sources.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string", "description": "Claim text to verify."}
                    },
                    "required": ["claim"]
                }
            },
            {
                "name": "manage_browser_profile",
                "description": "Inspect Playwright persistent browser context profile directory and saved session states.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "multi_tab_browser_action",
                "description": "Simulate multi-tab browser context controls (create, list, switch, close tab).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create_tab", "list_tabs", "switch_tab", "close_tab"]},
                        "url": {"type": "string", "description": "Optional URL for new tab."},
                        "tab_id": {"type": "integer", "description": "Optional target tab ID."}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "analyze_sentiment",
                "description": "Analyze polarity score (-1.0 to 1.0), emotional tone, and aspect-level sentiment for a text snippet.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text content to evaluate for sentiment and tone."}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "extract_keywords_and_entities",
                "description": "Extract semantic keywords, key phrases, dates, metrics, emails, and named entities from text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze."},
                        "top_k": {"type": "integer", "description": "Max number of keywords to return (default: 10)."}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "summarize_content",
                "description": "Summarize text into concise bullet points, executive summary, or single-sentence TL;DR.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to summarize."},
                        "mode": {"type": "string", "enum": ["bullet_points", "executive_summary", "one_sentence", "tldr"]},
                        "length": {"type": "string", "enum": ["concise", "standard", "comprehensive"]}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "transform_text_style",
                "description": "Rewrite text to match a target style (executive, technical, casual, persuasive, concise, customer_support).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Input text to transform."},
                        "target_style": {"type": "string", "description": "Target writing style preset."},
                        "tone": {"type": "string", "description": "Optional tone modifier."}
                    },
                    "required": ["text", "target_style"]
                }
            },
            {
                "name": "analyze_chemical_formula",
                "description": "Parse a chemical formula (e.g. C6H12O6, H2SO4, Ca(OH)2) to compute elemental counts, molecular weight, and mass percentages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "formula": {"type": "string", "description": "Chemical formula (e.g. 'C6H12O6', 'NaCl', 'H2SO4')."}
                    },
                    "required": ["formula"]
                }
            },
            {
                "name": "balance_chemical_equation",
                "description": "Balance a chemical equation (e.g. 'H2 + O2 -> H2O', 'CH4 + O2 -> CO2 + H2O').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "equation": {"type": "string", "description": "Chemical equation with reactants and products."}
                    },
                    "required": ["equation"]
                }
            },
            {
                "name": "query_pubchem_compound",
                "description": "Search the NCBI PubChem database for verified compound properties, SMILES, and IUPAC nomenclature.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "compound_name": {"type": "string", "description": "Chemical name or common compound name (e.g. 'caffeine', 'aspirin', 'glucose')."}
                    },
                    "required": ["compound_name"]
                }
            },
            {
                "name": "explain_biological_process",
                "description": "Synthesize structured scientific breakdown of cellular, genetic, or physiological pathways.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {"type": "string", "description": "Biological process (e.g. 'photosynthesis', 'cellular respiration', 'crispr')."},
                        "detail_level": {"type": "string", "enum": ["simple", "intermediate", "advanced"]}
                    },
                    "required": ["process_name"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "generate_research_report":
            return self.research_service.generate_research_report(parameters.get("topic", ""))
        elif tool_name == "analyze_pdf_document":
            return self.research_service.analyze_pdf_document(parameters.get("pdf_path", ""))
        elif tool_name == "verify_fact_claim":
            return self.research_service.verify_fact_claim(parameters.get("claim", ""))
        elif tool_name == "manage_browser_profile":
            return self.research_service.manage_browser_profile()
        elif tool_name == "multi_tab_browser_action":
            return self.research_service.multi_tab_browser_action(
                parameters.get("action", "list_tabs"),
                parameters.get("url"),
                parameters.get("tab_id")
            )
        elif tool_name == "analyze_sentiment":
            res = await transformation_engine.analyze_sentiment(parameters.get("text", ""))
            return res.model_dump()
        elif tool_name == "extract_keywords_and_entities":
            res = await transformation_engine.extract_keywords_and_entities(
                parameters.get("text", ""),
                top_k=parameters.get("top_k", 10)
            )
            return res.model_dump()
        elif tool_name == "summarize_content":
            res = await transformation_engine.summarize_text(
                parameters.get("text", ""),
                mode=parameters.get("mode", "bullet_points"),
                length=parameters.get("length", "concise")
            )
            return res.model_dump()
        elif tool_name == "transform_text_style":
            res = await transformation_engine.transform_style(
                parameters.get("text", ""),
                target_style=parameters.get("target_style", "executive"),
                tone=parameters.get("tone", "professional")
            )
            return res.model_dump()
        elif tool_name == "analyze_chemical_formula":
            return science_service.parse_chemical_formula(parameters.get("formula", ""))
        elif tool_name == "balance_chemical_equation":
            return science_service.balance_chemical_equation(parameters.get("equation", ""))
        elif tool_name == "query_pubchem_compound":
            return science_service.query_pubchem_compound(parameters.get("compound_name", ""))
        elif tool_name == "explain_biological_process":
            return science_service.explain_biological_process(
                parameters.get("process_name", ""),
                detail_level=parameters.get("detail_level", "intermediate")
            )
        else:
            raise ValueError(f"Unknown research tool: {tool_name}")
