# Databricks notebook source
# MAGIC %md
# MAGIC # 🧱 Módulo 2 — CRISP-DM: Preparação dos Dados & Feature Engineering em Unity Catalog
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA**
# MAGIC
# MAGIC Nesta etapa do CRISP-DM construímos o **dataset de treino** e registramos *features*
# MAGIC reutilizáveis em uma **Feature Table** no Unity Catalog (Feature Engineering in UC).
# MAGIC Vantagens: as features ficam **versionadas, governadas e reutilizáveis** entre modelos
# MAGIC e entre treino/inferência (evita *training-serving skew*).
# MAGIC
# MAGIC O que faremos:
# MAGIC 1. Montar o dataset de **regressão** (energia) a partir da telemetria.
# MAGIC 2. Criar uma **Feature Table** no UC com `FeatureEngineeringClient`.
# MAGIC 3. Montar o dataset de **classificação** (defeito) juntando inspeções + telemetria agregada.
# MAGIC 4. Fazer o **split treino/teste** de forma reprodutível.
# MAGIC
# MAGIC ---
# MAGIC ### 💬 Genie Code
# MAGIC Sempre que precisar de um *join*, uma agregação ou uma transformação, abra o **Databricks
# MAGIC Assistant** (`Ctrl/Cmd + I`) e descreva em português o que quer. Revise o código gerado.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração (mesmo padrão do Módulo 1)

# COMMAND ----------

CATALOG = "cba_workshop_trilha_tech"
current_user = spark.sql("SELECT current_user()").collect()[0][0]
user_prefix = current_user.split("@")[0].replace(".", "_").replace("-", "_")
SCHEMA = f"mlops_{user_prefix}"
GOLD = f"{CATALOG}.{SCHEMA}"  # dados criados no seu schema pelo Módulo 0 (00_setup_dados)

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
print(f"Catálogo.Schema: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Dataset de regressão — prever `energy_kwh_ton`
# MAGIC **Features escolhidas (no Módulo 1):** `temperature_c`, `amperage_ka`, `anode_effect`,
# MAGIC `bath_ratio`, `alumina_feed_rate`. **Alvo:** `energy_kwh_ton`.
# MAGIC
# MAGIC Precisamos de uma **chave primária** para a Feature Table. A telemetria não tem uma
# MAGIC coluna de ID única, então criamos `reading_id` (forno + timestamp).

# COMMAND ----------

from pyspark.sql import functions as F

df_telemetry = spark.table(f"{GOLD}.furnace_telemetry")

# Cria chave única reading_id = furnace_id + timestamp (a combinação é única na telemetria)
df_reg = (
    df_telemetry
    .withColumn("reading_id", F.concat_ws("_", F.col("furnace_id"), F.unix_timestamp("ts")))
    .select(
        "reading_id", "furnace_id", "ts",
        # features
        "temperature_c", "amperage_ka", "anode_effect", "bath_ratio", "alumina_feed_rate",
        # alvo
        "energy_kwh_ton",
    )
    # garante que não há nulos nas colunas usadas (as features escolhidas não têm nulos)
    .dropna(subset=["temperature_c", "amperage_ka", "anode_effect", "bath_ratio",
                    "alumina_feed_rate", "energy_kwh_ton"])
)
print(f"Linhas para regressão: {df_reg.count():,}")
display(df_reg.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Criar a Feature Table no Unity Catalog
# MAGIC Usamos o `FeatureEngineeringClient` (biblioteca `databricks-feature-engineering`, já
# MAGIC instalada no Databricks Runtime ML). A tabela é uma tabela Delta no UC com uma
# MAGIC **chave primária** declarada.
# MAGIC
# MAGIC ### 💬 Genie Code
# MAGIC > *"Crie uma feature table no Unity Catalog chamada `furnace_energy_features` com chave
# MAGIC > primária `reading_id` a partir do DataFrame `df_reg` usando o FeatureEngineeringClient."*

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

from databricks.feature_engineering import FeatureEngineeringClient

fe = FeatureEngineeringClient()

FEATURE_TABLE_REG = f"{CATALOG}.{SCHEMA}.furnace_energy_features"

# Remove versão anterior (caso o aluno reexecute o notebook)
try:
    fe.drop_table(name=FEATURE_TABLE_REG)
except Exception as e:
    print(f"(tabela ainda não existia: {e})")

fe.create_table(
    name=FEATURE_TABLE_REG,
    primary_keys=["reading_id"],
    df=df_reg.select("reading_id", "furnace_id",
                     "temperature_c", "amperage_ka", "anode_effect",
                     "bath_ratio", "alumina_feed_rate", "energy_kwh_ton"),
    description="Features de telemetria de fornos para prever energia (kWh/ton). CBA Trilha Tech 2026.",
)
print(f"Feature Table criada: {FEATURE_TABLE_REG}")
display(spark.table(FEATURE_TABLE_REG).limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Split treino/teste reprodutível (regressão)
# MAGIC Usamos `randomSplit` com **seed fixa** para que todos os alunos tenham a mesma divisão.
# MAGIC Salvamos as duas partes como tabelas Delta no schema do aluno.

# COMMAND ----------

train_reg, test_reg = df_reg.randomSplit([0.8, 0.2], seed=42)

train_reg.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.energy_train")
test_reg.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.energy_test")

print(f"Treino: {train_reg.count():,} linhas | Teste: {test_reg.count():,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Dataset de classificação — prever `is_defect`
# MAGIC O alvo principal é `is_defect` (tabela de inspeções). A feature mais forte é
# MAGIC `surface_quality_score`. Vamos **enriquecer** cada inspeção com a telemetria média
# MAGIC recente do forno (estado operacional do forno antes da inspeção).
# MAGIC
# MAGIC ### 💬 Genie Code
# MAGIC > *"Para cada forno, calcule a média de `temperature_c`, `amperage_ka`, `anode_effect`
# MAGIC > e `vibration_mm_s` na tabela `furnace_telemetry` e junte com `furnace_inspections`
# MAGIC > pela coluna `furnace_id`."*

# COMMAND ----------

# Agregação da telemetria por forno (estado operacional médio)
furnace_agg = (
    spark.table(f"{GOLD}.furnace_telemetry")
    .groupBy("furnace_id")
    .agg(
        F.avg("temperature_c").alias("avg_temperature_c"),
        F.avg("amperage_ka").alias("avg_amperage_ka"),
        F.avg("anode_effect").alias("avg_anode_effect"),
        F.avg("vibration_mm_s").alias("avg_vibration_mm_s"),
        F.avg("energy_kwh_ton").alias("avg_energy_kwh_ton"),
    )
)

df_inspections = spark.table(f"{GOLD}.furnace_inspections")

df_clf = (
    df_inspections
    .join(furnace_agg, on="furnace_id", how="left")
    .select(
        "inspection_id", "furnace_id", "alloy_id", "product_id",
        # features
        "surface_quality_score",
        "avg_temperature_c", "avg_amperage_ka", "avg_anode_effect", "avg_vibration_mm_s",
        # alvo
        "is_defect",
    )
)

# Imputa eventuais nulos de vibração média pela mediana (visto no Módulo 1)
median_vib = df_clf.approxQuantile("avg_vibration_mm_s", [0.5], 0.01)[0]
df_clf = df_clf.fillna({"avg_vibration_mm_s": median_vib})

print(f"Linhas para classificação: {df_clf.count():,}")
display(df_clf.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Salvar o dataset de classificação
# MAGIC O AutoML (Módulo 4) precisa de uma **tabela** de entrada. Salvamos o dataset completo;
# MAGIC o AutoML cuida do split interno de treino/validação/teste.

# COMMAND ----------

CLF_TABLE = f"{CATALOG}.{SCHEMA}.defect_dataset"
df_clf.write.mode("overwrite").saveAsTable(CLF_TABLE)
print(f"Tabela de classificação salva: {CLF_TABLE}")

# Confere a proporção de classes preservada
display(
    spark.table(CLF_TABLE).groupBy("is_defect").count()
    .withColumn("pct", F.round(F.col("count") / df_clf.count() * 100, 2))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint do Módulo 2
# MAGIC - [ ] Criei a Feature Table `furnace_energy_features` no Unity Catalog com chave `reading_id`.
# MAGIC - [ ] Gerei `energy_train` / `energy_test` (split 80/20, seed 42).
# MAGIC - [ ] Montei `defect_dataset` juntando inspeções + telemetria agregada por forno.
# MAGIC - [ ] Entendi por que registrar features no UC (governança, reuso, evitar skew).
# MAGIC
# MAGIC ### 🎯 Exercício
# MAGIC Use o **Genie Code** para adicionar uma nova feature ao dataset de regressão: o **desvio**
# MAGIC da temperatura em relação a 960 °C (`abs(temperature_c - 960)`). Recrie a feature table
# MAGIC incluindo essa coluna e discuta se ela ajudaria o modelo.
# MAGIC
# MAGIC **Próximo módulo:** treinar a regressão com MLflow autolog.
