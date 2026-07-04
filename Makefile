.PHONY: help install test frontend ui ui-old demo clean format

help:
	@echo "🎯 Sentinel Guard — Makefile"
	@echo ""
	@echo "Commands:"
	@echo "  make install      Install environment + dependencies"
	@echo "  make test         Run pytest (175 tests expected)"
	@echo "  make frontend     Run new chat UI (http://localhost:8770)"
	@echo "  make ui           Run original demo (http://localhost:8765)"
	@echo "  make demo         install + test + report status"
	@echo "  make clean        Remove venv, caches, artifacts"
	@echo ""
	@echo "Pipeline structure:"
	@echo "  src/sentinel_guard/"
	@echo "    ├── _1_decomposition/     (llm, orchestration)"
	@echo "    ├── _2_coverage/          (coverage check)"
	@echo "    ├── _3_retrieval/         (moulineuse, data.gouv, files)"
	@echo "    ├── _4_verification/      (verifier, normalization)"
	@echo "    ├── _5_triage/            (risk floor)"
	@echo "    ├── _6_validation/        (human validation, document)"
	@echo "    ├── _7_audit/             (compliance journal)"
	@echo "    ├── core_types/           (types, exceptions)"
	@echo "    ├── llm_providers/        (mistral, gemini, litellm)"
	@echo "    └── analysis/             (measurement, calibration)"

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[test]"
	@echo "✅ Environment ready. Activate with: source .venv/bin/activate"

test:
	. .venv/bin/activate && python -m pytest -q
	@echo "✅ Tests complete"

frontend:
	. .venv/bin/activate && python -m demarche.etape_2_front.server

ui:
	. .venv/bin/activate && python -m ui.server

demo: install test
	@echo ""
	@echo "✅ Build successful!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Activate env:     source .venv/bin/activate"
	@echo "  2. Set API key:      cp .env.example .env && edit .env"
	@echo "  3. New chat UI:      make frontend"
	@echo "  4. Original demo:    make ui"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .venv build dist .pytest_cache .coverage 2>/dev/null || true
	@echo "✅ Clean complete"

format:
	. .venv/bin/activate && black src/ tests/ demarche/ ui/ examples/ 2>/dev/null || echo "⚠️  black not installed (optional)"
