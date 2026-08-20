# Databricks notebook source
# MAGIC %md
# MAGIC # 🔢 Módulo 3 — CRISP-DM: Modelagem (Regressão) com MLflow 3
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA**
# MAGIC
# MAGIC Objetivo de negócio: **prever a energia por tonelada (`energy_kwh_ton`)** de uma cuba a
# MAGIC partir das suas variáveis operacionais. Energia é o **maior custo** do alumínio — prever e
# MAGIC explicar o consumo ajuda a operar fornos mais eficientes.
# MAGIC
# MAGIC Vamos treinar um **baseline em scikit-learn** com `mlflow.autolog()`, comparar *runs* e
# MAGIC registrar o modelo. O MLflow 3 captura **parâmetros, métricas, artefatos e o modelo**
# MAGIC automaticamente.
# MAGIC
# MAGIC > Requer um cluster com **Databricks Runtime for Machine Learning** (traz scikit-learn,
# MAGIC > MLflow e XGBoost pré-instalados).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração

# COMMAND ----------

import mlflow

CATALOG = "cba_workshop_trilha_tech"
current_user = spark.sql("SELECT current_user()").collect()[0][0]
user_prefix = current_user.split("@")[0].replace(".", "_").replace("-", "_")
SCHEMA = f"mlops_{user_prefix}"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# MLflow 3: registramos modelos no Unity Catalog (não no Workspace Registry legado)
mlflow.set_registry_uri("databricks-uc")

# Experimento dedicado do aluno
EXPERIMENT = f"/Users/{current_user}/cba_mlops_regression"
mlflow.set_experiment(EXPERIMENT)
print(f"Experimento MLflow: {EXPERIMENT}")

FEATURES = ["temperature_c", "amperage_ka", "anode_effect", "bath_ratio", "alumina_feed_rate"]
TARGET = "energy_kwh_ton"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Carregar treino e teste (criados no Módulo 2)
# MAGIC Trazemos para pandas — os datasets de regressão cabem confortavelmente em memória após o
# MAGIC split. (Para volumes maiores usaríamos Spark ML ou amostragem.)

# COMMAND ----------

train_pdf = spark.table(f"{CATALOG}.{SCHEMA}.energy_train").select(*FEATURES, TARGET).toPandas()
test_pdf = spark.table(f"{CATALOG}.{SCHEMA}.energy_test").select(*FEATURES, TARGET).toPandas()

X_train, y_train = train_pdf[FEATURES], train_pdf[TARGET]
X_test, y_test = test_pdf[FEATURES], test_pdf[TARGET]

print(f"Treino: {X_train.shape} | Teste: {X_test.shape}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Baseline — Regressão Linear com `mlflow.autolog()`
# MAGIC `mlflow.autolog()` instrumenta o scikit-learn: cada `.fit()` vira um **run** com parâmetros,
# MAGIC métricas de treino e o modelo logado, sem código extra.
# MAGIC
# MAGIC ### 💬 Genie Code
# MAGIC > *"Treine uma regressão linear do scikit-learn para prever `energy_kwh_ton` a partir de
# MAGIC > `temperature_c`, `amperage_ka`, `anode_effect`, `bath_ratio` e `alumina_feed_rate`,
# MAGIC > com mlflow.autolog ativado."*

# COMMAND ----------

# ✍️ EXERCÍCIO — Genie Code: gere o código com o Databricks Assistant (✨ ou Ctrl/Cmd + I) a partir
# do prompt acima e escreva sua solução nesta célula. Revise com /explain antes de rodar.
# 💡 Contrato: ative `mlflow.sklearn.autolog()` e treine uma LinearRegression (X_train/y_train)
#    dentro de um `mlflow.start_run(...)`, logando as métricas de teste `test_rmse`, `test_r2`,
#    `test_mae` (usadas na comparação de runs adiante).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Modelo desafiante — Gradient Boosting
# MAGIC Modelos baseados em árvore costumam capturar não-linearidades. Vamos treinar um
# MAGIC `GradientBoostingRegressor` e comparar com o baseline.
# MAGIC
# MAGIC ### 💬 Genie Code
# MAGIC > *"Treine um GradientBoostingRegressor para o mesmo problema e compare o RMSE de teste
# MAGIC > com a regressão linear."*

# COMMAND ----------

# ✍️ EXERCÍCIO — Genie Code: gere o código com o Databricks Assistant (✨ ou Ctrl/Cmd + I) a partir
# do prompt acima e escreva sua solução nesta célula. Revise com /explain antes de rodar.
# 💡 Contrato: treine um GradientBoostingRegressor dentro de um `mlflow.start_run(...)`, logando
#    `test_rmse`/`test_r2`/`test_mae` para comparar com o baseline linear na próxima seção.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Comparar runs
# MAGIC Abra a aba **Experiments** (ícone de frasco na barra lateral) para comparar visualmente os
# MAGIC dois runs. Via código, listamos os runs ordenados pelo RMSE de teste.

# COMMAND ----------

runs = mlflow.search_runs(
    experiment_ids=[mlflow.get_experiment_by_name(EXPERIMENT).experiment_id],
    order_by=["metrics.test_rmse ASC"],
)
display(runs[["run_id", "tags.mlflow.runName", "metrics.test_rmse",
              "metrics.test_r2", "metrics.test_mae"]])

best_run_id = runs.iloc[0]["run_id"]
best_name = runs.iloc[0]["tags.mlflow.runName"]
print(f"Melhor run: {best_name} ({best_run_id})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Registrar o melhor modelo no Unity Catalog
# MAGIC Registramos o modelo do melhor run como `furnace_energy_regressor` no UC. No Módulo 5
# MAGIC trabalharemos os **aliases** `@champion`/`@challenger`.

# COMMAND ----------

MODEL_NAME = f"{CATALOG}.{SCHEMA}.furnace_energy_regressor"

model_version = mlflow.register_model(
    model_uri=f"runs:/{best_run_id}/model",
    name=MODEL_NAME,
)
print(f"Modelo registrado: {MODEL_NAME} versão {model_version.version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint do Módulo 3
# MAGIC - [ ] Treinei um baseline (Linear) e um desafiante (Gradient Boosting) com `mlflow.autolog`.
# MAGIC - [ ] Loguei métricas de teste (RMSE, R², MAE) em cada run.
# MAGIC - [ ] Comparei os runs e identifiquei o melhor.
# MAGIC - [ ] Registrei o modelo vencedor no Unity Catalog.
# MAGIC
# MAGIC ### 🎯 Exercício
# MAGIC Treine um terceiro modelo (ex.: `RandomForestRegressor`) via **Genie Code**. Ele bate o
# MAGIC Gradient Boosting? Discuta o trade-off entre RMSE e tempo de treino/inferência.
# MAGIC
# MAGIC **Próximo módulo:** classificação binária (`is_defect`) com Databricks AutoML.
