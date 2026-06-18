# 00 · Setup do ambiente

Faça isto **uma vez**, antes dos workshops. Cria o catálogo `cba_trilha_tech`, gera os dados
sintéticos e carrega a camada `gold` que as trilhas consomem.

## Pré-requisitos (instalar uma vez)

**macOS / Linux**
```bash
brew install databricks/tap/databricks   # Databricks CLI v0.2x+
brew install terraform                   # Terraform v1.0+  (necessário para bundle deploy)
# Python 3.10+ já deve estar instalado; se não: brew install python
```

**Windows (PowerShell como Administrador)**
```powershell
winget install Python.Python.3 Databricks.DatabricksCLI Hashicorp.Terraform
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned  # liberar scripts
```

## Passo 1 — Gerar os dados (local)

**macOS / Linux**
```bash
cd data-generation
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python generate_synthetic_data.py        # cria CSVs/Parquet em output/
```

**Windows (PowerShell)**
```powershell
cd data-generation
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python generate_synthetic_data.py
```

Detalhes e dicionário de dados em [`data-generation/README.md`](data-generation/README.md).

## Passo 2 — Provisionar no workspace

```bash
# autenticar o CLI (igual em todos os sistemas)
databricks auth login --host https://<workspace-cba>.cloud.databricks.com
```

**macOS / Linux**
```bash
cd ../deployment
./deploy.sh <PROFILE> cba_trilha_tech     # sobe os dados, deploya o bundle e carrega a gold
```

**Windows (PowerShell)**
```powershell
cd ..\deployment
.\deploy.ps1 <PROFILE> cba_trilha_tech
```

Detalhes e arquitetura de dados em [`deployment/README.md`](deployment/README.md).

## Arquitetura de dados (resumo)
```
cba_trilha_tech
├── raw.landing (Volume)   ← CSVs/Parquet (origem da Trilha 1)
├── gold.*                 ← camada canônica: Trilhas 2 e 3 consomem (gabarito da Trilha 1)
└── ws_<usuario>           ← schema pessoal de cada aluno (Trilha 1 constrói aqui)
```

## Validação
No workspace: `SHOW TABLES IN cba_trilha_tech.gold;` deve listar 11 tabelas.
