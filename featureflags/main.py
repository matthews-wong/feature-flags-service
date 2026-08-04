"""REST API for managing and evaluating feature flags.

Endpoints:
  GET    /flags            list flags
  GET    /flags/{key}      fetch one flag
  PUT    /flags/{key}      create or replace a flag
  DELETE /flags/{key}      remove a flag
  POST   /evaluate         evaluate a flag for a user
  GET    /health           liveness probe

The app is built via ``create_app`` so tests can inject an in-memory store.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Response

from . import __version__
from .engine import evaluate
from .models import EvaluationRequest, EvaluationResponse, Flag
from .store import FlagNotFound, FlagStore

# Where the default (persistent) store reads/writes when no store is injected.
DEFAULT_DATA_PATH = os.environ.get("FEATUREFLAGS_DATA", "data/flags.json")


def create_app(store: FlagStore | None = None) -> FastAPI:
    """Build a FastAPI app bound to ``store`` (or a JSON-file store by default)."""

    active_store = store or FlagStore(Path(DEFAULT_DATA_PATH))
    app = FastAPI(
        title="Feature Flags Service",
        version=__version__,
        description="Boolean flags, percentage rollouts, and targeting rules.",
    )

    def get_store() -> FlagStore:
        return active_store

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/flags", response_model=List[Flag])
    def list_flags(s: FlagStore = Depends(get_store)) -> List[Flag]:
        return s.list()

    @app.get("/flags/{key}", response_model=Flag)
    def get_flag(key: str, s: FlagStore = Depends(get_store)) -> Flag:
        try:
            return s.get(key)
        except FlagNotFound:
            raise HTTPException(status_code=404, detail=f"Flag '{key}' not found")

    @app.put("/flags/{key}", response_model=Flag)
    def put_flag(key: str, flag: Flag, s: FlagStore = Depends(get_store)) -> Flag:
        if flag.key != key:
            raise HTTPException(
                status_code=400,
                detail=f"Body key '{flag.key}' does not match path '{key}'",
            )
        return s.upsert(flag)

    @app.delete("/flags/{key}", status_code=204, response_class=Response)
    def delete_flag(key: str, s: FlagStore = Depends(get_store)) -> Response:
        try:
            s.delete(key)
        except FlagNotFound:
            raise HTTPException(status_code=404, detail=f"Flag '{key}' not found")
        return Response(status_code=204)

    @app.post("/evaluate", response_model=EvaluationResponse)
    def evaluate_flag(
        req: EvaluationRequest, s: FlagStore = Depends(get_store)
    ) -> EvaluationResponse:
        try:
            flag = s.get(req.flag)
        except FlagNotFound:
            raise HTTPException(status_code=404, detail=f"Flag '{req.flag}' not found")
        enabled, reason = evaluate(flag, req.user, req.attributes)
        return EvaluationResponse(
            flag=req.flag, user=req.user, enabled=enabled, reason=reason
        )

    return app


# Module-level app for ``uvicorn featureflags.main:app``.
app = create_app()
