# Databricks notebook source
# MAGIC %md
# MAGIC # ⚠️ Módulo 4 — Modelagem (Classificação binária) com Databricks AutoML
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA**
# MAGIC
# MAGIC Objetivo de negócio: **prever se uma peça terá defeito (`is_defect`)** a partir da
# MAGIC qualidade de superfície e do estado operacional do forno. Antecipar defeitos reduz
# MAGIC **retrabalho e refugo** — perda direta de margem.
# MAGIC
# MAGIC O **Databricks AutoML** treina e compara dezenas de modelos automaticamente, gera um
# MAGIC notebook **"glass-box"** (código aberto e editável) para cada experimento, e entrega o
# MAGIC melhor modelo já logado no MLflow. É a forma ideal de **nivelar** uma turma heterogênea:
# MAGIC todo mundo chega a um bom modelo, e quem quiser mergulha no código gerado.
# MAGIC
# MAGIC > **Variação (manutenção preditiva):** o mesmo fluxo serve para prever `is_failure` na
# MAGIC > telemetria. Trocaríamos a tabela e a coluna alvo. Usamos `is_defect` como caso principal.
# MAGIC
# MAGIC ---
# MAGIC ### 💬 Genie Code
# MAGIC O AutoML tem interface visual (**Experiments → Create AutoML Experiment**) e **API Python**.
# MAGIC Usamos a API aqui para ficar reprodutível. Se travar, peça ao Assistant:
# MAGIC > *"Como rodar um experimento de classificação com a API do databricks.automl?"*

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração

# COMMAND ----------

import mlflow
import databricks.automl as automl

CATALOG = "cba_trilha_tech"
current_user = spark.sql("SELECT current_user()").collect()[0][0]
user_prefix = current_user.split("@")[0].replace(".", "_").replace("-", "_")
SCHEMA = f"mlops_{user_prefix}"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
mlflow.set_registry_uri("databricks-uc")

CLF_TABLE = f"{CATALOG}.{SCHEMA}.defect_dataset"
TARGET = "is_defect"
print(f"Tabela de classificação: {CLF_TABLE} | alvo: {TARGET}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Preparar os dados de entrada
# MAGIC O AutoML recebe um DataFrame Spark. Removemos colunas de **identificação** (`inspection_id`,
# MAGIC `furnace_id`) que não devem ser usadas como feature — elas vazariam informação ou seriam ruído.

# COMMAND ----------

df_clf = (
    spark.table(CLF_TABLE)
    .drop("inspection_id", "furnace_id")  # ids não são features
)
display(df_clf.limit(5))
print(f"Colunas usadas: {df_clf.columns}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Rodar o AutoML (classificação)
# MAGIC Parâmetros principais:
# MAGIC - `dataset` — DataFrame de entrada.
# MAGIC - `target_col` — `is_defect`.
# MAGIC - `primary_metric="f1"` — boa escolha para classes **desbalanceadas** (~10% de defeitos);
# MAGIC   acurácia enganaria. F1 equilibra precisão e recall.
# MAGIC - `timeout_minutes` — limite de tempo (curto para o workshop).
# MAGIC
# MAGIC O AutoML faz EDA, split, treina vários modelos e registra tudo no MLflow.

# COMMAND ----------

summary = automl.classify(
    dataset=df_clf,
    target_col=TARGET,
    primary_metric="f1",
    timeout_minutes=10,
    pos_label=1,  # defeito = classe positiva (o que queremos detectar)
)

print("AutoML concluído.")
print(f"Melhor trial: {summary.best_trial.model_description}")
print(f"Métrica ({summary.best_trial.metrics.get('val_f1_score', 'f1')}): "
      f"{summary.best_trial.metrics}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Abrir o notebook "glass-box" do melhor modelo
# MAGIC O AutoML **gera código**. Isto é didático: você vê exatamente como o melhor modelo foi
# MAGIC pré-processado, treinado e avaliado — e pode editar.
# MAGIC
# MAGIC - **`summary.experiment`** → link para o experimento MLflow (todos os trials).
# MAGIC - **`summary.best_trial.notebook_path`** → notebook gerado do melhor modelo.

# COMMAND ----------

print("Experimento MLflow (compare os trials na UI):")
print(f"  {summary.experiment.name}")
print("\nNotebook glass-box do MELHOR modelo (abra e leia o código gerado):")
print(f"  {summary.best_trial.notebook_path}")
print("\nDica: abra também a galeria de notebooks de exploração de dados (Data exploration).")
print(f"  {summary.experiment.artifact_location}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Pegar o melhor modelo e registrar no Unity Catalog
# MAGIC O melhor trial já tem o modelo logado no MLflow. Registramos como
# MAGIC `furnace_defect_classifier` no UC.

# COMMAND ----------

MODEL_NAME = f"{CATALOG}.{SCHEMA}.furnace_defect_classifier"

best_model_uri = summary.best_trial.model_path  # URI runs:/.../model do melhor trial

model_version = mlflow.register_model(
    model_uri=best_model_uri,
    name=MODEL_NAME,
)
print(f"Modelo registrado: {MODEL_NAME} versão {model_version.version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Testar o modelo registrado
# MAGIC Carregamos o modelo do UC e fazemos uma previsão de exemplo, para confirmar que funciona.

# COMMAND ----------

import mlflow.pyfunc

loaded = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{model_version.version}")

sample = (
    spark.table(CLF_TABLE)
    .drop("inspection_id", "furnace_id", TARGET)
    .limit(5)
    .toPandas()
)
sample["pred_is_defect"] = loaded.predict(sample)
display(sample)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint do Módulo 4
# MAGIC - [ ] Rodei o AutoML de classificação com `primary_metric="f1"` (classe desbalanceada).
# MAGIC - [ ] Abri o notebook **glass-box** do melhor modelo e li o código gerado.
# MAGIC - [ ] Registrei o classificador no Unity Catalog.
# MAGIC - [ ] Fiz uma previsão de teste com o modelo carregado.
# MAGIC
# MAGIC ### 🎯 Exercício
# MAGIC No notebook glass-box, encontre a **matriz de confusão** e a importância das features.
# MAGIC `surface_quality_score` é a mais importante? Depois, peça ao **Genie Code** para montar o
# MAGIC mesmo experimento prevendo `is_failure` na telemetria (manutenção preditiva).
# MAGIC
# MAGIC **Próximo módulo:** governança no UC — versões, aliases @champion/@challenger e lineage.
