"""Tests for source-scoped search and full-document chunk listing."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import pytest
from azure.core.exceptions import HttpResponseError

from backend.core.providers.parsers.base import BaseParser
from backend.core.providers.search.azure_search import (
    AzureSearch,
    build_title_scope_filter,
)
from backend.core.providers.search.base import order_chunks
from backend.core.providers.search.pgvector import PgVector
from backend.core.settings import (
    AppSettings,
    DatabaseSettings,
    OpenAISettings,
    SearchSettings,
)
from backend.core.types import SearchResult


class _FakeAsyncIter:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = list(items)

    def __aiter__(self) -> "_FakeAsyncIter":
        return self

    async def __anext__(self) -> dict[str, Any]:
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


def _settings(top_k: int = 2) -> AppSettings:
    s = MagicMock(spec=AppSettings)
    s.search = SearchSettings(top_k=top_k, use_semantic_search=False)
    s.database = DatabaseSettings(
        db_type="postgresql",
        index_store="pgvector",
        postgres_endpoint="postgresql://x:5432/cwyd?sslmode=require",
        postgres_admin_principal_name="id-cwyd001",
    )
    s.openai = OpenAISettings(embedding_dimensions=2)
    return s


def _doc(source: str, index: int, content: str = "c") -> dict[str, Any]:
    return {
        "id": BaseParser.make_chunk_id(source, index),
        "content": content,
        "title": source,
        "url": None,
    }


def _azure(docs: list[dict[str, Any]], top_k: int = 2) -> tuple[AzureSearch, MagicMock]:
    client = MagicMock()
    client.search = AsyncMock(return_value=_FakeAsyncIter(docs))
    return (
        AzureSearch(settings=_settings(top_k), credential=MagicMock(), client=client),
        client,
    )


def test_order_chunks_restores_ingestion_order() -> None:
    chunks = [
        SearchResult(id=BaseParser.make_chunk_id("a.pdf", i), content=str(i))
        for i in (2, 0, 1)
    ]
    ordered = order_chunks("a.pdf", chunks)
    assert [c.content for c in ordered] == ["0", "1", "2"]


def test_order_chunks_keeps_unknown_ids_last() -> None:
    chunks = [
        SearchResult(id="foreign", content="x"),
        SearchResult(id=BaseParser.make_chunk_id("a.pdf", 0), content="0"),
    ]
    assert [c.content for c in order_chunks("a.pdf", chunks)] == ["0", "x"]


def test_build_title_scope_filter_escapes_quotes() -> None:
    expr = build_title_scope_filter(["o'brien \"v2\".pdf", "b.docx"])
    assert expr == (
        "search.ismatch('\"o''brien \\\"v2\\\".pdf\"', 'title', 'simple', 'all')"
        " or search.ismatch('\"b.docx\"', 'title', 'simple', 'all')"
    )


@pytest.mark.asyncio
async def test_azure_search_scoped_overfetches_and_filters_exactly() -> None:
    handler, client = _azure(
        [
            _doc("report.pdf", 0),
            _doc("old report.pdf", 0),
            _doc("report.pdf", 1),
            _doc("report.pdf", 2),
        ]
    )
    results = await handler.search("q", vector=[0.1, 0.2], sources=["report.pdf"])
    kwargs = client.search.await_args.kwargs
    assert kwargs["top"] == 6
    assert kwargs["vector_queries"][0].k_nearest_neighbors == 6
    assert kwargs["filter"] == build_title_scope_filter(["report.pdf"])
    assert [r.title for r in results] == ["report.pdf", "report.pdf"]


@pytest.mark.asyncio
async def test_azure_search_combines_filter_expression_and_scope() -> None:
    handler, client = _azure([])
    await handler.search("q", filter_expression="x eq 1", sources=["a.pdf"])
    assert client.search.await_args.kwargs["filter"] == (
        f"(x eq 1) and ({build_title_scope_filter(['a.pdf'])})"
    )


@pytest.mark.asyncio
async def test_azure_search_empty_sources_is_unscoped() -> None:
    handler, client = _azure([])
    await handler.search("q", sources=[])
    kwargs = client.search.await_args.kwargs
    assert "filter" not in kwargs
    assert kwargs["top"] == 2


@pytest.mark.asyncio
async def test_azure_list_chunks_returns_exact_source_in_order() -> None:
    handler, client = _azure(
        [_doc("a.pdf", 1, "p2"), _doc("x a.pdf", 0), _doc("a.pdf", 0, "p1")]
    )
    chunks = await handler.list_chunks("a.pdf")
    assert [c.content for c in chunks] == ["p1", "p2"]
    assert client.search.await_args.kwargs["filter"] == build_title_scope_filter(
        ["a.pdf"]
    )


@pytest.mark.asyncio
async def test_azure_list_chunks_reraises_sdk_error() -> None:
    handler, client = _azure([])
    client.search = AsyncMock(side_effect=HttpResponseError("boom"))
    with pytest.raises(HttpResponseError):
        await handler.list_chunks("a.pdf")


def _pgvector(rows: list[dict[str, Any]]) -> tuple[PgVector, MagicMock]:
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=rows)
    return PgVector(settings=_settings(), credential=AsyncMock(), pool=pool), pool


@pytest.mark.asyncio
async def test_pgvector_scoped_vector_search_parameterizes_sources() -> None:
    handler, pool = _pgvector([])
    await handler.search("q", vector=[0.0, 1.0], sources=["b.pdf", "a.pdf"])
    sql, *params = pool.fetch.await_args.args
    assert "WHERE title = ANY($2::text[])" in sql
    assert sql.endswith("LIMIT $3")
    assert params[1] == ["a.pdf", "b.pdf"]
    assert params[2] == 2


@pytest.mark.asyncio
async def test_pgvector_scoped_text_search_parameterizes_sources() -> None:
    handler, pool = _pgvector([])
    await handler.search("q", sources=["a.pdf"])
    sql, *params = pool.fetch.await_args.args
    assert "AND title = ANY($2::text[])" in sql
    assert sql.endswith("LIMIT $3")
    assert params == ["q", ["a.pdf"], 2]


@pytest.mark.asyncio
async def test_pgvector_list_chunks_orders_rows() -> None:
    rows = [
        {**_doc("a.pdf", 1, "p2"), "url": ""},
        {**_doc("a.pdf", 0, "p1"), "url": ""},
    ]
    handler, pool = _pgvector(rows)
    chunks = await handler.list_chunks("a.pdf")
    assert [c.content for c in chunks] == ["p1", "p2"]
    assert pool.fetch.await_args.args[1] == "a.pdf"


@pytest.mark.asyncio
async def test_pgvector_list_chunks_reraises_postgres_error() -> None:
    handler, pool = _pgvector([])
    pool.fetch = AsyncMock(side_effect=asyncpg.PostgresError("boom"))
    with pytest.raises(asyncpg.PostgresError):
        await handler.list_chunks("a.pdf")
