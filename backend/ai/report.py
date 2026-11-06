"""Разбор ответа модели в строгую структуру отчёта.

Проверка не опирается на structured outputs провайдера: ответ приходит обычным
Markdown и валидируется здесь, поэтому работает с любой моделью.
"""

import re

from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.ai.client import AIResponseFormatError

RECOMMENDATIONS_COUNT = 5

# Заголовок секции в ответе и поле модели.
SECTION_FIELDS = {
    "общая оценка": "summary",
    "сильные стороны": "strengths",
    "проблемные зоны": "problems",
    "рекомендации": "recommendations",
    "лучший пост периода": "best_post_insight",
    "оптимальное время": "optimal_time",
    "прогноз": "forecast",
}
LIST_FIELDS = {"strengths", "problems", "recommendations"}

HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)")
NUMBERING_PATTERN = re.compile(r"^\d+[.)]\s*")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+(.+)")


class AuditReportSections(BaseModel):
    """Обязательная структура AI-отчёта."""

    summary: str = Field(min_length=1)
    strengths: list[str] = Field(min_length=2)
    problems: list[str] = Field(min_length=2)
    recommendations: list[str] = Field(
        min_length=RECOMMENDATIONS_COUNT,
        max_length=RECOMMENDATIONS_COUNT,
    )
    best_post_insight: str = Field(min_length=1)
    optimal_time: str = Field(min_length=1)
    forecast: str = Field(min_length=1)

    @field_validator("summary", "best_post_insight", "optimal_time", "forecast")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


def parse_report(text: str) -> AuditReportSections:
    """Превращает ответ модели в отчёт или объясняет, что в нём не так."""

    sections = _split_sections(text)
    data: dict[str, str | list[str]] = {}
    for heading, field in SECTION_FIELDS.items():
        if heading not in sections:
            continue
        body = sections[heading]
        data[field] = _list_items(body) if field in LIST_FIELDS else body

    try:
        return AuditReportSections.model_validate(data)
    except ValidationError as exc:
        raise AIResponseFormatError(_describe_problems(exc)) from exc


def _split_sections(text: str) -> dict[str, str]:
    """Разбивает Markdown по заголовкам, нормализуя их написание."""
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = _normalize_heading(heading.group(1))
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _normalize_heading(heading: str) -> str:
    cleaned = heading.strip().strip("*_:# ").lower()
    return NUMBERING_PATTERN.sub("", cleaned).strip()


def _list_items(section: str) -> list[str]:
    items = (LIST_ITEM_PATTERN.match(line) for line in section.splitlines())
    return [item.group(1).strip() for item in items if item]


def _describe_problems(error: ValidationError) -> str:
    headings = {field: heading.capitalize() for heading, field in SECTION_FIELDS.items()}
    problems: list[str] = []
    for issue in error.errors():
        heading = headings[str(issue["loc"][0])]
        if issue["type"] == "missing":
            problems.append(f"нет секции «{heading}»")
        elif str(issue["loc"][0]) == "recommendations":
            problems.append(f"в секции «{heading}» нужно ровно {RECOMMENDATIONS_COUNT} пунктов")
        else:
            problems.append(f"секция «{heading}» пустая или содержит слишком мало пунктов")
    return "; ".join(problems)
