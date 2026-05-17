from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from .search_document import SearchDocument


DEFAULT_SEARCH_LIMIT = 10
DEFAULT_EXCERPT_CHARS = 320
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    rank: int
    score: float
    document: SearchDocument
    matched_terms: tuple[str, ...]
    excerpt: str

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
            "excerpt": self.excerpt,
            "document": self.document.to_dict(),
        }


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in TOKEN_RE.finditer(text))


def retrieve_documents(
    query: str,
    documents: tuple[SearchDocument, ...] | list[SearchDocument],
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
) -> tuple[RetrievalResult, ...]:
    query_terms = tokenize(query)
    if not query_terms:
        return ()

    query_counts = Counter(query_terms)
    scored: list[tuple[float, SearchDocument, tuple[str, ...]]] = []
    document_frequencies = _document_frequencies(documents)
    total_documents = max(len(documents), 1)
    for document in documents:
        score, matched_terms = _score_document(document, query_counts, document_frequencies, total_documents)
        if score <= 0:
            continue
        scored.append((score, document, matched_terms))

    scored.sort(key=lambda item: (-item[0], _source_type_order(item[1].source_type), item[1].document_id))
    results: list[RetrievalResult] = []
    for rank, (score, document, matched_terms) in enumerate(scored[: max(limit, 0)], start=1):
        results.append(
            RetrievalResult(
                rank=rank,
                score=round(score, 6),
                document=document,
                matched_terms=matched_terms,
                excerpt=_build_excerpt(document.content, matched_terms, excerpt_chars=max(excerpt_chars, 80)),
            )
        )
    return tuple(results)


def _document_frequencies(documents: tuple[SearchDocument, ...] | list[SearchDocument]) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for document in documents:
        frequencies.update(set(tokenize(f"{document.title}\n{document.content}")))
    return frequencies


def _score_document(
    document: SearchDocument,
    query_counts: Counter[str],
    document_frequencies: Counter[str],
    total_documents: int,
) -> tuple[float, tuple[str, ...]]:
    title_counts = Counter(tokenize(document.title))
    content_counts = Counter(tokenize(document.content))
    source_boost = {
        "task_doc": 1.0,
        "artifact_snapshot": 1.15,
        "verification_claim": 1.25,
    }.get(document.source_type, 1.0)
    score = 0.0
    matched_terms: list[str] = []
    for term, query_count in sorted(query_counts.items()):
        occurrences = content_counts.get(term, 0) + (2 * title_counts.get(term, 0))
        if occurrences <= 0:
            continue
        inverse_document_frequency = math.log((1 + total_documents) / (1 + document_frequencies.get(term, 0))) + 1.0
        score += source_boost * query_count * (1 + math.log(occurrences)) * inverse_document_frequency
        matched_terms.append(term)
    return score, tuple(matched_terms)


def _build_excerpt(content: str, matched_terms: tuple[str, ...], *, excerpt_chars: int) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if len(normalized) <= excerpt_chars:
        return normalized

    lower = normalized.lower()
    first_match = min((lower.find(term) for term in matched_terms if lower.find(term) >= 0), default=0)
    start = max(first_match - (excerpt_chars // 3), 0)
    end = min(start + excerpt_chars, len(normalized))
    if end - start < excerpt_chars:
        start = max(end - excerpt_chars, 0)
    excerpt = normalized[start:end].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(normalized):
        excerpt = f"{excerpt}..."
    return excerpt


def _source_type_order(source_type: str) -> int:
    order = {
        "verification_claim": 0,
        "artifact_snapshot": 1,
        "task_doc": 2,
    }
    return order.get(source_type, 10)


__all__ = [
    "DEFAULT_EXCERPT_CHARS",
    "DEFAULT_SEARCH_LIMIT",
    "RetrievalResult",
    "retrieve_documents",
    "tokenize",
]
