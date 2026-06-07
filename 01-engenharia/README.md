# 01 · Engenharia na prática

**Trilha Tech 2026 | Workshop Hands-on: Engenharia na prática** — Engenheiro de Dados, ~4h.

Ingerir a telemetria dos fornos + dados de mercado, integrar por ID e transformar numa arquitetura
medalhão (bronze → silver → gold). Em cada passo, gere o código com o **Genie Code** e entenda o que
ele faz.

## Antes de começar
Ambiente provisionado (ver [`../00-setup/`](../00-setup/)) e este repositório clonado no workspace.

## Apostila
Leia o [`workbook.md`](workbook.md) — passo a passo, prompts de Genie Code, checkpoints e exercícios.

## Notebooks (ordem)
| # | Notebook | Tema |
|---|---|---|
| 00 | `notebooks/00_setup.py` | Acesso, catálogo/schema pessoal, Volume |
| 01 | `notebooks/01_upload_csv.py` | Subir e consumir um CSV (o básico) |
| 02 | `notebooks/02_autoloader_bronze.py` | Auto Loader → Bronze |
| 03 | `notebooks/03_medallion_silver_gold.py` | Medalhão Bronze→Silver→Gold (Delta, ACID, time travel) |
| 04 | `notebooks/04_join_by_id.py` | Integrar bases por ID (joins) |
| 05 | `notebooks/05_market_api_ingest.py` | Ingestão via API (mercado: LME + dólar) |
| 06 | `notebooks/06_dlt_pipeline.py` | Lakeflow Declarative Pipelines (DLT) + data quality |
| 07 | `notebooks/07_job_workflow.py` | Orquestração com Job/Workflow |
