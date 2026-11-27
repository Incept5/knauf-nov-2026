# Examples shown on the Day 2 slides

Everything runs on the Incept5 cluster: no model on your laptop.

```bash
export INCEPT5_API_KEY=...
pip install numpy chromadb                     # chromadb only for the last one
```

| Script | What | Needs |
|---|---|---|
| `rag_alice_simple.py` | **start here:** the whole of RAG in one short file, with timings | `numpy` |
| `rag_alice_in_wonderland_chromadb.py` | RAG over the book with cluster embeddings, vectors kept in a ChromaDB database | `numpy chromadb` |
| `data_extraction_ollama.py` | summarise a text and extract one thing (the slide shows the Ollama version) | nothing |
| `formatted_response_example.py` | ask for JSON in an exact format and parse it | nothing |

Text: *Alice's Adventures in Wonderland* by Lewis Carroll (public domain).
