# Deployment — Trilha Tech 2026 CBA

Provisiona o ambiente de testes da CBA para os 3 workshops.

## Arquitetura de dados

```
cba_trilha_tech (catálogo)
├── raw
│   └── landing (Volume)         ← CSVs/Parquet sintéticos (origem da Trilha 1)
│       ├── *.csv, furnace_telemetry.parquet
│       └── sample/furnace_telemetry_sample.csv
├── gold                          ← camada CANÔNICA (gabarito) — Trilhas 2 e 3 consomem
│   ├── dim_plantas, dim_ligas, dim_produtos, dim_fornos
│   ├── furnace_telemetry, furnace_inspections
│   ├── aluminum_lme_price, fx_usdbrl
│   └── fact_production, fact_sales
└── ws_<usuario>                  ← schema pessoal de cada aluno (Trilha 1 constrói aqui)
```

- **Trilha 1 (Engenharia):** alunos leem `raw.landing` e constroem bronze→silver→gold no seu schema pessoal `ws_<user>`. A camada `gold` serve de gabarito/referência.
- **Trilhas 2 (MLOps) e 3 (Insights):** leem direto de `cba_trilha_tech.gold.*` (não dependem do output de cada aluno na Trilha 1).

## Passo a passo

```bash
# 1. gerar os dados
cd ../data-generation
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python generate_synthetic_data.py

# 2. autenticar o CLI no workspace de testes da CBA
databricks auth login --host https://<workspace-cba>.cloud.databricks.com

# 3. provisionar (cria catálogo/volume, sobe dados, deploya bundle, carrega gold)
cd ../deployment
./deploy.sh <PROFILE> cba_trilha_tech
```

Alternativa manual (sem o script): suba os arquivos de `data-generation/output/` para o
Volume `raw.landing` e rode o notebook `setup_load_gold.py` (ou `databricks bundle run setup_gold -t dev`).

## Validação

```bash
databricks bundle validate -t dev          # valida o bundle
# no workspace: SHOW TABLES IN cba_trilha_tech.gold;  (deve listar 11 tabelas)
```

## Recursos adicionais por trilha (provisionar antes de cada workshop)

- **Trilha 1:** SQL Warehouse (serverless), permissão de `CREATE SCHEMA` para a turma, pipeline DLT (criado na aula). API mock de mercado acessível pelo cluster (Databricks App ou plano B: ler CSVs do Volume).
- **Trilha 2:** cluster Runtime ML, Model Serving habilitado (quota), Foundation Model / pay-per-token, opcional Vector Search endpoint para o agente.
- **Trilha 3:** SQL Warehouse serverless, AI/BI Dashboards e Genie habilitados, permissões de leitura na `gold`.
