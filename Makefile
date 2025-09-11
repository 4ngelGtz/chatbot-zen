.PHONY: install reinstall ids transcripts clean retranscripts all check-python test test-enus clean-test-enus use-ytdlp-master use-ytdlp-release ytdlp-version

export PYTHONPATH := $(PWD)
export PIP_DISABLE_PIP_VERSION_CHECK=1
PY ?= python3.11
PIP ?= pip

# Verifica Python >= 3.10
check-python:
	@$(PY) -c 'import sys; import platform; ok=sys.version_info>=(3,10); print("Python", platform.python_version()); exit(0 if ok else 1)'
	@echo "✅ Python >= 3.10 detectado"

# Crear venv e instalar dependencias
install: check-python
	$(PY) -m venv .venv
	. .venv/bin/activate && $(PIP) install --upgrade pip && $(PIP) install -r requirements.txt
	@echo "✅ Entorno instalado"

# Reinstalar dependencias desde cero (útil si cambias versión de Python)
reinstall:
	rm -rf .venv
	$(MAKE) install

# Obtener listado de videos
ids:
	. .venv/bin/activate && $(PY) -m src.fetch_video_ids

# Descargar transcripts y corpus unificado
transcripts:
	. .venv/bin/activate && $(PY) -m src.fetch_transcripts

# Limpiar carpeta data
clean:
	rm -rf data/*
	mkdir -p data

# Limpiar y volver a descargar todos los transcripts
retranscripts: clean ids transcripts

# Correr todos los tests
test:
	. .venv/bin/activate && $(PY) -m pytest -q

# Test específico: en-US (con fallback a en)
test-enus:
	mkdir -p data/tests/enus
	. .venv/bin/activate && $(PY) -m pytest -q tests/test_transcripts_enus.py

# Limpia salidas del test en-US
clean-test-enus:
	rm -rf data/tests/enus/*

# Usar yt-dlp master
use-ytdlp-master:
	. .venv/bin/activate && $(PIP) install --upgrade "git+https://github.com/yt-dlp/yt-dlp@master#egg=yt-dlp" "brotlicffi>=1.1.0" "pycryptodomex>=3.20" "mutagen>=1.47"
	@echo "✅ yt-dlp (master) instalado en el venv"

# Restaurar yt-dlp desde requirements
use-ytdlp-release:
	. .venv/bin/activate && $(PIP) install --upgrade -r requirements.txt
	@echo "✅ yt-dlp de requirements restaurado"

# Mostrar versión activa de yt-dlp en el venv
ytdlp-version:
	. .venv/bin/activate && yt-dlp --version || true
	. .venv/bin/activate && yt-dlp --help | grep -E -- '--impersonate' && echo "Soporta --impersonate" || echo "No soporta --impersonate"
