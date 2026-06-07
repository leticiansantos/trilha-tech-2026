# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Auto Loader → Camada Bronze
# MAGIC ### Ingerindo a telemetria COMPLETA do Gorila de forma incremental
# MAGIC
# MAGIC No módulo anterior subimos **um** CSV pequeno. No mundo real, o Gorila despeja arquivos
# MAGIC **continuamente** na área de pouso. Reprocessar tudo a cada execução é caro e lento.
# MAGIC
# MAGIC O **Auto Loader** (`cloudFiles`) resolve isso: ele **detecta só os arquivos novos** desde a última
# MAGIC execução, mantém um **checkpoint**, e lida com **evolução de schema** (quando aparece uma coluna nova).
# MAGIC O resultado vai para a tabela **bronze**: cópia fiel do dado bruto + metadados de ingestão.
# MAGIC
# MAGIC **Contexto CBA:** bronze = "tudo que o Gorila mandou, sem julgar". Limpeza vem depois (módulo 03).
# MAGIC
# MAGIC > 💬 Lembre-se: você pode pedir TODO este código ao Assistant em português e só revisar.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Configuração padrão

# COMMAND ----------

CATALOG = "cba_trilha_tech"
RAW_SCHEMA = "raw"
username = spark.sql("SELECT current_user()").collect()[0][0]
user_schema = "ws_" + username.split("@")[0].replace(".", "_").replace("-", "_")

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{user_schema}")
spark.sql(f"USE SCHEMA {user_schema}")

LANDING = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/landing"
# Cada aluno tem seu próprio Volume de checkpoint/schema, isolado no seu schema pessoal
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{user_schema}.checkpoints")
CHECKPOINT_BASE = f"/Volumes/{CATALOG}/{user_schema}/checkpoints"
print(f"Origem (telemetria): {LANDING}")
print(f"Checkpoints em ....: {CHECKPOINT_BASE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A fonte: a telemetria completa
# MAGIC O Auto Loader monitora um caminho. Vamos apontar para o CSV completo da telemetria do Gorila.
# MAGIC (Em produção apontaríamos para uma *pasta* onde caem vários arquivos; aqui o efeito é o mesmo.)

# COMMAND ----------

SOURCE_PATH = f"{LANDING}/furnace_telemetry.csv"
SCHEMA_LOCATION = f"{CHECKPOINT_BASE}/telemetry_bronze/_schema"
CHECKPOINT_LOCATION = f"{CHECKPOINT_BASE}/telemetry_bronze/_checkpoint"
BRONZE_TABLE = "telemetry_bronze"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Montar o stream do Auto Loader
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Use o Auto Loader (cloudFiles) para ler em streaming os CSVs de telemetria
# MAGIC > em formato CSV com cabeçalho, salvando a localização do schema, e adicione uma coluna com o nome
# MAGIC > do arquivo de origem e o horário de ingestão."*
# MAGIC
# MAGIC As opções que importam:
# MAGIC - `cloudFiles.format` = `csv` → o formato bruto.
# MAGIC - `cloudFiles.schemaLocation` → onde o Auto Loader guarda o schema que descobriu (e evolui).
# MAGIC - `cloudFiles.schemaEvolutionMode = addNewColumns` → se aparecer coluna nova, ele a adiciona.
# MAGIC - `_metadata.file_name` e `current_timestamp()` → rastreabilidade (de onde veio, quando entrou).

# COMMAND ----------

from pyspark.sql.functions import current_timestamp, col

bronze_stream = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("header", True)
    .option("cloudFiles.schemaLocation", SCHEMA_LOCATION)
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    .option("cloudFiles.inferColumnTypes", True)
    .load(SOURCE_PATH)
    .withColumn("_arquivo_origem", col("_metadata.file_name"))
    .withColumn("_ingestao_ts", current_timestamp())
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Gravar na tabela bronze (com checkpoint)
# MAGIC O `checkpointLocation` é o "marcador de página": guarda o que já foi lido. Se você rodar de novo,
# MAGIC nada é reprocessado. Usamos `trigger(availableNow=True)` para processar **tudo que existe agora e parar**
# MAGIC (modo *batch incremental* — perfeito para workshop; em produção poderia rodar contínuo).

# COMMAND ----------

(
    bronze_stream.writeStream
    .format("delta")
    .option("checkpointLocation", CHECKPOINT_LOCATION)
    .option("mergeSchema", True)
    .trigger(availableNow=True)
    .toTable(BRONZE_TABLE)
)

# Espera o micro-batch terminar antes de seguir
for q in spark.streams.active:
    q.awaitTermination()

print(f"✅ Ingestão concluída em {BRONZE_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Conferir a bronze

# COMMAND ----------

bronze = spark.read.table(BRONZE_TABLE)
print(f"Linhas na bronze: {bronze.count():,}")
bronze.select("furnace_id", "ts", "temperature_c", "energy_kwh_ton",
              "vibration_mm_s", "is_failure", "_arquivo_origem", "_ingestao_ts").show(5, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Demonstração do incremental
# MAGIC Rode a célula de gravação (passo 3) **de novo**. Como o checkpoint já registrou o arquivo,
# MAGIC **nenhuma linha nova** é processada — a contagem fica igual. Esse é o ganho do Auto Loader.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Conte as linhas da tabela telemetry_bronze e diga quantos arquivos
# MAGIC > distintos de origem existem na coluna _arquivo_origem."*

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS linhas,
# MAGIC        COUNT(DISTINCT _arquivo_origem) AS arquivos_origem
# MAGIC FROM telemetry_bronze;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Exercício
# MAGIC 1. Peça ao Assistant para ingerir também `furnace_inspections.csv` numa bronze `inspections_bronze`
# MAGIC    com seu próprio checkpoint (copie o padrão acima, mude o `SOURCE_PATH` e o nome da tabela).
# MAGIC 2. Confirme a contagem de linhas (~20 mil).
# MAGIC
# MAGIC > ⚠️ **Pegadinha clássica:** cada fonte precisa de um `schemaLocation` e `checkpointLocation`
# MAGIC > **diferentes**. Se reaproveitar a mesma pasta, o Auto Loader se confunde. Use `/fix` se der erro.

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - ~864 mil linhas em `telemetry_bronze` com as colunas `_arquivo_origem` e `_ingestao_ts`.
# MAGIC - Ao rodar a gravação de novo, a contagem **não muda** (incremental funcionando).
# MAGIC
# MAGIC **Próximo:** `03_medallion_silver_gold` — limpar a bronze e construir prata e ouro.
