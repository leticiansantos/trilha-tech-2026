# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Conectando as bases por um ID
# MAGIC ### "Fazer as bases se conectarem através de um ID"
# MAGIC
# MAGIC Esse foi um pedido direto da reunião: as pessoas têm várias planilhas/tabelas soltas e precisam
# MAGIC **juntá-las**. A telemetria tem `furnace_id`, mas não sabe **em qual planta** está o forno, nem
# MAGIC **qual liga** estava sendo produzida. Essa informação vive nas **dimensões** (`dim_fornos`,
# MAGIC `dim_plantas`, `dim_ligas`). O **JOIN** conecta tudo pela **chave** (o ID).
# MAGIC
# MAGIC Vamos aprender:
# MAGIC - O que é **chave primária** (PK) e **chave estrangeira** (FK).
# MAGIC - Os tipos de join (`inner`, `left`, e por que isso muda o resultado).
# MAGIC - Como enriquecer a telemetria com planta, modelo do forno e dados da liga.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Configuração padrão

# COMMAND ----------

CATALOG = "cba_workshop_trilha_tech"
RAW_SCHEMA = "raw"
username = spark.sql("SELECT current_user()").collect()[0][0]
user_schema = "ws_" + username.split("@")[0].replace(".", "_").replace("-", "_")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {user_schema}")
LANDING = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/landing"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Carregar as dimensões como tabelas
# MAGIC As dimensões são pequenas — lemos do Volume e salvamos como Delta no seu schema.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Leia os CSVs dim_fornos, dim_plantas, dim_ligas e dim_produtos do volume
# MAGIC > landing com cabeçalho e inferência de schema, e salve cada um como tabela Delta."*

# COMMAND ----------

for nome in ["dim_fornos", "dim_plantas", "dim_ligas", "dim_produtos"]:
    (
        spark.read.option("header", True).option("inferSchema", True)
        .csv(f"{LANDING}/{nome}.csv")
        .write.format("delta").mode("overwrite").option("overwriteSchema", True)
        .saveAsTable(nome)
    )
    print(f"✅ {nome}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Entendendo as chaves (o "ID")
# MAGIC
# MAGIC - **Chave primária (PK):** identifica unicamente uma linha. Em `dim_fornos`, é `furnace_id`.
# MAGIC - **Chave estrangeira (FK):** uma coluna que aponta para a PK de outra tabela. Em `telemetry_silver`,
# MAGIC   `furnace_id` é FK que aponta para `dim_fornos.furnace_id`.
# MAGIC - `dim_fornos.plant_id` por sua vez é FK para `dim_plantas.plant_id`.
# MAGIC
# MAGIC É como montar um quebra-cabeça: cada peça encaixa pelo ID.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Espiando as chaves
# MAGIC SELECT furnace_id, plant_id, potline, model, capacity_ton_day
# MAGIC FROM dim_fornos LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. JOIN: enriquecer a telemetria com planta e modelo do forno
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Junte a tabela telemetry_gold_forno_dia com dim_fornos pelo furnace_id
# MAGIC > e depois com dim_plantas pelo plant_id, trazendo o nome da planta, o estado, o modelo e a
# MAGIC > capacidade do forno."*
# MAGIC
# MAGIC > 💡 **PySpark vs SQL:** os dois fazem a mesma coisa. Use o que for mais confortável — o Assistant
# MAGIC > gera nos dois. Abaixo, a versão PySpark.

# COMMAND ----------

from pyspark.sql import functions as F

gold = spark.read.table("telemetry_gold_forno_dia")
fornos = spark.read.table("dim_fornos")
plantas = spark.read.table("dim_plantas")

enriquecido = (
    gold
    .join(fornos, on="furnace_id", how="left")            # FK telemetria -> PK forno
    .join(plantas, on="plant_id", how="left")             # FK forno -> PK planta
    .select(
        "furnace_id", "dia", "plant_name", "state", "model", "capacity_ton_day",
        "energia_media_kwh_ton", "temp_media_c", "taxa_falha", "oee_simplificado_pct",
    )
)
enriquecido.show(10, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Tipos de join — por que `inner` ≠ `left`?
# MAGIC
# MAGIC - **inner join:** mantém só as linhas que **casam dos dois lados**. Se um forno da telemetria
# MAGIC   não existir em `dim_fornos`, ele **some**.
# MAGIC - **left join:** mantém **todas** as linhas da esquerda (telemetria); onde não houver par à direita,
# MAGIC   vem `null`. Bom para **detectar dados órfãos** (forno sem cadastro).
# MAGIC
# MAGIC Vamos comparar as contagens para ver a diferença na prática.

# COMMAND ----------

n_inner = gold.join(fornos, on="furnace_id", how="inner").count()
n_left = gold.join(fornos, on="furnace_id", how="left").count()
print(f"inner join: {n_inner:,} linhas")
print(f"left  join: {n_left:,} linhas")
print("Se forem iguais, todo forno da telemetria está cadastrado em dim_fornos. 👍")

# COMMAND ----------

# MAGIC %md
# MAGIC > ⚠️ **Pegadinha do join:** se a chave **se repete** no lado direito, o join **multiplica** linhas
# MAGIC > (explosão de cardinalidade). Dimensões devem ter PK única. Confira com:
# MAGIC > *💬 "conte furnace_id distintos vs total de linhas em dim_fornos para checar se a chave é única"*.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Salvar a visão de negócio enriquecida (ouro "wide")

# COMMAND ----------

(
    enriquecido.write.format("delta").mode("overwrite")
    .option("overwriteSchema", True)
    .saveAsTable("gold_forno_dia_enriquecido")
)
print("✅ gold_forno_dia_enriquecido")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Pergunta de negócio respondida com o join
# MAGIC Agora que temos a planta, dá para comparar **consumo de energia por planta** — algo impossível
# MAGIC só com a telemetria crua.
# MAGIC
# MAGIC > 💬 **Genie Code (SQL):** *"Mostre a energia média por tonelada e a taxa de falha média por planta,
# MAGIC > da maior energia para a menor."*

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   plant_name,
# MAGIC   state,
# MAGIC   ROUND(AVG(energia_media_kwh_ton), 1) AS energia_kwh_ton,
# MAGIC   ROUND(AVG(taxa_falha) * 100, 2)      AS taxa_falha_pct
# MAGIC FROM gold_forno_dia_enriquecido
# MAGIC GROUP BY plant_name, state
# MAGIC ORDER BY energia_kwh_ton DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Exercício
# MAGIC 1. Junte `furnace_inspections` (do módulo 02, ou leia o CSV) com `dim_ligas` e `dim_produtos`
# MAGIC    pelos IDs `alloy_id` e `product_id`. Qual **liga** tem a maior taxa de defeito (`is_defect`)?
# MAGIC 2. Faça um `left join` propositalmente errado (chave trocada) e veja o que acontece — depois
# MAGIC    use `/fix` no Assistant.
# MAGIC
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - A telemetria com `plant_name`, `state` e `model` preenchidos.
# MAGIC - `inner` e `left` com a mesma contagem (sem fornos órfãos).
# MAGIC - O ranking de energia/falha por planta.
# MAGIC
# MAGIC **Próximo:** `05_market_api_ingest` — trazer o preço do mercado via API (o tema "Gorila/API").
