# Databricks notebook source
# MAGIC %md
# MAGIC # Trilha Tech 2026 | CBA — Setup da camada GOLD canônica
# MAGIC
# MAGIC Provisiona o ambiente das 3 trilhas: cria o catálogo `cba_trilha_tech`, os schemas
# MAGIC `raw` e `gold`, o Volume `raw.landing`, e **carrega os CSVs sintéticos como tabelas
# MAGIC Delta canônicas em `cba_trilha_tech.gold.*`**.
# MAGIC
# MAGIC - **Trilha 1 (Engenharia):** os alunos reconstroem a medalhão a partir do Volume `raw.landing`
# MAGIC   no seu schema pessoal (`ws_<user>`). Esta camada gold serve de gabarito.
# MAGIC - **Trilhas 2 (MLOps) e 3 (Insights):** consomem diretamente `cba_trilha_tech.gold.*`.
# MAGIC
# MAGIC Pré-requisito: os arquivos de `data-generation/output/` já devem estar no Volume
# MAGIC (o `deploy.sh` faz o upload). Rode este notebook uma vez, antes dos workshops.

# COMMAND ----------

# DBTITLE 1,Parâmetros
dbutils.widgets.text("catalog", "cba_trilha_tech", "Catálogo")
dbutils.widgets.text("catalog_location", "", "Storage location (deixe vazio para usar o default do metastore)")
CATALOG = dbutils.widgets.get("catalog")
CATALOG_LOCATION = dbutils.widgets.get("catalog_location").strip()
RAW_SCHEMA = "raw"
GOLD_SCHEMA = "gold"
VOLUME = "landing"
VOLUME_PATH = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/{VOLUME}"
print(f"Catálogo: {CATALOG} | Volume: {VOLUME_PATH}")
if CATALOG_LOCATION:
    print(f"Storage location: {CATALOG_LOCATION}")

# COMMAND ----------

# DBTITLE 1,Catálogo, schemas e Volume
existing_catalogs = [r.catalog for r in spark.sql("SHOW CATALOGS").collect()]
if CATALOG not in existing_catalogs:
    if CATALOG_LOCATION:
        spark.sql(f"CREATE CATALOG {CATALOG} MANAGED LOCATION '{CATALOG_LOCATION}'")
    else:
        spark.sql(f"CREATE CATALOG {CATALOG} MANAGED LOCATION ''")
    print(f"Catálogo {CATALOG} criado.")
else:
    print(f"Catálogo {CATALOG} já existe, pulando criação.")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{RAW_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{GOLD_SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{RAW_SCHEMA}.{VOLUME}")
print("Catálogo/schemas/Volume prontos.")

# COMMAND ----------

# DBTITLE 1,Conferir arquivos no Volume
files = dbutils.fs.ls(VOLUME_PATH)
for f in files:
    print(f.name, f.size)
assert any(f.name.startswith("furnace_telemetry") for f in files), \
    f"CSVs não encontrados em {VOLUME_PATH}. Rode deploy.sh para subir data-generation/output/."

# COMMAND ----------

# DBTITLE 1,Carregar CSVs como tabelas Delta canônicas em gold
# (nome_arquivo, nome_tabela) — telemetry vem do parquet (volume alto)
csv_tables = [
    ("dim_plantas.csv", "dim_plantas"),
    ("dim_ligas.csv", "dim_ligas"),
    ("dim_produtos.csv", "dim_produtos"),
    ("dim_fornos.csv", "dim_fornos"),
    ("aluminum_lme_price.csv", "aluminum_lme_price"),
    ("fx_usdbrl.csv", "fx_usdbrl"),
    ("furnace_inspections.csv", "furnace_inspections"),
    ("fact_production.csv", "fact_production"),
    ("fact_sales.csv", "fact_sales"),
]

for filename, table in csv_tables:
    df = (spark.read
          .option("header", True)
          .option("inferSchema", True)
          .csv(f"{VOLUME_PATH}/{filename}"))
    (df.write.format("delta").mode("overwrite")
       .option("overwriteSchema", True)
       .saveAsTable(f"{CATALOG}.{GOLD_SCHEMA}.{table}"))
    print(f"  ✓ {CATALOG}.{GOLD_SCHEMA}.{table}  ({df.count():,} linhas)")

# telemetria: usar o parquet (mais rápido) se existir; senão o CSV
telemetry_src = (f"{VOLUME_PATH}/furnace_telemetry.parquet"
                 if any(f.name == "furnace_telemetry.parquet" for f in files)
                 else f"{VOLUME_PATH}/furnace_telemetry.csv")
tdf = (spark.read.parquet(telemetry_src) if telemetry_src.endswith(".parquet")
       else spark.read.option("header", True).option("inferSchema", True).csv(telemetry_src))
(tdf.write.format("delta").mode("overwrite").option("overwriteSchema", True)
    .saveAsTable(f"{CATALOG}.{GOLD_SCHEMA}.furnace_telemetry"))
print(f"  ✓ {CATALOG}.{GOLD_SCHEMA}.furnace_telemetry  ({tdf.count():,} linhas)")

# COMMAND ----------

# DBTITLE 1,Permissões para a turma (leitura)
# Ajuste o grupo conforme o ambiente da CBA (ex.: 'account users' ou um grupo dedicado)
GROUP = "account users"
spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{GROUP}`")
spark.sql(f"GRANT USE SCHEMA, SELECT ON SCHEMA {CATALOG}.{GOLD_SCHEMA} TO `{GROUP}`")
spark.sql(f"GRANT READ VOLUME ON VOLUME {CATALOG}.{RAW_SCHEMA}.{VOLUME} TO `{GROUP}`")
# Para a Trilha 1, a turma precisa criar o schema pessoal:
spark.sql(f"GRANT USE SCHEMA, CREATE SCHEMA ON CATALOG {CATALOG} TO `{GROUP}`")
print("Permissões aplicadas.")

# COMMAND ----------

# DBTITLE 1,Validação final
print("Tabelas em gold:")
display(spark.sql(f"SHOW TABLES IN {CATALOG}.{GOLD_SCHEMA}"))
