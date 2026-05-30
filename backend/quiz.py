from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from .schemas import QuizChoiceOut, QuizQuestionOut, QuizQuestionResultOut, SourceOut


PASSING_SCORE = 80.0


class QuizChoice(BaseModel):
    id: str
    text: str
    correct: bool = False


class QuizQuestion(BaseModel):
    id: str
    prompt: str
    choices: list[QuizChoice]
    explanation: str
    citations: list[str] = Field(default_factory=list)


def build_quiz_retrieval_questions() -> list[str]:
    return [
        "What are the core concepts, named frameworks, and central ideas a reader must master?",
        "What definitions, distinctions, and terminology are essential for a knowledge check?",
        "What practical implications, decisions, or applications should a reader understand?",
        "What risks, tradeoffs, limitations, or governance concerns should a reader recognize?",
        "What examples or scenarios best test whether the reader can apply the material?",
    ]


def build_quiz_prompts(question_count: int, sources: list[SourceOut]) -> tuple[str, str]:
    context_blocks = []
    for index, source in enumerate(sources, start=1):
        context_blocks.append(
            f"[S{index}] {source.title} ({source.location or 'unknown location'})\n{source.excerpt}"
        )
    system_prompt = (
        "You are a mastery assessment designer for a private local book library. "
        "Create rigorous multiple-choice questions using only the supplied excerpts. "
        "Return strict JSON only; do not wrap it in Markdown."
    )
    user_prompt = (
        f"Create exactly {question_count} multiple-choice questions.\n\n"
        "Rules:\n"
        "- Each question must test mastery of the supplied book excerpts.\n"
        "- Each question must have exactly 4 choices.\n"
        "- Exactly 1 choice must have correct=true and 3 choices must have correct=false.\n"
        "- False choices must be plausible but clearly wrong based on the excerpts.\n"
        "- Include a short explanation for the correct answer.\n"
        "- Include citations using source IDs like [S1].\n"
        "- Do not invent facts outside the excerpts.\n\n"
        "Return this JSON shape exactly:\n"
        "{\n"
        '  "title": "Mastery Quiz: <short title>",\n'
        '  "questions": [\n'
        "    {\n"
        '      "id": "q1",\n'
        '      "prompt": "Question text?",\n'
        '      "choices": [\n'
        '        {"id": "A", "text": "Choice text", "correct": true},\n'
        '        {"id": "B", "text": "Choice text", "correct": false},\n'
        '        {"id": "C", "text": "Choice text", "correct": false},\n'
        '        {"id": "D", "text": "Choice text", "correct": false}\n'
        "      ],\n"
        '      "explanation": "Why the correct answer is right.",\n'
        '      "citations": ["S1"]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Excerpts:\n\n"
        + "\n\n".join(context_blocks)
    )
    return system_prompt, user_prompt


def parse_quiz_response(raw_response: str, question_count: int) -> tuple[str, list[QuizQuestion]]:
    payload = _loads_json_object(raw_response)
    title = _clean_text(str(payload.get("title") or "Mastery Quiz"))
    questions_payload = payload.get("questions")
    if not isinstance(questions_payload, list):
        raise ValueError("Quiz response must include a questions array.")
    if len(questions_payload) != question_count:
        raise ValueError(f"Quiz response must include exactly {question_count} questions.")

    questions = [_question_from_payload(item, index) for index, item in enumerate(questions_payload, start=1)]
    return title, questions


def sanitize_quiz_questions(questions: list[QuizQuestion]) -> list[QuizQuestionOut]:
    return [
        QuizQuestionOut(
            id=question.id,
            prompt=question.prompt,
            choices=[QuizChoiceOut(id=choice.id, text=choice.text) for choice in question.choices],
            citations=question.citations,
        )
        for question in questions
    ]


def score_quiz_attempt(
    questions: list[QuizQuestion],
    answers: dict[str, str],
    passing_score: float = PASSING_SCORE,
) -> tuple[float, bool, list[QuizQuestionResultOut]]:
    if not questions:
        return 0.0, False, []

    correct_count = 0
    results: list[QuizQuestionResultOut] = []
    normalized_answers = {str(key): str(value) for key, value in answers.items()}
    for question in questions:
        correct_choice = next(choice for choice in question.choices if choice.correct)
        selected_choice_id = normalized_answers.get(question.id)
        correct = selected_choice_id == correct_choice.id
        if correct:
            correct_count += 1
        results.append(
            QuizQuestionResultOut(
                question_id=question.id,
                prompt=question.prompt,
                choices=[QuizChoiceOut(id=choice.id, text=choice.text) for choice in question.choices],
                selected_choice_id=selected_choice_id,
                correct_choice_id=correct_choice.id,
                correct=correct,
                explanation=question.explanation,
                citations=question.citations,
            )
        )

    score = round((correct_count / len(questions)) * 100, 1)
    return score, score >= passing_score, results


def questions_from_json(value: str) -> list[QuizQuestion]:
    data = json.loads(value or "[]")
    return [QuizQuestion(**question) for question in data]


def questions_to_json(questions: list[QuizQuestion]) -> str:
    return json.dumps([question.model_dump() for question in questions])


def _loads_json_object(raw_response: str) -> dict[str, Any]:
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Quiz response must be a JSON object.")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Quiz response must be a JSON object.")
    return payload


def _question_from_payload(item: Any, index: int) -> QuizQuestion:
    if not isinstance(item, dict):
        raise ValueError("Each quiz question must be an object.")
    question_id = _clean_text(str(item.get("id") or f"q{index}"))
    prompt = _clean_text(str(item.get("prompt") or item.get("question") or ""))
    explanation = _clean_text(str(item.get("explanation") or ""))
    citations = item.get("citations") or []
    if not isinstance(citations, list):
        citations = []
    clean_citations = [_clean_text(str(citation)) for citation in citations if _clean_text(str(citation))]
    if not question_id or not prompt or not explanation:
        raise ValueError("Each quiz question needs an id, prompt, and explanation.")

    choices_payload = item.get("choices")
    if not isinstance(choices_payload, list) or len(choices_payload) != 4:
        raise ValueError("Each quiz question must have exactly 4 choices.")
    choices = [_choice_from_payload(choice, offset) for offset, choice in enumerate(choices_payload)]
    if sum(1 for choice in choices if choice.correct) != 1:
        raise ValueError("Each quiz question must have exactly 1 correct choice.")
    normalized_texts = [_clean_key(choice.text) for choice in choices]
    if len(set(normalized_texts)) != 4:
        raise ValueError("Quiz choices must not be duplicated.")
    normalized_ids = [_clean_key(choice.id) for choice in choices]
    if len(set(normalized_ids)) != 4:
        raise ValueError("Quiz choice ids must not be duplicated.")

    return QuizQuestion(
        id=question_id,
        prompt=prompt,
        choices=choices,
        explanation=explanation,
        citations=clean_citations,
    )


def _choice_from_payload(item: Any, offset: int) -> QuizChoice:
    if not isinstance(item, dict):
        raise ValueError("Each quiz choice must be an object.")
    choice_id = _clean_text(str(item.get("id") or chr(ord("A") + offset))).upper()
    text = _clean_text(str(item.get("text") or ""))
    if not choice_id or not text:
        raise ValueError("Each quiz choice needs an id and text.")
    return QuizChoice(id=choice_id, text=text, correct=bool(item.get("correct")))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_key(value: str) -> str:
    return _clean_text(value).casefold()
