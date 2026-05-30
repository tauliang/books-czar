from __future__ import annotations

import pytest

from backend.schemas import SourceOut
from backend.schemas import SynthesisRequest
from backend.synthesis import (
    LENS_LABELS,
    build_synthesis_prompts,
    build_synthesis_retrieval_questions,
    dedupe_synthesis_sources,
)


@pytest.mark.parametrize("lens", LENS_LABELS)
def test_build_synthesis_retrieval_questions_covers_each_lens(lens: str):
    questions = build_synthesis_retrieval_questions(
        "Improve our AI operating model",
        "c_suite",
        lens,
    )

    assert len(questions) == 6
    assert all("Improve our AI operating model" in question for question in questions)
    assert any("core thesis" in question for question in questions)
    assert any("metrics" in question for question in questions)
    assert LENS_LABELS[lens] in questions[0]


def test_dedupe_synthesis_sources_keeps_highest_scored_unique_sources():
    duplicate_low = SourceOut(
        book_id="book-1",
        title="Strategy",
        location="chunk 1",
        excerpt="same excerpt",
        score=0.2,
    )
    duplicate_high = duplicate_low.model_copy(update={"score": 0.9})
    second = SourceOut(
        book_id="book-2",
        title="Risk",
        location="chunk 3",
        excerpt="different excerpt",
        score=0.6,
    )

    deduped = dedupe_synthesis_sources([duplicate_low, second, duplicate_high])

    assert deduped == [duplicate_high, second]


def test_build_synthesis_prompts_request_executive_ready_structure():
    request = SynthesisRequest(
        objective="Prioritize AI strategy",
        audience="board",
        lens="strategy",
        book_ids=None,
    )
    source = SourceOut(
        book_id="book-1",
        title="Strategy",
        location="chapter 1",
        excerpt="Executives should govern AI with measurable adoption goals.",
        score=0.8,
    )

    system_prompt, user_prompt = build_synthesis_prompts(request, [source])

    assert "executive-ready Board Brief" in system_prompt
    assert "one concise executive takeaway" in user_prompt
    assert "3-5 cross-book themes" in user_prompt
    assert "clearly labeled risks" in user_prompt
    assert "3-6 measurable executive indicators" in user_prompt
    assert "Use [S#] citations" in user_prompt
    assert "[S1] Strategy" in user_prompt
