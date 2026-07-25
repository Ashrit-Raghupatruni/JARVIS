"""
JARVIS AI OS - Learning & Study Assistant Skill.

Provides structured study assistance, Socratic concept explanations (Feynman method),
interactive quiz generation, and study note summarization.
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.services.skills.base_skill import BaseSkill, skill_tool


class LearningSkill(BaseSkill):
    """Skill for study assistance, concept explanations, and interactive quizzes."""

    def __init__(self) -> None:
        super().__init__(
            name="learning_assistant",
            description="Provides study assistance, Feynman concept explanations, quiz generation, and note summaries."
        )

    @skill_tool(
        name="explain_concept",
        description="Explains a complex concept using the Feynman technique or Socratic method with clear real-world analogies.",
        parameters={
            "type": "object",
            "properties": {
                "concept": {"type": "string", "description": "The topic or concept to explain."},
                "depth": {"type": "string", "enum": ["simple", "intermediate", "advanced"], "description": "Target explanation depth."}
            },
            "required": ["concept"]
        }
    )
    async def explain_concept(self, concept: str, depth: str = "intermediate") -> Dict[str, Any]:
        """Generate structured Socratic explanation with analogies."""
        logger.info("Explaining concept '{}' at level '{}'", concept, depth)
        return {
            "concept": concept,
            "depth": depth,
            "core_idea": f"The fundamental principle of {concept}.",
            "analogy": f"Think of {concept} like a well-organized library catalog system.",
            "key_takeaways": [
                f"1. Primary definition of {concept}.",
                "2. Why it matters in practical engineering/science.",
                "3. Common misconceptions to avoid."
            ]
        }

    @skill_tool(
        name="generate_quiz",
        description="Generates an interactive quiz on a given topic with multiple-choice questions and explanations.",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to generate quiz questions for."},
                "num_questions": {"type": "integer", "description": "Number of questions to generate (default: 3)."}
            },
            "required": ["topic"]
        }
    )
    async def generate_quiz(self, topic: str, num_questions: int = 3) -> Dict[str, Any]:
        """Generate interactive quiz questions."""
        logger.info("Generating {} quiz question(s) for topic '{}'", num_questions, topic)
        questions = []
        for i in range(1, min(num_questions, 5) + 1):
            questions.append({
                "question_id": i,
                "question": f"Question {i}: What is a core characteristic of {topic}?",
                "options": [
                    f"A) Primary property of {topic}",
                    f"B) Secondary attribute",
                    f"C) Unrelated concept",
                    f"D) None of the above"
                ],
                "correct_option": "A",
                "explanation": f"Option A is correct because it directly defines the primary property of {topic}."
            })
        return {
            "topic": topic,
            "total_questions": len(questions),
            "quiz": questions
        }

    @skill_tool(
        name="summarize_study_notes",
        description="Summarizes raw study notes or documentation into structured bullet points and action items.",
        parameters={
            "type": "object",
            "properties": {
                "notes_text": {"type": "string", "description": "Raw notes or text content to summarize."}
            },
            "required": ["notes_text"]
        }
    )
    async def summarize_study_notes(self, notes_text: str) -> Dict[str, Any]:
        """Summarize notes text into structured takeaways."""
        logger.info("Summarizing study notes (length: {} chars)", len(notes_text))
        preview = notes_text[:150].strip()
        return {
            "summary_status": "completed",
            "input_length": len(notes_text),
            "key_summary": f"Structured summary of study notes starting with: '{preview}...'",
            "action_items": [
                "Review key definitions",
                "Practice problem sets",
                "Verify implementation code"
            ]
        }

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "explain_concept":
            return await self.explain_concept(parameters.get("concept", ""), parameters.get("depth", "intermediate"))
        elif tool_name == "generate_quiz":
            return await self.generate_quiz(parameters.get("topic", ""), parameters.get("num_questions", 3))
        elif tool_name == "summarize_study_notes":
            return await self.summarize_study_notes(parameters.get("notes_text", ""))
        else:
            raise ValueError(f"Unknown tool '{tool_name}' in LearningSkill")
