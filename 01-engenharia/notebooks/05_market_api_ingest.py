# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Ingestão via API: o preço do mercado
# MAGIC ### "Consumir uma API de fora" — fechando o "Do Forno ao Mercado"
# MAGIC
# MAGIC Até aqui temos o **custo** (telemetria do Gorila → energia). Falta o outro lado da margem:
# MAGIC **por quanto o mercado paga o alumínio**. Isso vem de fontes externas via **API**:
# MAGIC - **Preço do alumínio** na **LME** (London Metal Exchange), em USD/tonelada.
# MAGIC - **Câmbio USD/BRL** (no real, do **Banco Central**).
# MAGIC
# MAGIC Na reunião citaram que o **Gorila vai expor uma API** e que o time quer aprender a **consumir API**.
# MAGIC Hoje usamos uma **API mock** (FastAPI) que imita LME + Banco Central, mas o padrão é idêntico ao real.
# MAGIC
# MAGIC > 📌 **Fonte real:** em produção, o preço viria da B3/LME (ou de um provedor licenciado) e o câmbio
# MAGIC > do **PTAX do Banco Central** (`https://olinda.bcb.gov.br/`). A mecânica — `requests.get`, JSON →
# MAGIC > DataFrame → Delta — é a mesma.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Configuração padrão

# COMMAND ----------

CATALOG = "cba_trilha_tech"
username = spark.sql("SELECT current_user()").collect()[0][0]
user_schema = "ws_" + username.split("@")[0].replace(".", "_").replace("-", "_")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {user_schema}")

# URL da API mock — o instrutor informa o endereço (ex.: um serviço rodando ou Databricks App)
# Ex.: "http://<host>:8000"  ou  "https://<app>.databricksapps.com"
# API_BASE = dbutils.widgets.get("api_base") if "api_base" in [w.name for w in dbutils.widgets.getAll()] else "http://localhost:8000"

API_BASE = "https://cba-market-api-7405605468532306.6.azure.databricksapps.com"
print(f"API base: {API_BASE}")

# COMMAND ----------

# MAGIC %md
# MAGIC > 💡 **Widget de parâmetro:** crie um widget de texto chamado `api_base` (menu **Edit → Add widget**)
# MAGIC > e cole a URL que o instrutor passar. Assim ninguém precisa editar o código.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Chamar a API com `requests`
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Faça uma requisição GET para {API_BASE}/aluminum/lme com os parâmetros
# MAGIC > start=2026-01-01 e end=2026-03-31 usando a biblioteca requests, verifique o status e mostre o JSON."*
# MAGIC
# MAGIC Uma API REST responde a um `GET` com **JSON**. Vamos pegar, checar o status e olhar a estrutura.

# COMMAND ----------

import requests
from databricks.sdk import WorkspaceClient

# 1. Inicializa o cliente do SDK para ler os metadados do App
w = WorkspaceClient()

# 2. Captura dinamicamente o ID de Cliente OAuth gerado para a sua API mock
app_client_id = w.apps.get("cba-market-api").oauth2_app_client_id

# 3. Recupera o token interno da sessão do notebook e a URL do workspace
notebook_token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
workspace_url = w.config.host

# 4. Executa o fluxo de Troca de Token (Token Exchange) exigido pelo proxy do App
token_url = f"{workspace_url.rstrip('/')}/oidc/v1/token"
exchange_data = {
    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    "subject_token": notebook_token,
    "subject_token_type": "urn:databricks:params:oauth:token-type:personal-access-token",
    "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
    "scope": "all-apis",
    "audience": app_client_id,
}

print("==> Efetuando a troca de token por escopo de audiência (OAuth 2.0)...")
token_response = requests.post(url=token_url, data=exchange_data)
token_response.raise_for_status()

# 5. Extrai o token de acesso exclusivo para o App e monta o cabeçalho
audience_token = token_response.json()["access_token"]
headers = {"Authorization": f"Bearer {audience_token}"}

# 6. Faz a requisição para o endpoint da API ativa com o cabeçalho correto
params = {"start": "2026-01-01", "end": "2026-03-31"}
print(f"==> Executando chamada para: {API_BASE}/aluminum/lme")

resp_lme = requests.get(f"{API_BASE}/aluminum/lme", params=params, headers=headers, timeout=30)
resp_lme.raise_for_status()


# 7. Realiza o parse do JSON dos dados de mercado reais
payload_lme = resp_lme.json()

print("\n--- Dados Ingeridos com Sucesso ---")
print("Fonte :", payload_lme["source"])
print("Unidade:", payload_lme["unit"])
print("Registros:", payload_lme["count"])
print("Exemplo:", payload_lme["data"][:2])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Normalizar o JSON em DataFrame
# MAGIC O JSON tem um envelope (`source`, `count`, `data`). O que vira tabela é a **lista `data`**.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Pegue a lista data do JSON e crie um DataFrame Spark com colunas date e
# MAGIC > lme_price_usd_ton, convertendo date para tipo date."*

# COMMAND ----------

from pyspark.sql import functions as F

lme_df = (
    spark.createDataFrame(payload_lme["data"])
    .withColumn("date", F.to_date("date"))
    .withColumn("lme_price_usd_ton", F.col("lme_price_usd_ton").cast("double"))
)
lme_df.orderBy("date").show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Repetir para o câmbio USD/BRL
# MAGIC Mesmo padrão, outro endpoint. (Boa hora para pedir ao Assistant: *"faça o mesmo para /fx/usdbrl"*.)

# COMMAND ----------

resp_fx = requests.get(f"{API_BASE}/fx/usdbrl", params=params, headers=headers, timeout=30)
resp_fx.raise_for_status()
payload_fx = resp_fx.json()

fx_df = (
    spark.createDataFrame(payload_fx["data"])
    .withColumn("date", F.to_date("date"))
    .withColumn("usd_brl", F.col("usd_brl").cast("double"))
)
fx_df.orderBy("date").show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Salvar como Delta (camada bronze de mercado)

# COMMAND ----------

lme_df.write.format("delta").mode("overwrite").option("overwriteSchema", True).saveAsTable("market_lme_bronze")
fx_df.write.format("delta").mode("overwrite").option("overwriteSchema", True).saveAsTable("market_fx_bronze")
print("✅ market_lme_bronze e market_fx_bronze")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Juntar mercado × produção → margem preliminar
# MAGIC Agora unimos os dois mundos. Lemos a produção (custo de energia) e juntamos com preço LME × câmbio
# MAGIC **pela data**. O preço de venda em BRL = `LME (USD) × câmbio`. A **margem preliminar** = preço − custo.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Leia fact_production do volume landing, junte com market_lme_bronze e
# MAGIC > market_fx_bronze pela data, calcule o preço em reais por tonelada (lme × câmbio) e a margem por
# MAGIC > tonelada subtraindo o custo de energia por tonelada."*

# COMMAND ----------

LANDING = f"/Volumes/{CATALOG}/raw/landing"

producao = (
    spark.read.option("header", True).option("inferSchema", True)
    .csv(f"{LANDING}/fact_production.csv")
    .withColumn("date", F.to_date("date"))
)

margem = (
    producao
    .join(spark.read.table("market_lme_bronze"), on="date", how="inner")
    .join(spark.read.table("market_fx_bronze"), on="date", how="inner")
    .withColumn("preco_brl_ton", F.round(F.col("lme_price_usd_ton") * F.col("usd_brl"), 2))
    .withColumn("custo_energia_brl_ton", F.round(F.col("energy_cost_brl") / F.col("tons_produced"), 2))
    .withColumn("margem_preliminar_brl_ton",
                F.round(F.col("preco_brl_ton") - F.col("custo_energia_brl_ton"), 2))
    .select("date", "plant_id", "furnace_id", "product_id", "tons_produced",
            "lme_price_usd_ton", "usd_brl", "preco_brl_ton",
            "custo_energia_brl_ton", "margem_preliminar_brl_ton")
)

margem.write.format("delta").mode("overwrite").option("overwriteSchema", True).saveAsTable("gold_margem_preliminar")
margem.orderBy("date").show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC > ⚠️ **Margem "preliminar":** consideramos só o **custo de energia**. A margem real inclui matéria-prima
# MAGIC > (alumina), mão de obra, overhead e o **prêmio** sobre o LME por liga/produto. Mesmo assim já dá para
# MAGIC > ver a **sensibilidade ao câmbio** que foi citada na reunião: quando o dólar sobe, o preço em BRL sobe.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Margem média por dia: dá para ver o efeito do câmbio e do preço LME
# MAGIC SELECT date,
# MAGIC        ROUND(AVG(preco_brl_ton), 2)              AS preco_brl_ton,
# MAGIC        ROUND(AVG(margem_preliminar_brl_ton), 2)  AS margem_brl_ton
# MAGIC FROM gold_margem_preliminar
# MAGIC GROUP BY date ORDER BY date
# MAGIC LIMIT 15;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Exercício
# MAGIC 1. Sem filtro de data, traga o **período inteiro** da API (remova `start`/`end`) e recalcule.
# MAGIC 2. Em que **dia** a margem média foi a **menor**? O que aconteceu com o câmbio nesse dia?
# MAGIC    (Peça o gráfico ao Assistant: *"plote a margem média e o câmbio por dia no mesmo período"*.)
# MAGIC
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - JSON da LME e do câmbio retornando status 200.
# MAGIC - `market_lme_bronze` e `market_fx_bronze` criadas.
# MAGIC - `gold_margem_preliminar` com `preco_brl_ton` e `margem_preliminar_brl_ton`.
# MAGIC
# MAGIC **Próximo:** `06_dlt_pipeline` — recriar o medalhão de forma **declarativa** (Lakeflow / DLT).
