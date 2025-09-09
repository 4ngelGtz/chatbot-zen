.PHONY: install fetch build-docs clean

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

fetch:
	. .venv/bin/activate && python -m src.fetch_transcripts

build-docs:
	. .venv/bin/activate && python -m src.make_langchain_docs

clean:
	rm -rf data/raw_transcripts/*.json data/transcripts.jsonl data/chunks/*.jsonl
