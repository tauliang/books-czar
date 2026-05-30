from __future__ import annotations

from backend.certificates import build_certificate_pdf
from backend.quiz import (
    QuizChoice,
    QuizQuestion,
    build_quiz_prompts,
    parse_quiz_response,
    sanitize_quiz_questions,
    score_quiz_attempt,
)
from backend.schemas import QuizAttemptOut, QuizQuestionResultOut, QuizRunOut, SourceOut


def test_build_quiz_prompts_request_strict_four_choice_json():
    source = SourceOut(
        book_id="book-1",
        title="Strategy",
        location="chunk 1",
        excerpt="AI strategy requires governance and adoption metrics.",
        score=0.8,
    )

    system_prompt, user_prompt = build_quiz_prompts(5, [source])

    assert "strict JSON only" in system_prompt
    assert "Create exactly 5 multiple-choice questions" in user_prompt
    assert "exactly 4 choices" in user_prompt
    assert "Exactly 1 choice must have correct=true" in user_prompt
    assert '"correct": false' in user_prompt
    assert "[S1] Strategy" in user_prompt


def test_parse_quiz_response_rejects_malformed_answer_sets():
    raw = """
    {
      "title": "Bad Quiz",
      "questions": [{
        "id": "q1",
        "prompt": "What matters?",
        "choices": [
          {"id": "A", "text": "Governance", "correct": true},
          {"id": "B", "text": "Metrics", "correct": true},
          {"id": "C", "text": "Speed", "correct": false},
          {"id": "D", "text": "Reuse", "correct": false}
        ],
        "explanation": "Only one answer should be correct.",
        "citations": ["S1"]
      }]
    }
    """

    try:
        parse_quiz_response(raw, 1)
    except ValueError as exc:
        assert "exactly 1 correct choice" in str(exc)
    else:
        raise AssertionError("Malformed quiz was accepted")


def test_score_quiz_attempt_handles_passing_threshold():
    questions = [
        QuizQuestion(
            id=f"q{index}",
            prompt=f"Question {index}?",
            choices=[
                QuizChoice(id="A", text="Correct", correct=True),
                QuizChoice(id="B", text="Wrong", correct=False),
                QuizChoice(id="C", text="Wronger", correct=False),
                QuizChoice(id="D", text="Wrongest", correct=False),
            ],
            explanation="Because A is supported.",
            citations=["S1"],
        )
        for index in range(1, 6)
    ]

    score, passed, results = score_quiz_attempt(
        questions,
        {"q1": "A", "q2": "A", "q3": "A", "q4": "A", "q5": "B"},
    )

    assert score == 80.0
    assert passed is True
    assert results[-1].correct is False


def test_sanitized_quiz_questions_do_not_leak_answer_keys():
    question = QuizQuestion(
        id="q1",
        prompt="What should leaders measure?",
        choices=[
            QuizChoice(id="A", text="Adoption", correct=True),
            QuizChoice(id="B", text="Noise", correct=False),
            QuizChoice(id="C", text="Guesswork", correct=False),
            QuizChoice(id="D", text="Delay", correct=False),
        ],
        explanation="Adoption is supported.",
        citations=["S1"],
    )

    sanitized = sanitize_quiz_questions([question])[0].model_dump()

    assert "correct" not in sanitized["choices"][0]
    assert sanitized["choices"][0] == {"id": "A", "text": "Adoption"}


def test_certificate_pdf_generation_returns_valid_pdf_payload():
    quiz = QuizRunOut(
        id="quiz-1",
        title="Mastery Quiz: Strategy",
        book_ids=["book-1"],
        question_count=5,
        passing_score=80.0,
        status="complete",
        questions=[],
        error=None,
        created_at="2026-06-01T12:00:00+00:00",
        updated_at="2026-06-01T12:00:00+00:00",
    )
    attempt = QuizAttemptOut(
        id="attempt-1",
        quiz_id="quiz-1",
        learner_name="Ada Lovelace",
        answers={},
        score=100.0,
        passed=True,
        results=[
            QuizQuestionResultOut(
                question_id="q1",
                prompt="Question?",
                choices=[],
                selected_choice_id="A",
                correct_choice_id="A",
                correct=True,
                explanation="Because.",
                citations=["S1"],
            )
        ],
        created_at="2026-06-01T12:30:00+00:00",
    )

    pdf = build_certificate_pdf(quiz, attempt)

    assert pdf.startswith(b"%PDF-1.4")
    assert b"Certificate of Completion" in pdf
    assert b"Ada Lovelace" in pdf
