# 00 · Setup do ambiente

Faça isto **uma vez**, antes dos workshops. Cria o catálogo `cba_trilha_tech`, gera os dados
sintéticos e carrega a camada `gold` que as trilhas consomem.

## Passo 1 — Gerar os dados (local)
```bash
cd data-generation
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python generate_synthetic_data.py        # cria CSVs/Parquet em output/
```
Detalhes e dicionário de dados em [`data-generation/README.md`](data-generation/README.md).

## Passo 2 — Provisionar no workspace
```bash
# autenticar o CLI no workspace de testes da CBA
databricks auth login --host https://<workspace-cba>.cloud.databricks.com

cd ../deployment
./deploy.sh <PROFILE> cba_trilha_tech     # sobe os dados, deploya o bundle e carrega a gold
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
