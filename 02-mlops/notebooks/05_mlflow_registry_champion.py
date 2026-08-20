# Databricks notebook source
# MAGIC %md
# MAGIC # 🏆 Módulo 5 — CRISP-DM: Avaliação & Governança no Unity Catalog
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA**
# MAGIC
# MAGIC Treinar é metade do trabalho. A outra metade é **governar**: versionar modelos, decidir
# MAGIC qual vai para produção e manter o histórico/linhagem para auditoria. No Unity Catalog,
# MAGIC modelos são objetos governados como tabelas — com permissões, lineage e **aliases**.
# MAGIC
# MAGIC Padrão de promoção:
# MAGIC - **`@champion`** → versão atualmente em produção.
# MAGIC - **`@challenger`** → versão candidata, em avaliação. Se superar o champion, é promovida.
# MAGIC
# MAGIC Trabalhamos aqui com o **regressor de energia** (`furnace_energy_regressor`) do Módulo 3.
# MAGIC O mesmo vale para o classificador de defeitos.
# MAGIC
# MAGIC ---
# MAGIC ### 💬 Genie Code
# MAGIC > *"Use o MlflowClient para listar as versões do modelo indicado pela variável `MODEL_NAME`
# MAGIC > (já definida na célula de configuração com o nome totalmente qualificado
# MAGIC > `catálogo.schema.furnace_energy_regressor`) e definir o alias `champion` na versão 1.
# MAGIC > Referencie a variável `MODEL_NAME`; não escreva o nome do modelo à mão."*

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
print(f"Modelo: {MODEL_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Listar versões registradas
# MAGIC Cada `register_model` cria uma nova versão imutável. Vemos o histórico completo.

# COMMAND ----------

versions = client.search_model_versions(f"name='{MODEL_NAME}'")
for v in sorted(versions, key=lambda x: int(x.version)):
    print(f"Versão {v.version} | run_id={v.run_id} | criada em {v.creation_timestamp}")

latest_version = max(int(v.version) for v in versions)
print(f"\nVersão mais recente: {latest_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Definir o champion
# MAGIC Se ainda não há champion, promovemos a versão 1 (nosso primeiro modelo em produção).

# COMMAND ----------

# ✍️ EXERCÍCIO — Genie Code: gere o código com o Databricks Assistant (✨ ou Ctrl/Cmd + I) a partir
# do prompt acima e escreva sua solução nesta célula. Revise com /explain antes de rodar.
# 💡 Contrato: defina o alias `champion` para a versão 1 de MODEL_NAME
#    (client.set_registered_model_alias). A listagem de versões já foi feita na célula anterior.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Registrar um desafiante (challenger)
# MAGIC Suponha que treinamos uma nova versão (ex.: o Gradient Boosting do Módulo 3, ou um modelo
# MAGIC retreinado com mais dados). Vamos registrá-la como **challenger** apontando para a versão
# MAGIC mais recente disponível.

# COMMAND ----------

# Se só existe a versão 1, treinamos rapidamente um challenger aqui para a demonstração.
if latest_version == 1:
    from sklearn.ensemble import RandomForestRegressor
    import numpy as np
    from sklearn.metrics import mean_squared_error

    FEATURES = ["temperature_c", "amperage_ka", "anode_effect", "bath_ratio", "alumina_feed_rate"]
    TARGET = "energy_kwh_ton"
    train_pdf = spark.table(f"{CATALOG}.{SCHEMA}.energy_train").select(*FEATURES, TARGET).toPandas()

    mlflow.sklearn.autolog(log_models=True)
    with mlflow.start_run(run_name="random_forest_challenger") as run:
        rf = RandomForestRegressor(n_estimators=150, max_depth=10, random_state=42, n_jobs=-1)
        rf.fit(train_pdf[FEATURES], train_pdf[TARGET])
        challenger_run_id = run.info.run_id

    mv = mlflow.register_model(model_uri=f"runs:/{challenger_run_id}/model", name=MODEL_NAME)
    challenger_version = mv.version
else:
    challenger_version = latest_version

client.set_registered_model_alias(name=MODEL_NAME, alias="challenger", version=challenger_version)
print(f"Alias 'challenger' -> versão {challenger_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Comparar challenger × champion no conjunto de teste
# MAGIC A decisão de promover é baseada em **dados**, não em opinião. Avaliamos as duas versões no
# MAGIC mesmo teste e comparamos o RMSE.

# COMMAND ----------

import numpy as np
from sklearn.metrics import mean_squared_error, r2_score

FEATURES = ["temperature_c", "amperage_ka", "anode_effect", "bath_ratio", "alumina_feed_rate"]
TARGET = "energy_kwh_ton"
test_pdf = spark.table(f"{CATALOG}.{SCHEMA}.energy_test").select(*FEATURES, TARGET).toPandas()
X_test, y_test = test_pdf[FEATURES], test_pdf[TARGET]

def evaluate(alias):
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{alias}")
    preds = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds))
    return rmse, r2

champ_rmse, champ_r2 = evaluate("champion")
chal_rmse, chal_r2 = evaluate("challenger")

print(f"Champion   : RMSE={champ_rmse:.1f} | R²={champ_r2:.3f}")
print(f"Challenger : RMSE={chal_rmse:.1f} | R²={chal_r2:.3f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Promover o challenger se ele for melhor
# MAGIC Regra: se o challenger tem **RMSE menor**, ele vira o novo champion. Esta lógica pode ir
# MAGIC para um **job** que roda no retreino (CI/CD de modelos).

# COMMAND ----------

if chal_rmse < champ_rmse:
    client.set_registered_model_alias(name=MODEL_NAME, alias="champion", version=challenger_version)
    print(f"✅ Challenger PROMOVIDO: versão {challenger_version} agora é 'champion'.")
else:
    print("ℹ️ Champion mantido — challenger não superou o RMSE atual.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Governança & lineage
# MAGIC No Unity Catalog, abra **Catalog → cba_workshop_trilha_tech → seu schema → Models** e veja:
# MAGIC - **Versions** e os **aliases** (champion/challenger) que você definiu.
# MAGIC - **Lineage** — quais notebooks/jobs e tabelas geraram o modelo.
# MAGIC - **Permissions** — quem pode ler, usar e gerenciar o modelo.
# MAGIC
# MAGIC Adicionamos também uma **tag** e uma **descrição** para documentar o propósito.

# COMMAND ----------

client.set_registered_model_tag(MODEL_NAME, "use_case", "eficiencia_energetica_fornos")
client.set_registered_model_tag(MODEL_NAME, "trilha", "mlops_2026")
client.update_registered_model(
    name=MODEL_NAME,
    description="Regressor de energia (kWh/ton) das cubas eletrolíticas. CBA Trilha Tech 2026.",
)
print("Tags e descrição atualizadas. Confira na UI do Unity Catalog.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint do Módulo 5
# MAGIC - [ ] Listei as versões do modelo no UC.
# MAGIC - [ ] Defini o alias `@champion` e registrei um `@challenger`.
# MAGIC - [ ] Comparei as duas versões no conjunto de teste com a **mesma** métrica.
# MAGIC - [ ] Apliquei a regra de promoção baseada em dados.
# MAGIC - [ ] Documentei o modelo com tags/descrição e vi o lineage na UI.
# MAGIC
# MAGIC ### 🎯 Exercício
# MAGIC Repita o fluxo champion/challenger para o **classificador de defeitos**
# MAGIC (`furnace_defect_classifier`), usando **F1** como métrica de decisão em vez de RMSE.
# MAGIC
# MAGIC **Próximo módulo:** colocar o champion em produção (Model Serving + `ai_query`).
