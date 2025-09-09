\
import os, json
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm
from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter

DATA_DIR = Path("data")
CHUNKS_DIR = DATA_DIR / "chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def main():
    load_dotenv()
    source_path = DATA_DIR / "transcripts.jsonl"
    if not source_path.exists():
        raise SystemExit("Missing data/transcripts.jsonl. Run `make fetch` first.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""],
    )

    out_langchain = CHUNKS_DIR / "langchain_docs.jsonl"
    out_corpus = CHUNKS_DIR / "corpus.jsonl"  # simple id/text for generic embedding pipelines

    n_docs, n_chunks = 0, 0
    with out_langchain.open("w", encoding="utf-8") as w_docs, out_corpus.open("w", encoding="utf-8") as w_corpus:
        for rec in tqdm(iter_jsonl(source_path), desc="Chunking transcripts"):
            text = rec.get("text_full", "")
            if not text:
                continue
            # Split into chunks
            chunks = splitter.split_text(text)
            base_id = rec["video_id"]
            for i, ch in enumerate(chunks):
                doc = {
                    "page_content": ch,
                    "metadata": {
                        "source": "youtube",
                        "video_id": rec.get("video_id"),
                        "title": rec.get("title"),
                        "url": rec.get("url"),
                        "published_at": rec.get("published_at"),
                        "language": rec.get("language"),
                        "chunk_id": f"{base_id}:{i}",
                        "n_total_chunks": len(chunks),
                    },
                }
                w_docs.write(json.dumps(doc, ensure_ascii=False) + "\n")
                w_corpus.write(json.dumps({"id": doc["metadata"]["chunk_id"], "text": ch}, ensure_ascii=False) + "\n")
                n_chunks += 1
            n_docs += 1

    print(f"[DONE] Wrote {n_chunks} chunks from {n_docs} videos to:")
    print(f"  - {out_langchain}")
    print(f"  - {out_corpus}")

if __name__ == "__main__":
    main()
