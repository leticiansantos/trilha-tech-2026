# 03 · Geração de Insights

**Trilha Tech 2026 | Workshop Hands-on: Geração de Insights** — Analista de Dados, ~4h.

Partir das tabelas `gold`/fatos e responder perguntas de negócio (produção, custo, mercado, margem,
qualidade) com **Databricks SQL**, **Metric Views**, **AI/BI Dashboards** e **AI/BI Genie** (em
português). Princípio: dashboard **"farol"** — entregar o insight direto, não despejar colunas.

## Antes de começar
Ambiente provisionado (ver [`../00-setup/`](../00-setup/)). SQL Warehouse (serverless), AI/BI
Dashboards e Genie habilitados.

## Apostila
Leia o [`workbook.md`](workbook.md) — passo a passo, prompts de Assistant/Genie, a seção
"Power BI ↔ Databricks", checkpoints e exercícios.

## Roteiro (ordem)
| # | Arquivo | Tema |
|---|---|---|
| 01 | `notebooks/01_sql_explore.sql` | DBSQL + Databricks Assistant (gerar/explicar/corrigir SQL) |
| 02 | `notebooks/02_metric_views.sql` | Camada semântica com UC Metric Views (custo, margem, OEE) |
| 03 | `notebooks/03_aibi_dashboard.md` | Construir o AI/BI Dashboard "farol" (guia passo a passo) |
| 04 | `notebooks/04_genie_space.md` | Criar o AI/BI Genie space em português (guia passo a passo) |
| 05 | `notebooks/05_capstone.md` | Capstone por domínio + rubrica de avaliação |
