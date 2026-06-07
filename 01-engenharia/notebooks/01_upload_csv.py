# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Como subir e consumir um CSV
# MAGIC ### "Como é que o cara sobe um CSV?" — o básico, do zero
# MAGIC
# MAGIC Este é **o módulo mais didático** do dia. Objetivo: tirar o medo. Vamos pegar **um CSV**,
# MAGIC entender o que ele é, lê-lo com Spark, deixar o Databricks **descobrir os tipos das colunas**,
# MAGIC e salvar como uma **tabela Delta** que dá para consultar em SQL — como se fosse uma tabela de banco.
# MAGIC
# MAGIC **Contexto CBA:** a sala de fornos exporta a telemetria do **Gorila** em CSV. Cada linha é uma
# MAGIC leitura de sensores de uma cuba eletrolítica (temperatura, amperagem, energia, vibração…).
# MAGIC
# MAGIC > 💡 Se travar na sintaxe, **não decore**: peça ao Assistant. Há um quadro 💬 **Genie Code**
# MAGIC > em cada passo. Use `/explain` para entender e `/fix` quando der erro vermelho.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Configuração padrão (rode primeiro)

# COMMAND ----------

CATALOG = "cba_trilha_tech"
RAW_SCHEMA = "raw"
username = spark.sql("SELECT current_user()").collect()[0][0]
user_schema = "ws_" + username.split("@")[0].replace(".", "_").replace("-", "_")

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{user_schema}")
spark.sql(f"USE SCHEMA {user_schema}")

LANDING = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/landing"
CSV_SAMPLE = f"{LANDING}/sample/furnace_telemetry_sample.csv"
print(f"Lendo amostra de: {CSV_SAMPLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. O que é um CSV, afinal?
# MAGIC CSV = *Comma-Separated Values*. Um arquivo de texto onde cada linha é um registro e as colunas
# MAGIC são separadas por vírgula. A **primeira linha** costuma ser o **cabeçalho** (os nomes das colunas).
# MAGIC
# MAGIC Vamos olhar as primeiras linhas **cruas**, como texto, antes de transformar em tabela.

# COMMAND ----------

with open(CSV_SAMPLE, "r") as f:
    for i, linha in enumerate(f):
        print(linha.rstrip())
        if i >= 4:  # cabeçalho + 4 linhas
            break

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Como subir o seu próprio CSV (passo a passo na UI)
# MAGIC Hoje o instrutor já subiu os arquivos, mas é assim que VOCÊ sobe um CSV no dia a dia:
# MAGIC
# MAGIC 1. Menu lateral → **Catalog**.
# MAGIC 2. Navegue até `cba_trilha_tech` → `raw` → `landing`.
# MAGIC 3. Botão **Upload to this volume** (canto superior direito).
# MAGIC 4. Arraste o `.csv` e confirme.
# MAGIC
# MAGIC > **Alternativa "Create Table" (UI):** Catalog → seu schema → **Create** → **Create table** →
# MAGIC > **Upload file**. A UI já infere o schema e cria a tabela com cliques. Ótimo para quem vem do Power BI.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Ler o CSV com Spark
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Leia o CSV em /Volumes/cba_trilha_tech/raw/landing/sample/furnace_telemetry_sample.csv
# MAGIC > com cabeçalho e inferência de schema, e mostre as 10 primeiras linhas."*
# MAGIC
# MAGIC Duas opções importantes:
# MAGIC - `header=True` → a 1ª linha são os nomes das colunas.
# MAGIC - `inferSchema=True` → o Spark **lê os dados e adivinha o tipo** de cada coluna (número, texto, data).

# COMMAND ----------

df = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(CSV_SAMPLE)
)

df.show(10)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Inspecionar o schema (os tipos que o Spark descobriu)
# MAGIC `inferSchema` não é mágica: ele leu uma amostra e chutou. Vamos conferir.

# COMMAND ----------

df.printSchema()
print(f"Linhas: {df.count():,}  |  Colunas: {len(df.columns)}")

# COMMAND ----------

# MAGIC %md
# MAGIC > ⚠️ **Observação didática:** `inferSchema` é prático, mas relê o arquivo (custa tempo) e às vezes
# MAGIC > erra (ex.: um CEP vira número e perde o zero à esquerda). Em produção, é comum **declarar o schema**.
# MAGIC > Por hoje, `inferSchema=True` está ótimo.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Salvar como tabela Delta (governada no Unity Catalog)
# MAGIC Um DataFrame na memória some quando o cluster reinicia. Uma **tabela Delta** é persistida,
# MAGIC versionada e consultável por toda a turma em SQL.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Salve esse DataFrame como uma tabela Delta gerenciada chamada telemetry_csv_demo,
# MAGIC > sobrescrevendo se já existir."*

# COMMAND ----------

(
    df.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("telemetry_csv_demo")
)
print("✅ Tabela criada: telemetry_csv_demo")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Consultar em SQL — igual a um banco de dados
# MAGIC Agora dá para usar **SQL puro**. Quem vem do Power BI/Excel se sente em casa aqui.
# MAGIC
# MAGIC > 💬 **Genie Code (em célula SQL, comece com `%sql`):** *"Quais são os 5 fornos com maior
# MAGIC > temperatura média na tabela telemetry_csv_demo?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   furnace_id,
# MAGIC   ROUND(AVG(temperature_c), 2) AS temp_media_c,
# MAGIC   ROUND(AVG(energy_kwh_ton), 1) AS energia_media_kwh_ton,
# MAGIC   COUNT(*) AS leituras
# MAGIC FROM telemetry_csv_demo
# MAGIC GROUP BY furnace_id
# MAGIC ORDER BY temp_media_c DESC
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Exercício
# MAGIC Usando o Assistant (💬 Genie Code), responda **em SQL**:
# MAGIC 1. Quantas leituras têm `is_failure = 1` (falha) na amostra?
# MAGIC 2. Qual a vibração média (`vibration_mm_s`) — e quantos nulos existem nessa coluna?
# MAGIC
# MAGIC *(Dica do prompt: "conte linhas com is_failure = 1 e mostre a média e a contagem de nulos de vibration_mm_s em telemetry_csv_demo")*

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - As primeiras linhas do CSV cru e depois como DataFrame.
# MAGIC - O schema inferido (`furnace_id` int, `temperature_c` double, `ts` timestamp…).
# MAGIC - A tabela `telemetry_csv_demo` aparecendo no Catalog, dentro do seu schema.
# MAGIC - O resultado do `SELECT` em SQL.
# MAGIC
# MAGIC **Próximo:** `02_autoloader_bronze` — em vez de 1 CSV, ingerir **tudo** de forma incremental com Auto Loader.
