"""ALEMBIC LABS — autonomous AI laboratory backend.

Entry points:
- ``alembic_labs.main:app`` — FastAPI application served via uvicorn.
- ``alembic_labs.orchestrator.cycle:run_distillation_cycle`` — single
  end-to-end research cycle, also driven by APScheduler.
"""

__version__ = "0.1.0"
