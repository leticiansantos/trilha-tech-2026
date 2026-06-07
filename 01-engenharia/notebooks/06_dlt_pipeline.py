# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Lakeflow Declarative Pipelines (DLT)
# MAGIC ### O mesmo medalhão, agora declarativo e com qualidade de dados
# MAGIC
# MAGIC Nos módulos 02–03 construímos bronze→prata→ouro **na mão** (cada `write`, cada checkpoint).
# MAGIC As **Lakeflow Declarative Pipelines** (o que era "DLT") deixam isso **declarativo**: você descreve
# MAGIC *o que* cada tabela é, com decorators `@dlt.table`, e o Lakeflow cuida da ordem de execução,
# MAGIC dos checkpoints, do incremental e da **qualidade** (`dlt.expect`).
# MAGIC
# MAGIC > ⚠️ **Importante:** este notebook **não roda célula a célula** como os outros. Ele é o **código-fonte
# MAGIC > de um pipeline**. Você o anexa a um Pipeline (instruções no fim) e o Lakeflow executa o grafo todo.
# MAGIC
# MAGIC **O que vamos declarar:**
# MAGIC - 🥉 `telemetry_bronze_dlt` — streaming table ingerindo o CSV com Auto Loader.
# MAGIC - 🥈 `telemetry_silver_dlt` — limpeza + tipagem + **expectativas** de qualidade.
# MAGIC - 🥇 `telemetry_gold_dlt` — materialized view com métricas por forno/dia.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F

# Parâmetro do pipeline (configurado nas Settings do pipeline). Default seguro abaixo.
LANDING = spark.conf.get("landing_path", "/Volumes/cba_trilha_tech/raw/landing")
SOURCE = f"{LANDING}/furnace_telemetry.csv"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🥉 Bronze — streaming table com Auto Loader
# MAGIC `@dlt.table` define uma tabela do pipeline. Como lemos com `readStream` + `cloudFiles`, ela é uma
# MAGIC **streaming table** (ingestão incremental). Não precisamos gerenciar checkpoint: o Lakeflow faz isso.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Escreva uma função DLT decorada com @dlt.table que usa Auto Loader (cloudFiles
# MAGIC > formato csv) para ler a telemetria de fornos e retornar o DataFrame de streaming."*

# COMMAND ----------

@dlt.table(
    name="telemetry_bronze_dlt",
    comment="Telemetria bruta do Gorila, ingerida incrementalmente via Auto Loader.",
    table_properties={"quality": "bronze"},
)
def telemetry_bronze_dlt():
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", True)
        .option("cloudFiles.inferColumnTypes", True)
        .load(SOURCE)
        .withColumn("_ingestao_ts", F.current_timestamp())
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🥈 Prata — limpeza + expectativas de qualidade
# MAGIC `dlt.expect_*` define **regras de qualidade**:
# MAGIC - `expect` → registra a violação nas métricas, mas **mantém** a linha (warning).
# MAGIC - `expect_or_drop` → **descarta** a linha que viola.
# MAGIC - `expect_or_fail` → **falha o pipeline** (use para invariantes críticas).
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Crie uma tabela DLT silver que lê a streaming table bronze, com expectativas:
# MAGIC > temperatura entre 800 e 1100 (descartar se violar), furnace_id não nulo (falhar se violar), e
# MAGIC > registre violações de vibração não nula sem descartar."*

# COMMAND ----------

@dlt.table(
    name="telemetry_silver_dlt",
    comment="Telemetria limpa e tipada, com regras de qualidade.",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("temperatura_plausivel", "temperature_c BETWEEN 800 AND 1100")
@dlt.expect_or_fail("forno_identificado", "furnace_id IS NOT NULL")
@dlt.expect("vibracao_presente", "vibration_mm_s IS NOT NULL")
def telemetry_silver_dlt():
    return (
        dlt.read_stream("telemetry_bronze_dlt")
        .withColumn("ts", F.col("ts").cast("timestamp"))
        .withColumn("furnace_id", F.col("furnace_id").cast("int"))
        .withColumn("temperature_c", F.col("temperature_c").cast("double"))
        .withColumn("energy_kwh_ton", F.col("energy_kwh_ton").cast("double"))
        .withColumn("vibration_mm_s", F.col("vibration_mm_s").cast("double"))
        .withColumn("anode_effect", F.col("anode_effect").cast("int"))
        .withColumn("is_failure", F.col("is_failure").cast("int"))
        .dropDuplicates(["furnace_id", "ts"])
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🥇 Ouro — materialized view com as métricas de negócio
# MAGIC Agregação por forno/dia. Como é uma agregação (não streaming append), declaramos uma
# MAGIC **materialized view** lendo a prata com `dlt.read`.

# COMMAND ----------

@dlt.table(
    name="telemetry_gold_dlt",
    comment="Métricas diárias por forno: energia, falha e OEE simplificado.",
    table_properties={"quality": "gold"},
)
def telemetry_gold_dlt():
    return (
        dlt.read("telemetry_silver_dlt")
        .withColumn("dia", F.to_date("ts"))
        .groupBy("furnace_id", "dia")
        .agg(
            F.round(F.avg("energy_kwh_ton"), 1).alias("energia_media_kwh_ton"),
            F.round(F.avg("temperature_c"), 2).alias("temp_media_c"),
            F.sum("anode_effect").alias("efeitos_anodicos"),
            F.count("*").alias("leituras"),
            F.round(F.avg("is_failure"), 4).alias("taxa_falha"),
        )
        .withColumn("oee_simplificado_pct", F.round((1 - F.col("taxa_falha")) * 100, 2))
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🛠️ Como criar e rodar este pipeline na UI
# MAGIC
# MAGIC 1. Menu lateral → **Jobs & Pipelines** → **Create** → **ETL pipeline** (Lakeflow Declarative).
# MAGIC 2. **Pipeline name:** `cba_engenharia_<seu_nome>`.
# MAGIC 3. **Source code:** aponte para **este notebook** (`06_dlt_pipeline`).
# MAGIC 4. **Destination:** Unity Catalog → **Catalog** `cba_trilha_tech`, **Schema** o seu (`ws_...`).
# MAGIC 5. Em **Configuration**, adicione o parâmetro:
# MAGIC    `landing_path` = `/Volumes/cba_trilha_tech/raw/landing`
# MAGIC 6. **Serverless** ligado (recomendado). Modo **Triggered** (roda e para).
# MAGIC 7. Clique **Start**. Acompanhe o **grafo**: bronze → silver → gold se desenham e processam sozinhos.
# MAGIC 8. Veja a aba **Data quality** — as expectativas mostram % de linhas que passaram/violaram.
# MAGIC
# MAGIC > 💬 **Genie Code:** dentro do editor de pipeline, o Assistant também ajuda. Peça
# MAGIC > *"adicione uma expectativa que descarta leituras com energy_kwh_ton negativa"* e veja o efeito.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exercício
# MAGIC 1. Adicione uma quarta tabela DLT que ingere `furnace_inspections.csv` e calcula a taxa de defeito
# MAGIC    por liga (junte com `dim_ligas` — pode lê-la com `spark.read`).
# MAGIC 2. Quebre uma expectativa de propósito (ex.: `expect_or_fail` impossível) e observe o pipeline falhar
# MAGIC    com mensagem clara. Depois conserte.
# MAGIC
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - O grafo do pipeline com 3 nós (bronze → silver → gold) verdes.
# MAGIC - As 3 tabelas `*_dlt` no seu schema.
# MAGIC - A aba **Data quality** com as expectativas (`temperatura_plausivel`, etc.).
# MAGIC
# MAGIC **Próximo:** `07_job_workflow` — orquestrar ingestão + pipeline num Job agendado.
