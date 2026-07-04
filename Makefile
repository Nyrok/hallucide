# `make` tout court = lance la démo (front de chat). Voir `make help`.
.DEFAULT_GOAL := run
.PHONY: run help setup test frontend ui clean stop

# Python à utiliser : le .venv du projet s'il existe, sinon python3 système.
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

run: frontend   ## `make` = démarre le front de chat (http://localhost:8770)

stop:  ## Arrête un serveur front déjà lancé (libère le port)
	@pkill -f "demarche.etape_2_front.server" 2>/dev/null && echo "✅ ancien serveur arrêté" || echo "aucun serveur à arrêter"

frontend: stop  ## Front de chat futuriste (Claude par défaut)
	@echo "→ http://localhost:8770  (Ctrl+C pour arrêter)"
	@echo "  (clé : ANTHROPIC_API_KEY dans .env ; sinon « moteur non connecté »)"
	@sleep 1
	$(PY) -m demarche.etape_2_front.server

ui:  ## Démonstrateur historique (http://localhost:8765)
	$(PY) -m ui.server

test:  ## Lance pytest (195 tests attendus)
	$(PY) -m pytest -q

setup:  ## (1re fois seulement) crée .venv + installe les dépendances
	python3 -m venv .venv
	.venv/bin/pip install -e ".[test]"
	@echo "✅ Prêt. Colle ta clé dans .env, puis lance : make"

clean:  ## Nettoie caches et artefacts (garde .venv)
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf build dist .pytest_cache .coverage 2>/dev/null || true
	@echo "✅ Nettoyé"

help:  ## Affiche cette aide
	@echo "Sentinel Guard — commandes make :"
	@echo "  make          → lance la démo (front de chat, port 8770)"
	@echo "  make test     → 195 tests"
	@echo "  make ui       → démonstrateur historique (port 8765)"
	@echo "  make setup    → 1re installation (.venv + dépendances)"
	@echo "  make clean    → nettoie les caches"
	@echo ""
	@echo "Python utilisé : $(PY)"
	@echo "Avant la démo : colle ta clé dans .env (ANTHROPIC_API_KEY=...)"
