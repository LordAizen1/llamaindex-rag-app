"""Evaluation harness.

Runs a fixed Q/A set against the sample documents across different chunking /
retrieval configurations and reports:

  * Retrieval hit rate  — did a chunk from the correct source containing an
                          expected keyword appear in the top-k?
  * Answer accuracy     — LLM-as-judge comparison of the generated answer
                          against the expected answer.
  * Avg latency         — wall-clock per query (retrieval + generation).

Because chunk size, overlap and top-k are configurable, the harness sweeps a
grid and prints a comparison table so the effect of each strategy is visible.

Usage (from the `backend/` directory):

    python -m app.eval.run_eval
    python -m app.eval.run_eval --chunk-sizes 256 512 1024 --overlaps 0 64 --top-k 3 5
    python -m app.eval.run_eval --json results.json
"""
import argparse
import json
import os
import time
from itertools import product

import chromadb
from llama_index.core import Settings as LISettings
from llama_index.core import StorageContext, VectorStoreIndex, get_response_synthesizer
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.prompts import PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.chroma import ChromaVectorStore
from tabulate import tabulate

from ..config import get_settings
from ..rag.parsers import parse_file
from ..rag.query import QA_PROMPT

HERE = os.path.dirname(__file__)
EVAL_SET_PATH = os.path.join(HERE, "eval_set.json")
EVAL_CHROMA_DIR = os.path.join(HERE, "_eval_chroma")

JUDGE_PROMPT = PromptTemplate(
    "You are grading a question-answering system.\n"
    "Question: {question}\n"
    "Reference answer: {expected}\n"
    "System answer: {actual}\n\n"
    "Does the system answer convey the same key facts as the reference answer? "
    "Minor wording differences are fine. Reply with exactly one word: YES or NO."
)


def load_eval_set() -> list[dict]:
    with open(EVAL_SET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def configure(settings) -> OpenAI:
    llm = OpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        max_tokens=settings.max_tokens,
        temperature=0,
    )
    LISettings.llm = llm
    LISettings.embed_model = OpenAIEmbedding(
        model=settings.embed_model, api_key=settings.openai_api_key
    )
    return llm


def build_index(client, chunk_size: int, overlap: int, settings) -> tuple[VectorStoreIndex, int]:
    coll_name = f"eval_cs{chunk_size}_co{overlap}"
    try:
        client.delete_collection(coll_name)
    except Exception:  # noqa: BLE001
        pass
    collection = client.get_or_create_collection(coll_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage = StorageContext.from_defaults(vector_store=vector_store)

    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    nodes = []
    for name in sorted(os.listdir(settings.samples_dir)):
        path = os.path.join(settings.samples_dir, name)
        if not os.path.isfile(path):
            continue
        docs = parse_file(path, name)
        nodes.extend(splitter.get_nodes_from_documents(docs))

    index = VectorStoreIndex(nodes, storage_context=storage)
    return index, len(nodes)


def retrieval_hit(nodes, item: dict) -> bool:
    keywords = [k.lower() for k in item["expected_keywords"]]
    for nws in nodes:
        md = nws.node.metadata or {}
        if md.get("source") != item["expected_source"]:
            continue
        text = nws.node.get_content().lower()
        if any(k in text for k in keywords):
            return True
    return False


def judge(llm, question: str, expected: str, actual: str) -> bool:
    prompt = JUDGE_PROMPT.format(question=question, expected=expected, actual=actual)
    verdict = llm.complete(prompt).text.strip().upper()
    return verdict.startswith("YES")


def run_config(client, chunk_size, overlap, top_k, eval_set, settings, llm) -> dict:
    index, n_chunks = build_index(client, chunk_size, overlap, settings)
    retriever = VectorIndexRetriever(index=index, similarity_top_k=top_k)
    synthesizer = get_response_synthesizer(text_qa_template=QA_PROMPT)

    hits = 0
    correct = 0
    latencies = []

    for item in eval_set:
        started = time.perf_counter()
        nodes = retriever.retrieve(item["question"])
        if retrieval_hit(nodes, item):
            hits += 1
        answer = str(synthesizer.synthesize(item["question"], nodes)) if nodes else ""
        latencies.append((time.perf_counter() - started) * 1000)
        if answer and judge(llm, item["question"], item["expected_answer"], answer):
            correct += 1

    total = len(eval_set)
    return {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "top_k": top_k,
        "chunks_indexed": n_chunks,
        "hit_rate": hits / total,
        "answer_accuracy": correct / total,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG chunking-strategy eval harness")
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=[256, 512, 1024])
    parser.add_argument("--overlaps", type=int, nargs="+", default=[64])
    parser.add_argument("--top-k", type=int, nargs="+", default=[3, 5])
    parser.add_argument("--json", type=str, default=None, help="Optional path to write raw results.")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Add it to backend/.env before running the eval.")

    llm = configure(settings)
    eval_set = load_eval_set()
    os.makedirs(EVAL_CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=EVAL_CHROMA_DIR)

    print(
        f"Running eval: {len(eval_set)} questions x "
        f"{len(args.chunk_sizes) * len(args.overlaps) * len(args.top_k)} configs\n"
    )

    results = []
    for chunk_size, overlap, top_k in product(args.chunk_sizes, args.overlaps, args.top_k):
        print(f"  -> chunk_size={chunk_size}, overlap={overlap}, top_k={top_k} ...")
        results.append(run_config(client, chunk_size, overlap, top_k, eval_set, settings, llm))

    results.sort(key=lambda r: (r["answer_accuracy"], r["hit_rate"]), reverse=True)

    table = [
        [
            r["chunk_size"],
            r["overlap"],
            r["top_k"],
            r["chunks_indexed"],
            f"{r['hit_rate'] * 100:.1f}%",
            f"{r['answer_accuracy'] * 100:.1f}%",
            f"{r['avg_latency_ms']:.0f}",
        ]
        for r in results
    ]
    print("\n" + tabulate(
        table,
        headers=["chunk", "overlap", "top_k", "#chunks", "hit_rate", "answer_acc", "latency(ms)"],
        tablefmt="github",
    ))

    best = results[0]
    print(
        f"\nBest config: chunk_size={best['chunk_size']}, overlap={best['overlap']}, "
        f"top_k={best['top_k']} "
        f"(hit_rate={best['hit_rate'] * 100:.1f}%, answer_acc={best['answer_accuracy'] * 100:.1f}%)"
    )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nRaw results written to {args.json}")


if __name__ == "__main__":
    main()
