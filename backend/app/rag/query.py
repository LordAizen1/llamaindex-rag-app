"""Retrieval + grounded generation with streaming and citations."""
from dataclasses import dataclass, field
from typing import Iterator

from llama_index.core import get_response_synthesizer
from llama_index.core.prompts import PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.schema import NodeWithScore

from ..config import get_settings
from .index import configure_models, get_index, token_counter

NOT_FOUND_MESSAGE = "I couldn't find that in the provided documents."

QA_PROMPT = PromptTemplate(
    "You are a careful assistant answering questions strictly from the provided context.\n"
    "Rules:\n"
    "1. Use ONLY the context below. Do not use prior knowledge.\n"
    f'2. If the context does not contain the answer, reply exactly: "{NOT_FOUND_MESSAGE}"\n'
    "3. Be concise and cite specifics from the context.\n\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Question: {query_str}\n"
    "Answer: "
)


@dataclass
class RetrievalResult:
    nodes: list[NodeWithScore]
    stream: Iterator[str] = field(default_factory=lambda: iter(()))

    def citations(self) -> list[dict]:
        out = []
        for nws in self.nodes:
            md = nws.node.metadata or {}
            out.append(
                {
                    "source": md.get("source", "unknown"),
                    "page": md.get("page"),
                    "section": md.get("section"),
                    "score": round(float(nws.score), 4) if nws.score is not None else None,
                    "text": nws.node.get_content(),
                }
            )
        return out


def retrieve(question: str, top_k: int | None = None) -> list[NodeWithScore]:
    s = get_settings()
    configure_models()
    retriever = VectorIndexRetriever(index=get_index(), similarity_top_k=top_k or s.top_k)
    return retriever.retrieve(question)


def answer_stream(question: str, top_k: int | None = None) -> RetrievalResult:
    """Retrieve first (so citations are known up front), then stream the answer.

    Token usage is captured via the global TokenCountingHandler and can be read
    from `token_counter` after the stream is exhausted.
    """
    token_counter.reset_counts()
    nodes = retrieve(question, top_k)

    if not nodes:
        # Empty retrieval: don't call the LLM, return the explicit not-found line.
        return RetrievalResult(nodes=[], stream=iter([NOT_FOUND_MESSAGE]))

    synthesizer = get_response_synthesizer(streaming=True, text_qa_template=QA_PROMPT)
    streaming_response = synthesizer.synthesize(question, nodes)
    return RetrievalResult(nodes=nodes, stream=streaming_response.response_gen)


def token_usage() -> dict:
    return {
        "prompt_tokens": token_counter.prompt_llm_token_count,
        "completion_tokens": token_counter.completion_llm_token_count,
        "total_tokens": token_counter.total_llm_token_count,
        "embedding_tokens": token_counter.total_embedding_token_count,
    }
