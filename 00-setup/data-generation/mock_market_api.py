"""
Trilha Tech 2026 | CBA - API mock de mercado
============================================
Simula fontes externas citadas na reuniao (B3/LME para preco do aluminio e
Banco Central para o cambio USD/BRL). Usada na trilha de Engenharia para o
modulo de "ingestao via API".

Le os CSVs gerados por generate_synthetic_data.py (output/aluminum_lme_price.csv
e output/fx_usdbrl.csv) e os serve como JSON.

Subir local:
    pip install -r requirements.txt
    python generate_synthetic_data.py
    uvicorn mock_market_api:app --reload --port 8000

Endpoints:
    GET /aluminum/lme?start=2026-01-01&end=2026-03-31
    GET /fx/usdbrl?start=2026-01-01&end=2026-03-31
    GET /health
"""
from __future__ import annotations

from pathlib import Path

import polars as pl
from fastapi import FastAPI, Query

OUTPUT = Path(__file__).parent / "output"

app = FastAPI(
    title="CBA Market API (mock)",
    description="Preco do aluminio (LME) e cambio USD/BRL - dados sinteticos para a Trilha Tech 2026",
    version="1.0.0",
)


def _load(name: str) -> pl.DataFrame:
    path = OUTPUT / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} nao encontrado. Rode 'python generate_synthetic_data.py' primeiro."
        )
    return pl.read_csv(path)


def _filter(df: pl.DataFrame, start: str | None, end: str | None) -> list[dict]:
    if start:
        df = df.filter(pl.col("date") >= start)
    if end:
        df = df.filter(pl.col("date") <= end)
    return df.to_dicts()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/aluminum/lme")
def aluminum_lme(
    start: str | None = Query(None, description="data inicial YYYY-MM-DD"),
    end: str | None = Query(None, description="data final YYYY-MM-DD"),
) -> dict:
    df = _load("aluminum_lme_price")
    rows = _filter(df, start, end)
    return {"source": "LME (mock)", "unit": "USD/ton", "count": len(rows), "data": rows}


@app.get("/fx/usdbrl")
def fx_usdbrl(
    start: str | None = Query(None, description="data inicial YYYY-MM-DD"),
    end: str | None = Query(None, description="data final YYYY-MM-DD"),
) -> dict:
    df = _load("fx_usdbrl")
    rows = _filter(df, start, end)
    return {"source": "Banco Central (mock)", "pair": "USD/BRL", "count": len(rows), "data": rows}
