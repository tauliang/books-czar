from __future__ import annotations

from .schemas import SourceOut, SynthesisAudience, SynthesisLens, SynthesisRequest


AUDIENCE_LABELS: dict[str, str] = {
    "board": "Board",
    "c_suite": "C-Suite",
    "cdao_leadership": "CDAO leadership",
    "technical_leaders": "technical leaders",
}

LENS_LABELS: dict[str, str] = {
    "all": "all executive angles",
    "strategy": "strategy",
    "risk_governance": "risk and governance",
    "operating_model": "operating model",
    "investment": "investment",
    "talent_change": "talent and change",
}

SYNTHESIS_SECTIONS = [
    "Executive Takeaway",
    "Cross-Book Themes",
    "Strategic Implications",
    "Risks, Tensions, and Blind Spots",
    "Recommended 30/60/90 Day Actions",
    "Metrics to Watch",
    "Source Notes",
]


def build_synthesis_retrieval_questions(
    objective: str,
    audience: SynthesisAudience | str,
    lens: SynthesisLens | str,
) -> list[str]:
    clean_objective = objective.strip()
    audience_label = AUDIENCE_LABELS.get(str(audience), str(audience))
    lens_label = LENS_LABELS.get(str(lens), str(lens))
    prefix = (
        f"For a {audience_label} audience, using a {lens_label} lens, "
        f"answer this objective: {clean_objective}."
    )
    return [
        f"{prefix} What is the core thesis across the books?",
        f"{prefix} What recurring themes appear across multiple books?",
        f"{prefix} Where do the books disagree, create tension, or reveal blind spots?",
        f"{prefix} What are the executive strategic implications?",
        f"{prefix} What risks, governance issues, or control concerns matter most?",
        f"{prefix} What actions, operating moves, and metrics should leaders consider?",
    ]


def dedupe_synthesis_sources(sources: list[SourceOut], limit: int = 18) -> list[SourceOut]:
    ordered = sorted(sources, key=lambda source: source.score, reverse=True)
    seen: set[tuple[str, str | None, str]] = set()
    deduped: list[SourceOut] = []
    for source in ordered:
        key = (source.book_id, source.location, source.excerpt)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
        if len(deduped) >= limit:
            break
    return deduped


def build_synthesis_prompts(request: SynthesisRequest, sources: list[SourceOut]) -> tuple[str, str]:
    audience_label = AUDIENCE_LABELS[request.audience]
    lens_label = LENS_LABELS[request.lens]
    sections = "\n".join(f"- {section}" for section in SYNTHESIS_SECTIONS)
    context_blocks = []
    for index, source in enumerate(sources, start=1):
        context_blocks.append(
            f"[S{index}] {source.title} ({source.location or 'unknown location'})\n{source.excerpt}"
        )

    system_prompt = (
        "You are an executive strategy analyst synthesizing a private local book library. "
        "Use only the supplied excerpts as evidence. Write a concise, executive-ready Board Brief in Markdown. "
        "Cite evidence inline with source IDs like [S1] and [S2]. "
        "Do not invent claims that are not supported by the excerpts. "
        "Prioritize crisp decisions, risks, actions, and measurable indicators over long explanation."
    )
    user_prompt = (
        f"Objective:\n{request.objective.strip()}\n\n"
        f"Audience: {audience_label}\n"
        f"Lens: {lens_label}\n\n"
        "Return exactly these sections:\n"
        f"{sections}\n\n"
        "Formatting contract:\n"
        "- Executive Takeaway: one concise executive takeaway, no more than 90 words.\n"
        "- Cross-Book Themes: 3-5 cross-book themes as bullets.\n"
        "- Strategic Implications: 2-4 decision-relevant implications as bullets.\n"
        "- Risks, Tensions, and Blind Spots: clearly labeled risks as bullets.\n"
        "- Recommended 30/60/90 Day Actions: group actions under 30 Days, 60 Days, and 90 Days.\n"
        "- Metrics to Watch: 3-6 measurable executive indicators as bullets.\n"
        "- Source Notes: explain which sources most shaped the synthesis.\n"
        "Use [S#] citations on every evidence-based claim or bullet. "
        "Keep the language direct enough for a C-level briefing.\n\n"
        "Excerpts:\n\n"
        + "\n\n".join(context_blocks)
    )
    return system_prompt, user_prompt
