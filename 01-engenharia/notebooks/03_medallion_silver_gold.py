# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Medalhão: Bronze → Prata → Ouro
# MAGIC ### Limpar, padronizar e agregar a telemetria do Gorila
# MAGIC
# MAGIC A **arquitetura medalhão** organiza o dado em camadas de qualidade crescente:
# MAGIC
# MAGIC | Camada | O que é | Na CBA |
# MAGIC |---|---|---|
# MAGIC | 🥉 **Bronze** | dado bruto, fiel à origem | tudo que o Gorila mandou (módulo 02) |
# MAGIC | 🥈 **Prata** | limpo, tipado, deduplicado | telemetria confiável, pronta para análise |
# MAGIC | 🥇 **Ouro** | agregado para o negócio | métricas por forno/dia: energia, taxa de falha, OEE |
# MAGIC
# MAGIC Vamos tratar os **nulos de vibração**, garantir **tipos** corretos, **remover duplicatas** e,
# MAGIC no ouro, calcular indicadores que o time de operação realmente usa.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Configuração padrão

# COMMAND ----------

CATALOG = "cba_trilha_tech"
username = spark.sql("SELECT current_user()").collect()[0][0]
user_schema = "ws_" + username.split("@")[0].replace(".", "_").replace("-", "_")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {user_schema}")
print(f"Trabalhando em {CATALOG}.{user_schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Bronze → Prata: limpeza e tipagem
# MAGIC
# MAGIC > 💬 **Genie Code:** *"A partir da tabela telemetry_bronze, crie uma tabela limpa: converta ts
# MAGIC > para timestamp, garanta que as colunas numéricas sejam double/int, remova linhas duplicadas por
# MAGIC > furnace_id e ts, e preencha os nulos de vibration_mm_s com a mediana por forno."*
# MAGIC
# MAGIC Decisões de limpeza desta etapa:
# MAGIC 1. **Tipos**: `ts` vira `timestamp`, sensores viram `double`, labels viram `int`.
# MAGIC 2. **Nulos de `vibration_mm_s`** (~1%): em vez de descartar, **imputamos a mediana de cada forno**
# MAGIC    (cada cuba vibra diferente). Marcamos com uma flag `vibration_imputada` para honestidade.
# MAGIC 3. **Deduplicação**: a chave natural é (`furnace_id`, `ts`). Mantemos 1 linha por chave.
# MAGIC 4. **Sanidade**: descartamos temperaturas absurdas (fora de 800–1100 °C).

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

bronze = spark.read.table("telemetry_bronze")

# tipagem explícita
tipado = (
    bronze
    .withColumn("ts", F.col("ts").cast("timestamp"))
    .withColumn("furnace_id", F.col("furnace_id").cast("int"))
    .withColumn("temperature_c", F.col("temperature_c").cast("double"))
    .withColumn("amperage_ka", F.col("amperage_ka").cast("double"))
    .withColumn("bath_ratio", F.col("bath_ratio").cast("double"))
    .withColumn("anode_effect", F.col("anode_effect").cast("int"))
    .withColumn("alumina_feed_rate", F.col("alumina_feed_rate").cast("double"))
    .withColumn("energy_kwh_ton", F.col("energy_kwh_ton").cast("double"))
    .withColumn("pressure_pa", F.col("pressure_pa").cast("double"))
    .withColumn("vibration_mm_s", F.col("vibration_mm_s").cast("double"))
    .withColumn("is_failure", F.col("is_failure").cast("int"))
)

# imputar nulos de vibração com a mediana POR FORNO + flag de auditoria
med_por_forno = Window.partitionBy("furnace_id")
silver = (
    tipado
    .withColumn("vibration_imputada", F.col("vibration_mm_s").isNull())
    .withColumn(
        "vibration_mm_s",
        F.coalesce(
            F.col("vibration_mm_s"),
            F.percentile_approx("vibration_mm_s", 0.5).over(med_por_forno),
        ),
    )
    # filtros de sanidade
    .filter(F.col("temperature_c").between(800, 1100))
    # dedup por (furnace_id, ts) mantendo a 1ª ocorrência
    .dropDuplicates(["furnace_id", "ts"])
)

(
    silver.write.format("delta").mode("overwrite")
    .option("overwriteSchema", True)
    .saveAsTable("telemetry_silver")
)
print(f"✅ telemetry_silver: {spark.read.table('telemetry_silver').count():,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Conferindo a limpeza
# MAGIC Quantos valores foram imputados? Ainda sobrou algum nulo?

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   COUNT(*)                                            AS total,
# MAGIC   SUM(CASE WHEN vibration_imputada THEN 1 ELSE 0 END) AS imputados,
# MAGIC   SUM(CASE WHEN vibration_mm_s IS NULL THEN 1 ELSE 0 END) AS nulos_restantes
# MAGIC FROM telemetry_silver;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Prata → Ouro: métricas por forno/dia
# MAGIC
# MAGIC O negócio não olha leitura de 5 em 5 minutos — olha **indicadores diários por forno**.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"A partir de telemetry_silver, agregue por furnace_id e dia: energia média
# MAGIC > por tonelada, temperatura média, vibração média, total de efeitos anódicos, número de leituras e
# MAGIC > taxa de falha (média de is_failure). Crie também um OEE simplificado."*
# MAGIC
# MAGIC **OEE simplificado (didático):** o OEE real combina Disponibilidade × Performance × Qualidade.
# MAGIC Aqui usamos um proxy: **disponibilidade** = 1 − taxa de falha do dia (quanto menos falha, mais
# MAGIC disponível a cuba). É uma simplificação para o workshop, não uma definição oficial.

# COMMAND ----------

gold = (
    spark.read.table("telemetry_silver")
    .withColumn("dia", F.to_date("ts"))
    .groupBy("furnace_id", "dia")
    .agg(
        F.round(F.avg("energy_kwh_ton"), 1).alias("energia_media_kwh_ton"),
        F.round(F.avg("temperature_c"), 2).alias("temp_media_c"),
        F.round(F.avg("vibration_mm_s"), 3).alias("vibracao_media_mm_s"),
        F.sum("anode_effect").alias("efeitos_anodicos"),
        F.count("*").alias("leituras"),
        F.round(F.avg("is_failure"), 4).alias("taxa_falha"),
    )
    # OEE simplificado: disponibilidade (1 - taxa de falha), em %
    .withColumn("oee_simplificado_pct", F.round((1 - F.col("taxa_falha")) * 100, 2))
)

(
    gold.write.format("delta").mode("overwrite")
    .option("overwriteSchema", True)
    .saveAsTable("telemetry_gold_forno_dia")
)
print(f"✅ telemetry_gold_forno_dia: {spark.read.table('telemetry_gold_forno_dia').count():,} linhas")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM telemetry_gold_forno_dia
# MAGIC ORDER BY taxa_falha DESC
# MAGIC LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. ACID & Time Travel (a "máquina do tempo" do Delta)
# MAGIC Delta é **ACID**: gravações são atômicas e versionadas. Dá para **voltar no tempo** e ver a tabela
# MAGIC como ela estava em uma versão anterior — ótimo para auditoria e para desfazer erros.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Histórico de versões da tabela prata
# MAGIC DESCRIBE HISTORY telemetry_silver;

# COMMAND ----------

# MAGIC %md
# MAGIC Vamos provocar uma **nova versão** (um UPDATE) e depois comparar com a versão anterior.

# COMMAND ----------

# Captura a versão atual (antes do UPDATE)
versao_antes = spark.sql("DESCRIBE HISTORY telemetry_silver") \
    .selectExpr("MAX(version)").collect()[0][0]
print(f"Versão atual (antes do update): {versao_antes}")

# Simula uma correção: zera a flag de imputação (gera nova versão)
spark.sql("UPDATE telemetry_silver SET vibration_imputada = false WHERE vibration_imputada = true")
print("✅ UPDATE executado — nova versão criada.")

# Time travel dinâmico: consulta a versão anterior ao update
df = spark.sql(f"""
    SELECT COUNT(*) AS imputados_antes_do_update
    FROM telemetry_silver VERSION AS OF {versao_antes}
    WHERE vibration_imputada = true
""")
display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC > 💬 **Genie Code:** *"Mostre o histórico de versões de telemetry_silver e selecione a tabela
# MAGIC > como ela estava na versão 0 usando time travel."*
# MAGIC >
# MAGIC > 🔁 Para reverter de fato: `RESTORE TABLE telemetry_silver TO VERSION AS OF 0;`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Exercício
# MAGIC 1. Crie uma ouro alternativa **por planta/dia** em vez de por forno (você vai precisar juntar com
# MAGIC    `dim_fornos` para saber a planta — isso é exatamente o tema do **módulo 04**, então pode adiantar!).
# MAGIC 2. Qual forno tem a **pior** taxa de falha média no período? Use o Assistant.
# MAGIC
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - `telemetry_silver` sem nulos em `vibration_mm_s` e com a flag `vibration_imputada`.
# MAGIC - `telemetry_gold_forno_dia` com energia média, taxa de falha e OEE por forno/dia.
# MAGIC - O `DESCRIBE HISTORY` listando ao menos 2 versões e o time travel funcionando.
# MAGIC
# MAGIC **Próximo:** `04_join_by_id` — conectar as bases pelos IDs.
