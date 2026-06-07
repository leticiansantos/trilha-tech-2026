# 02 · MLOps na prática

**Trilha Tech 2026 | Workshop Hands-on: MLOps na prática** — Ciência de Dados, MLOps e Agentes, ~4h.

Seguindo o ciclo **CRISP-DM**, partir das tabelas `gold`, prever falha/eficiência do forno (uma
**regressão** + uma **classificação binária**) e construir um **agente de RCA** de manutenção. Use o
**Genie Code** em todos os passos.

## Antes de começar
Ambiente provisionado (ver [`../00-setup/`](../00-setup/)). Use um cluster com **Runtime ML**.
Confirme um Foundation Model disponível para o módulo 07 (agente).

## Apostila
Leia o [`workbook.md`](workbook.md) — passo a passo, prompts de Genie Code, checkpoints e exercícios.

## Notebooks (ordem)
| # | Notebook | Tema |
|---|---|---|
| 01 | `notebooks/01_eda.py` | EDA (CRISP-DM): correlações, nulos, distribuição dos labels |
| 02 | `notebooks/02_feature_engineering.py` | Feature Engineering no Unity Catalog |
| 03 | `notebooks/03_train_regression.py` | Regressão: prever `energy_kwh_ton` (eficiência) |
| 04 | `notebooks/04_automl_classification.py` | Classificação `is_defect` via AutoML |
| 05 | `notebooks/05_mlflow_registry_champion.py` | MLflow + Model Registry UC (champion/challenger) |
| 06 | `notebooks/06_model_serving_ai_query.py` | Model Serving + inferência via `ai_query()` |
| 07 | `notebooks/07_rca_agent.py` | Agente de RCA (Mosaic AI Agent Framework + Vector Search) |
