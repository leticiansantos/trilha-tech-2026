"""
Trilha Tech 2026 | CBA - API mock de mercado (Databricks App)
=============================================================
Serve os dados de preco do aluminio (LME) e cambio (USD/BRL)
lendo diretamente do Volume Unity Catalog raw.landing via SDK.
-- atualização
Endpoints:
    GET /aluminum/lme?start=2026-01-01&end=2026-03-31
    GET /fx/usdbrl?start=2026-01-01&end=2026-03-31
    GET /health
"""
from __future__ import annotations

import io
import polars as pl
from fastapi import FastAPI, Query
from databricks.sdk import WorkspaceClient

# Inicializa o cliente do SDK (se autentica automaticamente dentro do Databricks App)
w = WorkspaceClient()

# Caminho absoluto do Volume no Unity Catalog
VOLUME_PATH = "/Volumes/cba_workshop_trilha_tech/raw/landing"

app = FastAPI(
    title="CBA Market API (mock)",
    description="Preco do aluminio (LME) e cambio USD/BRL - Trilha Tech 2026",
    version="1.0.0",
)


def _load(name: str) -> pl.DataFrame:
    file_path = f"{VOLUME_PATH}/{name}.csv"
    try:
        # Baixa o streaming do arquivo do Volume utilizando o SDK oficial
        response = w.files.download(file_path)
        # Lê o conteúdo binário em memória diretamente com o Polars
        return pl.read_csv(io.BytesIO(response.contents.read()))
    except Exception as e:
        raise FileNotFoundError(
            f"Erro ao acessar {file_path} via Databricks SDK: {str(e)}. "
            "Verifique as permissões de READ VOLUME do App."
        )


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