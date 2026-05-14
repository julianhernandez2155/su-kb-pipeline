"""sukb — SU Knowledge Base Pipeline (v1.5, Phase 1).

Four layers:
  - sukb.ingest: Confluence → canonical markdown
  - sukb.chat:   RAG over the corpus with Claude Sonnet 4.6
  - sukb.web:    FastAPI orchestration + UI
  - sukb.config: shared SyncConfig (used by all layers)
"""

__version__ = "0.1.0"
