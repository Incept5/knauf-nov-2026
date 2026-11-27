#!/usr/bin/env python3
"""The whole of RAG in one short file: chunk Alice in Wonderland, embed the chunks, find the closest ones, ask the model.

    export INCEPT5_API_KEY=...
    python3 rag_alice_simple.py                    # runs on the cluster   (pip install numpy)

It prints how long each step takes.
"""
import numpy as np
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))     # llm.py: URLs and models are set there
sys.path.insert(0, str(HERE.parent / "knowledge"))  # rag_lib.py: the embeddings call
sys.dont_write_bytecode = True
from llm import chat  # noqa: E402
from rag_lib import QUERY_PREFIX, embed  # noqa: E402

BACKEND = sys.argv[sys.argv.index("--backend") + 1] if "--backend" in sys.argv else None


def get_embeddings(texts, task_type="document"):
    # Qwen embedding models want an instruction prefix on questions, not on documents
    if task_type == "query":
        texts = [QUERY_PREFIX + t for t in texts]
    return [np.array(v) for v in embed(texts, BACKEND)]     # one request for up to 64 texts


def chunk_text(text, chunk_size=250, overlap=50):
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'])', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    chunks = []
    current_chunk = []
    word_count = 0

    for sentence in sentences:
        words = len(sentence.split())

        if word_count + words > chunk_size and word_count > 0:
            chunks.append(" ".join(current_chunk))
            overlap_text = " ".join(current_chunk)
            overlap_words = overlap_text.split()[-overlap:]
            current_chunk = [" ".join(overlap_words)]
            word_count = len(overlap_words)

        current_chunk.append(sentence)
        word_count += words

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def query_rag(question, chunks, embeddings, top_k=6):
    start = time.time()
    query_emb = get_embeddings([question], "query")[0]

    scores = [cosine_similarity(query_emb, emb) for emb in embeddings]
    top_indices = np.argsort(scores)[-top_k:][::-1]

    searched = time.time() - start
    print(f"Q: {question}\n")
    print("Top matches:")
    for i, idx in enumerate(top_indices, 1):
        preview = chunks[idx][:80].replace('\n', ' ') + "..."
        print(f"  {i}. Chunk {idx:03d} | Score: {scores[idx]:.4f} | \"{preview}\"")
    print()

    context = "\n\n".join([f"[{i}] {chunks[idx]}" for i, idx in enumerate(top_indices, 1)])

    prompt = f"""Answer the question using the context below. Be specific and quote relevant text.

Question: {question}

Context:
{context}

Answer:"""

    start = time.time()
    answer = chat(prompt, backend=BACKEND, max_tokens=1200, temperature=0.05)
    answered = time.time() - start

    print(f"A: {answer}\n")
    print(f"[search {searched:.2f}s, answer {answered:.2f}s]")
    print("-" * 70)
    return answer


def main():
    print("Simple RAG Demo - Alice in Wonderland\n")

    with open(HERE / "data" / "alice_in_wonderland.txt", 'r', encoding='utf-8') as f:
        text = f.read()

    text = re.sub(r'\r\n', '\n', text)
    match = re.search(r'CHAPTER I\.\s*\n\s*[\w\s-]+\n\s*\n', text)
    if match:
        text = text[match.end():]

    print("Creating chunks...")
    chunks = chunk_text(text)
    print(f"Created {len(chunks)} chunks\n")

    print("Generating embeddings...")
    start = time.time()
    embeddings = get_embeddings(chunks)
    took = time.time() - start
    print(f"Done! {len(chunks)} chunks embedded in {took:.2f}s ({len(chunks) / took:.0f} chunks/s)\n")
    print("-" * 70)

    questions = [
        "What was Alice doing at the beginning of the story?",
        "What was written on the bottle that made Alice shrink?",
        "Where was the Cheshire Cat when Alice first met him?",
        "What did the White Rabbit say when Alice first saw him?",
    ]

    start = time.time()
    for question in questions:
        query_rag(question, chunks, embeddings)
    print(f"{len(questions)} questions in {time.time() - start:.2f}s")


if __name__ == "__main__":
    main()
