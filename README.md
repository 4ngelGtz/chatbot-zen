# 📚 Chatbot-Zen

Chatbot-Zen is an **end-to-end Retrieval-Augmented Generation (RAG) demo** that ingests YouTube transcripts, indexes them with FAISS, and serves answers through a FastAPI backend. The project is modular, reproducible, and CI-ready.

---

## 🚀 Current Progress

### ✅ Phase 1 – Repo & Setup
- Project repository created.
- Professional README in English with roadmap and badges.
- Virtual environment managed with `make install` / `make reinstall`.

### ✅ Phase 2 – Data Ingestion
- **Video IDs** fetched via `src/fetch_video_ids.py`.
- **Transcripts** downloaded via `src/fetch_transcripts.py`:
  - Uses `yt-dlp` (with cookies and impersonation).
  - Prefers `en-US`, falls back to `en`, then translates to `en` with `youtube-transcript-api`.
  - Stores subtitles in `data/raw/subs/<VIDEO_ID>/Transcript [VIDEO_ID].<lang>.srt`.
  - Generates an index in `data/chunks/transcripts_index.jsonl`.
- **Problems fixed**:
  - 429 errors handled with retries, backoff, impersonation, and cookies.
  - Deterministic file names for stable indexing.

### ✅ Phase 3 – Backend RAG
- Core pipeline ready:
  - `src/utils.py`
  - `src/rag_pipeline.py` → FAISS + OpenAI/HF embeddings
  - `src/main.py` → FastAPI server
- Endpoints:
  - `GET /health` → `{status:"ok"}`
  - `POST /ask` → `{answer, sources, provider, top_k}`
- `.env` config for choosing embeddings/LLM providers.

### ✅ Testing & CI
- Unit test: `tests/test_transcripts_enus.py` ensures transcripts can be downloaded for a reference video.
- `make test` runs all tests.
- `make test-enus` runs the smoke test on a single video.
- GitHub Actions workflow (`.github/workflows/test.yml`) runs tests on every push/PR.

---

## 📂 Project Structure

```bash
chatbot-zen/
├── .github/
│   └── workflows/
│       └── test.yml              # CI workflow (pytest + yt-dlp master)
├── data/
│   ├── raw/
│   │   └── subs/                 # transcripts per video (srt files)
│   ├── chunks/
│   │   └── transcripts_index.jsonl
│   └── video_ids.jsonl           # list of video IDs (fetched)
├── src/
│   ├── fetch_video_ids.py        # fetch list of videos
│   ├── fetch_transcripts.py      # download transcripts for all videos
│   ├── make_langchain_docs.py    # (next) convert transcripts to LC docs
│   ├── rag_pipeline.py           # FAISS + embeddings pipeline
│   ├── utils.py                  # helper functions
│   └── main.py                   # FastAPI app
├── tests/
│   └── test_transcripts_enus.py  # transcript smoke test
├── .env                          # environment variables (providers, cookies, channel URL)
├── requirements.txt              # dependencies (yt-dlp, transcript API, dotenv, tqdm, pytest)
├── Makefile                      # build/test/clean tasks
└── README.md                     # this file


## 🛠️ Makefile Targets
make install          # create venv + install dependencies
make reinstall        # recreate venv from scratch
make ids              # fetch video IDs
make transcripts      # fetch transcripts for all videos
make retranscripts    # clean + re-fetch all transcripts
make clean            # clean data directory
make test             # run all tests
make test-enus        # run smoke test on reference video
make use-ytdlp-master # upgrade yt-dlp to latest master
make ytdlp-version    # check yt-dlp version and impersonation support



## 🛠️ Roadmap
- [x] Phase 1 – Repo setup & design  
- [x] Phase 2 – YouTube transcript ingestion  
- [ ] Phase 3 – RAG pipeline + FastAPI backend  
- [ ] Phase 4 – Dockerization & CI/CD  
- [ ] Phase 5 – Cloud deployment (GCP/Azure/AWS)  
- [ ] Phase 6 – Frontend integration (Streamlit/React)  
- [ ] Phase 7 – Monitoring & optimization  

---

## 📜 License
MIT License – free to use and adapt.
