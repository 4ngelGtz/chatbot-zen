# Phase 2 – YouTube Transcripts Ingestion

### 1) Create your env
```bash
cp .env.example .env
# edit .env and set CHANNEL_URL to: https://www.youtube.com/@BuddhasWizdom/videos
```

### 2) Install
```bash
make install
```

### 3) Fetch transcripts
```bash
make fetch
# outputs:
# - data/videos.json
# - data/raw_transcripts/<video_id>.json
# - data/transcripts.jsonl
```

### 4) Build LangChain documents / corpus
```bash
make build-docs
# outputs:
# - data/chunks/langchain_docs.jsonl    (one JSON per line: {page_content, metadata})
# - data/chunks/corpus.jsonl            (id, text) generic format
```

> Tip: While iterating, set MAX_VIDEOS in `.env` to a small number (e.g., 10) to go faster.
