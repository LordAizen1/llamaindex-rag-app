"""ChromaDB + LlamaIndex index management.

Owns the persistent Chroma collection and the LlamaIndex objects layered on
top of it: model configuration, ingestion (with configurable chunking),
document listing and deletion.
"""
import os
from collections import defaultdict

import chromadb
from llama_index.core import Settings as LISettings
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.chroma import ChromaVectorStore

from ..config import get_settings
from .parsers import parse_file

_client: chromadb.ClientAPI | None = None
_index: VectorStoreIndex | None = None
token_counter = TokenCountingHandler()


def configure_models(chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
    """Wire OpenAI LLM + embeddings and chunking params into LlamaIndex globals."""
    s = get_settings()
    LISettings.llm = OpenAI(
        model=s.llm_model,
        api_key=s.openai_api_key,
        max_tokens=s.max_tokens,
        temperature=0.1,
    )
    LISettings.embed_model = OpenAIEmbedding(model=s.embed_model, api_key=s.openai_api_key)
    LISettings.chunk_size = chunk_size or s.chunk_size
    LISettings.chunk_overlap = chunk_overlap or s.chunk_overlap
    LISettings.callback_manager = CallbackManager([token_counter])


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        s = get_settings()
        os.makedirs(s.chroma_dir, exist_ok=True)
        _client = chromadb.PersistentClient(path=s.chroma_dir)
    return _client


def get_collection(name: str | None = None):
    s = get_settings()
    return get_client().get_or_create_collection(name or s.collection_name)


def get_index() -> VectorStoreIndex:
    """Return the singleton index bound to the persistent Chroma collection."""
    global _index
    if _index is None:
        configure_models()
        vector_store = ChromaVectorStore(chroma_collection=get_collection())
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        _index = VectorStoreIndex.from_vector_store(
            vector_store, storage_context=storage_context
        )
    return _index


def ingest_file(
    path: str,
    filename: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> int:
    """Parse -> chunk -> embed -> store. Returns the number of chunks indexed."""
    s = get_settings()
    configure_models(chunk_size, chunk_overlap)
    documents = parse_file(path, filename)
    splitter = SentenceSplitter(
        chunk_size=chunk_size or s.chunk_size,
        chunk_overlap=chunk_overlap or s.chunk_overlap,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    index = get_index()
    index.insert_nodes(nodes)
    return len(nodes)


def list_documents() -> list[dict]:
    """Aggregate stored chunks by source filename."""
    collection = get_collection()
    result = collection.get(include=["metadatas"])
    counts: dict[str, int] = defaultdict(int)
    file_types: dict[str, str] = {}
    for md in result.get("metadatas") or []:
        src = md.get("source", "unknown")
        counts[src] += 1
        if md.get("file_type"):
            file_types[src] = md["file_type"]
    return [
        {"source": src, "chunks": n, "file_type": file_types.get(src)}
        for src, n in sorted(counts.items())
    ]


def delete_document(source: str) -> int:
    """Delete all chunks belonging to a source. Returns chunks removed."""
    collection = get_collection()
    before = collection.get(where={"source": source}, include=[])
    ids = before.get("ids") or []
    if ids:
        collection.delete(where={"source": source})
    return len(ids)


def document_exists(source: str) -> bool:
    collection = get_collection()
    res = collection.get(where={"source": source}, include=[], limit=1)
    return bool(res.get("ids"))
