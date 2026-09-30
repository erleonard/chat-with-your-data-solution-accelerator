"""Search provider ABC.

Every concrete search provider (`azure_search`, `pgvector`,
`integrated_vectorization` future) inherits from `BaseSearch`
and self-registers via `@registry.register("<key>")`.

Constructors take `AppSettings` so providers can read their own
endpoint / index / top_k defaults; data-plane authentication uses an
`AsyncTokenCredential` (managed identity in production, AzureCli in
local dev) -- never an API key (Hard Rule #2: no Key Vault, no shared
secrets).

`search(query, *, top_k=None, vector=None, filter=None)` returns
provider-agnostic `SearchResult` instances. Producers map their native
shape (search documents, pgvector rows) to `SearchResult` so the chat
pipeline and citation extractor consume one
stable type.

`merge_or_upload_documents(*, documents)` is the symmetric write
surface used by ingestion blueprints. Concrete providers override
with their native upsert (Azure Search SDK call / Postgres ON
CONFLICT UPDATE / etc.); the default body raises
`NotImplementedError` so a provider that forgets to implement fails
loudly at the ingestion call site rather than silently no-oping.
"""

from abc import ABC, abstractmethod
from typing import Any, Sequence

from azure.core.credentials_async import AsyncTokenCredential
from pydantic import BaseModel, ConfigDict, Field

from backend.core.providers.parsers.base import BaseParser
from backend.core.settings import AppSettings
from backend.core.types import SearchDocument, SearchResult


class SourceListing(BaseModel):
    """One indexed source as listed by the admin documents API.

    Returned by :meth:`BaseSearch.list_sources` and serialized as
    part of the ``GET /api/admin/documents`` response. ``source``
    matches the value used by :meth:`BaseSearch.delete_by_source` so
    the admin UI can round-trip list -> select -> delete without
    identifier translation.

    - ``source``: filename or URL the chunks were ingested under.
    - ``chunk_count``: number of indexed chunks for this source.
    - ``last_modified``: ISO-8601 timestamp of the most recent
      chunk, or ``None`` when the provider does not track per-chunk
      timestamps (Azure Search facet aggregation has no timestamp
      field, so the Azure-Search implementation always emits
      ``None`` here).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Filename or URL the chunks were ingested under.")
    chunk_count: int = Field(description="Number of indexed chunks for this source.")
    last_modified: str | None = Field(
        default=None,
        description=(
            "ISO-8601 timestamp of the most recent chunk, or null when the "
            "provider does not track per-chunk timestamps."
        ),
    )


def order_chunks(source: str, chunks: Sequence[SearchResult]) -> list[SearchResult]:
    """Sort ``chunks`` of one ``source`` into ingestion (page) order.

    Ingestion keys each chunk with
    ``BaseParser.make_chunk_id(source, index)``, so the original index is
    recovered by recomputing the key for ``0..len(chunks)-1``. Chunks whose
    key does not match (e.g. written by a different ingestion path) keep
    their relative order after the matched ones.
    """
    index_by_id = {
        BaseParser.make_chunk_id(source, index): index for index in range(len(chunks))
    }
    fallback = len(chunks)
    return sorted(chunks, key=lambda chunk: index_by_id.get(chunk.id, fallback))


class BaseSearch(ABC):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
    ) -> None:
        self._settings = settings
        self._credential = credential

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        use_semantic_search: bool | None = None,
        vector: Sequence[float] | None = None,
        filter_expression: str | None = None,
        sources: Sequence[str] | None = None,
    ) -> Sequence[SearchResult]:
        """Return search hits for the given query.

        - `query`: free-text query. Required even for pure-vector
          searches (used for hybrid scoring + semantic re-ranking).
        - `top_k`: max hits to return. None = provider default
          (`settings.search.top_k`).
        - `use_semantic_search`: per-call override for semantic
          re-ranking. None = provider default
          (`settings.search.use_semantic_search`). Providers without a
          semantic mode (pgvector) accept the flag and ignore it.
        - `vector`: optional dense embedding for hybrid / pure-vector
          retrieval. Providers that don't support vectors ignore it.
        - `filter_expression`: provider-specific filter (OData for
          azure_search, SQL fragment for pgvector). Pass-through; no
          parsing here. Named `filter_expression` to avoid shadowing
          the `filter()` builtin.
        - `sources`: optional document scope. When non-empty, only chunks
          whose source (the `title` field) exactly equals one of these
          values are returned. Provider-agnostic so callers never build
          OData / SQL themselves. None or empty = no scoping.
        """

    @abstractmethod
    async def delete_by_source(self, source: str) -> int:
        """Delete every indexed chunk whose source matches `source`.

        - `source`: the filename or URL ingestion stored on each chunk
          (mapped to the `title` field in both Azure Search and the
          pgvector schema).
        - Returns the count of chunks deleted. A return of 0 means no
          matching documents existed; the admin route maps that to a
          404 response.
        """

    async def list_sources(self) -> list[SourceListing]:
        """List every indexed source the provider currently holds.

        Read counterpart to :meth:`delete_by_source` -- the admin
        documents API surfaces this for the Delete Data UI so the
        operator can pick from existing sources rather than typing
        identifiers blind. ``source`` values in the returned
        listings round-trip back into :meth:`delete_by_source`
        without translation.

        Returns a ``list[SourceListing]`` ordered by ``source``
        (provider-implemented stable ordering keeps the UI grid
        deterministic). Empty list means the index is empty -- not
        an error.

        Default implementation raises ``NotImplementedError`` so a
        provider class that forgets to override the method fails at
        the admin route call site rather than silently returning an
        empty list (which would mislead the UI into showing 'no
        sources to delete' when the index actually contains data).
        Matches the same fail-loud contract as
        :meth:`merge_or_upload_documents`.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement list_sources; "
            "override on the concrete provider class."
        )

    async def list_chunks(self, source: str) -> list[SearchResult]:
        """Return every indexed chunk of ``source`` in document order.

        Full-document read used by synthesis: where :meth:`search`
        returns the top-k most relevant chunks, this returns all of them
        so a 100+ page document can be summarized end to end. Ordering is
        recovered from the deterministic chunk key (see
        :func:`order_chunks`), so no index schema field is required.

        Default implementation raises ``NotImplementedError`` (same
        fail-loud contract as :meth:`list_sources`).
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement list_chunks; "
            "override on the concrete provider class."
        )

    async def get_document_by_key(self, key: str) -> SearchResult | None:
        """Fetch a single indexed document by its primary key.

        By-key read counterpart to :meth:`search` -- where ``search``
        ranks hits for a query, this resolves one document whose key is
        already known. Used by citation enrichment to recover a
        friendly ``title`` / snippet for a source the orchestrator
        holds only as an opaque document key (the ``agent_framework``
        Knowledge Base path keys citations by the Search document id).

        - ``key``: the provider's primary-key value (Azure Search
          document key / pgvector ``id``).
        - Returns the matching :class:`SearchResult`, or ``None`` when
          no document with that key exists. ``None`` is a soft miss,
          not an error: a citation can reference a key that was since
          re-ingested or deleted, and enrichment must degrade to the
          raw id rather than fail the answer.

        Default implementation raises ``NotImplementedError`` so a
        provider class that forgets to override fails at the call site
        rather than silently skipping enrichment. Matches the same
        fail-loud contract as :meth:`list_sources` /
        :meth:`merge_or_upload_documents`.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_document_by_key; "
            "override on the concrete provider class."
        )

    async def merge_or_upload_documents(
        self,
        *,
        documents: Sequence[SearchDocument],
    ) -> list[Any]:
        """Upsert ingestion documents into the provider's index.

        Symmetric write counterpart to :meth:`search` /
        :meth:`delete_by_source`. Concrete providers override with
        their native upsert path (Azure Search SDK
        ``merge_or_upload_documents`` / Postgres
        ``ON CONFLICT (id) DO UPDATE`` / etc.); each implementation
        owns the ``SearchDocument`` -> wire-shape translation at its
        own SDK boundary (Hard Rule #15: the ingestion model is the
        source of truth; the dict/row passed to the SDK is a
        transport detail).

        Keyword-only ``documents`` matches the
        ``SupportsMergeOrUploadDocuments`` Protocol in
        :mod:`backend.core.providers.search.writer` so adapter sites
        and provider sites share one signature.

        Returns provider-specific result objects (Azure SDK
        ``IndexingResult``, asyncpg ``Record``, etc.) typed
        ``list[Any]`` per Hard Rule #11(a) boundary carve-out --
        callers that need a uniform success/failure shape build it on
        top of the raw return rather than forcing every backend into
        a synthetic envelope.

        Default implementation raises ``NotImplementedError`` so a
        provider class that forgets to override the method fails at
        the ingestion call site rather than silently dropping data.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement merge_or_upload_documents; "
            "override on the concrete provider class."
        )

    async def ensure_schema(self) -> None:
        """Bootstrap any index/table/extension the provider needs to serve.

        Called once per process by the lifespan wiring (backend
        startup) and once per blueprint invocation by the Functions
        ingestion path (idempotent on the concrete side). Lets
        providers that own a lazy schema -- pgvector creates
        ``documents`` + the HNSW index on first use -- self-bootstrap
        on a fresh deploy without an out-of-band DDL step.

        Default implementation is a **no-op**. Providers whose index
        is managed out-of-band (Azure Search index created by Bicep
        / admin tooling; future managed-vector services) inherit the
        default and require no override. Only providers that own
        their DDL override this method.

        Concrete overrides are responsible for their own idempotency
        (typically a ``_schema_ready`` flag guarded by
        :class:`asyncio.Lock` for single-flight under concurrent
        callers) and for wrapping SDK errors per Hard Rule #14.
        """
        return None

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default no-op."""
        return None
