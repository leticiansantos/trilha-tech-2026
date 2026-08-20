# Databricks notebook source
# MAGIC %md
# MAGIC # 🚀 Módulo 6 — CRISP-DM: Implantação (Model Serving + `ai_query`)
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA**
# MAGIC
# MAGIC Um modelo só gera valor quando **alguém o usa**. Vamos publicar o champion de energia em um
# MAGIC **Model Serving endpoint** (REST, com **scale-to-zero** para economizar), fazer
# MAGIC **inferência em lote** e chamar o modelo direto do **SQL** com `ai_query()` — o que permite
# MAGIC que analistas (trilha de Insights) consumam previsões sem escrever Python.
# MAGIC
# MAGIC ---
# MAGIC ### 💬 Genie Code
# MAGIC > *"Crie um endpoint de Model Serving servindo a versão @champion do modelo
# MAGIC > `furnace_energy_regressor` do Unity Catalog, com scale-to-zero habilitado."*

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração

# COMMAND ----------

import mlflow
from mlflow.tracking import MlflowClient

CATALOG = "cba_workshop_trilha_tech"
current_user = spark.sql("SELECT current_user()").collect()[0][0]
user_prefix = current_user.split("@")[0].replace(".", "_").replace("-", "_")
SCHEMA = f"mlops_{user_prefix}"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
mlflow.set_registry_uri("databricks-uc")

client = MlflowClient()
MODEL_NAME = f"{CATALOG}.{SCHEMA}.furnace_energy_regressor"
ENDPOINT_NAME = f"cba_energy_{user_prefix}"  # nome único por aluno

champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
print(f"Servindo {MODEL_NAME} @champion (versão {champion.version})")
print(f"Endpoint: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Criar/atualizar o endpoint de Model Serving
# MAGIC Usamos o SDK do Databricks. `scale_to_zero_enabled=True` desliga o endpoint quando ocioso
# MAGIC (custo zero) e religa sob demanda — ideal para um workshop.
# MAGIC
# MAGIC > A criação leva alguns minutos. Faça isso no início do módulo e siga para a parte de lote
# MAGIC > enquanto provisiona.

# COMMAND ----------

# ✍️ EXERCÍCIO — Genie Code: gere o código com o Databricks Assistant (✨ ou Ctrl/Cmd + I) a partir
# do prompt acima e escreva sua solução nesta célula. Revise com /explain antes de rodar.
# 💡 Contrato: crie `w = WorkspaceClient()` e o endpoint `ENDPOINT_NAME` servindo MODEL_NAME na
#    versão @champion, com `scale_to_zero_enabled=True`. `w` é reutilizado nas células REST adiante.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Inferência em lote (sem endpoint)
# MAGIC Para pontuar **muitos** registros de uma vez, o caminho mais eficiente é carregar o modelo
# MAGIC como uma **Spark UDF** e aplicar sobre uma tabela inteira — paralelizado pelo cluster.
# MAGIC Não precisa de endpoint para isso.
# MAGIC
# MAGIC ### 💬 Genie Code
# MAGIC > *"Carregue o modelo @champion como uma spark_udf do MLflow e aplique sobre a tabela
# MAGIC > `energy_test` para gerar uma coluna de previsão."*

# COMMAND ----------

# ✍️ EXERCÍCIO — Genie Code: gere o código com o Databricks Assistant (✨ ou Ctrl/Cmd + I) a partir
# do prompt acima e escreva sua solução nesta célula. Revise com /explain antes de rodar.
# 💡 Contrato: importe `pyspark.sql.functions as F`, crie `predict_udf` com
#    `mlflow.pyfunc.spark_udf(... models:/{MODEL_NAME}@champion ...)`, gere a coluna
#    `predicted_energy_kwh_ton` sobre `energy_test` e salve a tabela `energy_predictions`
#    (usada no alerta de fornos ineficientes adiante).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Inferência via REST (endpoint online)
# MAGIC Para previsões **em tempo real** (uma cuba específica agora), chamamos o endpoint.
# MAGIC Aguarde o endpoint ficar `READY` antes de rodar esta célula.

# COMMAND ----------

# Verifica se o endpoint está pronto; se sim, faz uma chamada de exemplo
try:
    state = w.serving_endpoints.get(ENDPOINT_NAME).state
    print(f"Estado do endpoint: {state}")

    sample = spark.table(f"{CATALOG}.{SCHEMA}.energy_test").select(*FEATURES).limit(3).toPandas()
    response = w.serving_endpoints.query(
        name=ENDPOINT_NAME,
        dataframe_records=sample.to_dict(orient="records"),
    )
    print("Previsões do endpoint:", response.predictions)
except Exception as e:
    print(f"Endpoint ainda provisionando ou indisponível: {e}")
    print("Aguarde alguns minutos e rode esta célula novamente.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. `ai_query()` — inferência direto no SQL
# MAGIC `ai_query()` chama um endpoint de serving de dentro de uma consulta SQL. Assim, **analistas**
# MAGIC pontuam dados sem Python. (Requer o endpoint `READY`.)
# MAGIC
# MAGIC ### 💬 Genie Code (célula SQL)
# MAGIC > *"Use ai_query no endpoint para prever energy_kwh_ton em 5 linhas da tabela energy_test."*

# COMMAND ----------

# MAGIC %md
# MAGIC ```sql
# MAGIC -- Substitua <ENDPOINT_NAME> pelo nome impresso na célula 1 (ex.: cba_energy_seu_user)
# MAGIC SELECT
# MAGIC   temperature_c, amperage_ka, anode_effect, bath_ratio, alumina_feed_rate,
# MAGIC   energy_kwh_ton AS energia_real,
# MAGIC   ai_query(
# MAGIC     '<ENDPOINT_NAME>',
# MAGIC     named_struct(
# MAGIC       'temperature_c', temperature_c,
# MAGIC       'amperage_ka', amperage_ka,
# MAGIC       'anode_effect', anode_effect,
# MAGIC       'bath_ratio', bath_ratio,
# MAGIC       'alumina_feed_rate', alumina_feed_rate
# MAGIC     )
# MAGIC   ) AS energia_prevista
# MAGIC FROM energy_test
# MAGIC LIMIT 5;
# MAGIC ```

# COMMAND ----------

# ✍️ EXERCÍCIO — Genie Code: gere o código com o Databricks Assistant (✨ ou Ctrl/Cmd + I) a partir
# do prompt acima e escreva sua solução aqui. Revise com /explain antes de rodar.
# 💡 Dica: rode o `ai_query(...)` numa célula %sql (use o modelo SQL de referência acima,
#    trocando <ENDPOINT_NAME> pelo nome do seu endpoint), OU monte o SQL em Python e execute com
#    `spark.sql(...)`. Requer o endpoint em estado READY.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Alerta simples — fornos ineficientes
# MAGIC Combinando previsão e realidade, sinalizamos fornos cuja energia real **excede** a prevista
# MAGIC em mais de um limiar (possível ineficiência / desvio operacional).

# COMMAND ----------

alerts = (
    spark.table(f"{CATALOG}.{SCHEMA}.energy_predictions")
    .withColumn("desvio", F.col("energy_kwh_ton") - F.col("predicted_energy_kwh_ton"))
    .filter(F.col("desvio") > 300)  # consome >300 kWh/ton acima do esperado
    .select("furnace_id", "ts", "energy_kwh_ton", "predicted_energy_kwh_ton", "desvio")
    .orderBy(F.col("desvio").desc())
)
print(f"Fornos com consumo acima do previsto: {alerts.count()}")
display(alerts.limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint do Módulo 6
# MAGIC - [ ] Criei um Model Serving endpoint com scale-to-zero servindo o @champion.
# MAGIC - [ ] Fiz inferência **em lote** com `spark_udf` e salvei `energy_predictions`.
# MAGIC - [ ] Consultei o endpoint via REST e via **`ai_query()`** no SQL.
# MAGIC - [ ] Montei um alerta de fornos ineficientes.
# MAGIC
# MAGIC ### 🎯 Exercício
# MAGIC Crie um endpoint para o **classificador de defeitos** e use `ai_query()` para marcar quais
# MAGIC inspeções têm alta probabilidade de defeito. Pense: como a trilha de Insights usaria isso?
# MAGIC
# MAGIC > **Limpeza:** ao final do workshop, exclua o endpoint para não consumir recursos:
# MAGIC > `w.serving_endpoints.delete(ENDPOINT_NAME)`.
# MAGIC
# MAGIC **Próximo módulo:** construir um **agente de RCA** de manutenção com Mosaic AI Agent Framework.
