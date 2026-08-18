# Deployment — Trilha Tech 2026 CBA

Provisiona o ambiente de testes da CBA para os 3 workshops.

## Arquitetura de dados

```
cba_workshop_trilha_tech (catálogo)
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
- **Trilhas 2 (MLOps) e 3 (Insights):** leem direto de `cba_workshop_trilha_tech.gold.*` (não dependem do output de cada aluno na Trilha 1).

## Pré-requisitos (instalar uma vez na máquina local)

### macOS / Linux

| Ferramenta | Instalação | Verificação |
|---|---|---|
| **Python 3.10+** | já instalado ou `brew install python` | `python3 --version` |
| **Databricks CLI v0.2x+** | `brew install databricks/tap/databricks` | `databricks --version` |
| **Terraform v1.0+** | `brew install terraform` | `terraform version` |

### Windows

| Ferramenta | Instalação | Verificação |
|---|---|---|
| **Python 3.10+** | `winget install Python.Python.3` | `python --version` |
| **Databricks CLI v0.2x+** | `winget install Databricks.DatabricksCLI` | `databricks --version` |
| **Terraform v1.0+** | `winget install Hashicorp.Terraform` | `terraform version` |

> **Por que Terraform?** O bundle deploy usa Terraform internamente. A versão embutida no CLI tem um problema de chave PGP expirada; o script usa o Terraform local como workaround.

## Passo a passo

### macOS / Linux

```bash
# 0. instalar pré-requisitos (se ainda não tiver)
brew install databricks/tap/databricks terraform

# 1. gerar os dados
cd ../data-generation
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python generate_synthetic_data.py

# 2. autenticar o CLI no workspace de testes da CBA
databricks auth login --host https://<workspace-cba>.cloud.databricks.com

# 3. provisionar (cria catálogo/volume, sobe dados, deploya bundle, carrega gold)
cd ../deployment
./deploy.sh <PROFILE> cba_workshop_trilha_tech
```

### Windows (PowerShell)

```powershell
# 0. instalar pré-requisitos (se ainda não tiver) — rodar como Administrador
winget install Python.Python.3 Databricks.DatabricksCLI Hashicorp.Terraform

# Liberar execução de scripts (rodar uma vez)
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 1. gerar os dados
cd ..\data-generation
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python generate_synthetic_data.py

# 2. autenticar o CLI no workspace de testes da CBA
databricks auth login --host https://<workspace-cba>.cloud.databricks.com

# 3. provisionar (cria catálogo/volume, sobe dados, deploya bundle, carrega gold)
cd ..\deployment
.\deploy.ps1 <PROFILE> cba_workshop_trilha_tech
```

### Parâmetro opcional: `CATALOG_LOCATION`

Por padrão, o catálogo é criado usando o **Default Storage** do metastore Unity Catalog. Se o metastore do workspace não tiver um storage root URL configurado, passe o caminho do cloud storage como 3º argumento:

```bash
# macOS/Linux — Azure Data Lake Storage
./deploy.sh <PROFILE> cba_workshop_trilha_tech "abfss://container@storageaccount.dfs.core.windows.net/cba"

# macOS/Linux — AWS S3
./deploy.sh <PROFILE> cba_workshop_trilha_tech "s3://bucket-name/cba"

# macOS/Linux — Google Cloud Storage
./deploy.sh <PROFILE> cba_workshop_trilha_tech "gs://bucket-name/cba"
```

```powershell
# Windows — Azure Data Lake Storage
.\deploy.ps1 <PROFILE> cba_workshop_trilha_tech "abfss://container@storageaccount.dfs.core.windows.net/cba"

# Windows — AWS S3
.\deploy.ps1 <PROFILE> cba_workshop_trilha_tech "s3://bucket-name/cba"

# Windows — Google Cloud Storage
.\deploy.ps1 <PROFILE> cba_workshop_trilha_tech "gs://bucket-name/cba"
```

> **Como saber se preciso?** Se o deploy falhar com `Metastore storage root URL does not exist`, é necessário passar o `CATALOG_LOCATION`. O caminho pode ser encontrado no workspace em **Settings → Unity Catalog → Storage credentials** ou com o admin da conta.

Alternativa manual (sem o script): suba os arquivos de `data-generation/output/` para o
Volume `raw.landing` e rode o notebook `setup_load_gold.py` com o parâmetro `catalog_location` preenchido se necessário (ou `databricks bundle run setup_gold -t dev --var=catalog_location=<path>`).

## Validação

```bash
databricks bundle validate -t dev          # valida o bundle
# no workspace: SHOW TABLES IN cba_workshop_trilha_tech.gold;  (deve listar 11 tabelas)
```

## Recursos adicionais por trilha (provisionar antes de cada workshop)

- **Trilha 1:** SQL Warehouse (serverless), permissão de `CREATE SCHEMA` para a turma, pipeline DLT (criado na aula). API mock de mercado acessível pelo cluster (Databricks App ou plano B: ler CSVs do Volume).
- **Trilha 2:** cluster Runtime ML, Model Serving habilitado (quota), Foundation Model / pay-per-token, opcional Vector Search endpoint para o agente.
- **Trilha 3:** SQL Warehouse serverless, AI/BI Dashboards e Genie habilitados, permissões de leitura na `gold`.
