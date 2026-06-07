# Databricks notebook source
# MAGIC %md
# MAGIC # 🤖 Módulo 7 — Agente de RCA de Manutenção (Mosaic AI Agent Framework)
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA**
# MAGIC
# MAGIC Vamos construir um **assistente de RCA** (Root Cause Analysis / análise de causa raiz) de
# MAGIC manutenção dos fornos. Um engenheiro pergunta em **português** — *"Por que a cuba 7 está
# MAGIC consumindo tanta energia?"* — e o agente:
# MAGIC 1. Consulta a **telemetria** e a **qualidade** do forno via **funções UC** (suas ferramentas).
# MAGIC 2. (Opcional) Busca trechos de **manuais de manutenção** via **Vector Search**.
# MAGIC 3. Raciocina com um **Foundation Model** (LLM pré-provisionado pay-per-token) e responde.
# MAGIC
# MAGIC Usamos o **Mosaic AI Agent Framework**: ferramentas declaradas como **funções no Unity
# MAGIC Catalog**, o agente montado com `databricks-langchain`, e **avaliação com MLflow + LLM judges**.
# MAGIC
# MAGIC ### 🎮 Ponto de partida: AI Playground
# MAGIC Antes de codar, abra o **AI Playground** (barra lateral). Lá você escolhe um Foundation Model,
# MAGIC **anexa funções UC como tools** e testa o agente **sem escrever código**. É a forma mais
# MAGIC rápida de prototipar — e de nivelar a turma. Este notebook formaliza o que se prototipa lá.
# MAGIC
# MAGIC ---
# MAGIC ### 💬 Genie Code
# MAGIC > *"Crie uma função SQL no Unity Catalog que recebe um furnace_id e retorna as médias de
# MAGIC > temperatura, amperagem, efeito anódico e vibração desse forno na tabela furnace_telemetry."*

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Instalar as bibliotecas do Agent Framework
# MAGIC No Databricks Runtime ML recente já vêm muitas; fixamos as principais para reprodutibilidade.

# COMMAND ----------

# MAGIC %pip install -U -qqqq databricks-langchain databricks-agents mlflow langgraph unitycatalog-ai unitycatalog-langchain
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração

# COMMAND ----------

import mlflow

CATALOG = "cba_trilha_tech"
current_user = spark.sql("SELECT current_user()").collect()[0][0]
user_prefix = current_user.split("@")[0].replace(".", "_").replace("-", "_")
SCHEMA = f"mlops_{user_prefix}"
GOLD = f"{CATALOG}.gold"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
mlflow.set_registry_uri("databricks-uc")

# Foundation Model pré-provisionado (pay-per-token). Claude está disponível como endpoint
# nativo no Databricks; se sua workspace não tiver, troque por outro FM da lista de
# "Serving -> Foundation models" (ex.: databricks-meta-llama-3-3-70b-instruct).
LLM_ENDPOINT = "databricks-claude-3-7-sonnet"

print(f"Schema do aluno: {CATALOG}.{SCHEMA}")
print(f"LLM endpoint   : {LLM_ENDPOINT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Ferramentas do agente — Funções no Unity Catalog
# MAGIC As **tools** do agente são funções UC. Vantagem: governadas, reutilizáveis, auditáveis e
# MAGIC chamáveis por SQL, pelo Playground e pelo agente. Criamos três:
# MAGIC - `get_furnace_telemetry_stats(furnace_id)` — estado operacional médio do forno.
# MAGIC - `get_furnace_quality(furnace_id)` — taxa de defeito e qualidade média do forno.
# MAGIC - `get_furnace_failure_rate(furnace_id)` — taxa de falha (`is_failure`) do forno.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_furnace_telemetry_stats(furnace_id_in INT)
RETURNS TABLE (
  avg_temperature_c DOUBLE, avg_amperage_ka DOUBLE,
  avg_anode_effect DOUBLE, avg_vibration_mm_s DOUBLE, avg_energy_kwh_ton DOUBLE
)
COMMENT 'Retorna o estado operacional médio (temperatura, amperagem, efeito anódico, vibração, energia) de uma cuba/forno a partir da telemetria.'
RETURN
  SELECT avg(temperature_c), avg(amperage_ka), avg(anode_effect),
         avg(vibration_mm_s), avg(energy_kwh_ton)
  FROM {GOLD}.furnace_telemetry
  WHERE furnace_id = furnace_id_in
""")
print("Função criada: get_furnace_telemetry_stats")

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_furnace_quality(furnace_id_in INT)
RETURNS TABLE (n_inspections BIGINT, defect_rate_pct DOUBLE, avg_surface_quality DOUBLE)
COMMENT 'Retorna o número de inspeções, a taxa de defeito (%) e a qualidade média de superfície de uma cuba/forno.'
RETURN
  SELECT count(*),
         round(avg(is_defect) * 100, 2),
         round(avg(surface_quality_score), 3)
  FROM {GOLD}.furnace_inspections
  WHERE furnace_id = furnace_id_in
""")
print("Função criada: get_furnace_quality")

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_furnace_failure_rate(furnace_id_in INT)
RETURNS TABLE (n_readings BIGINT, failure_rate_pct DOUBLE)
COMMENT 'Retorna o total de leituras e a taxa de falha (%) registrada na telemetria de uma cuba/forno.'
RETURN
  SELECT count(*), round(avg(is_failure) * 100, 3)
  FROM {GOLD}.furnace_telemetry
  WHERE furnace_id = furnace_id_in
""")
print("Função criada: get_furnace_failure_rate")

# COMMAND ----------

# MAGIC %md
# MAGIC Testando uma função diretamente em SQL (é assim que o agente vai chamá-la por baixo):

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.get_furnace_telemetry_stats(7)"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Montar o agente com `databricks-langchain`
# MAGIC Carregamos as funções UC como ferramentas (`UCFunctionToolkit`) e ligamos a um Foundation
# MAGIC Model via `ChatDatabricks`. O `create_react_agent` (LangGraph) cuida do loop de raciocínio
# MAGIC e chamada de ferramentas.

# COMMAND ----------

from databricks_langchain import ChatDatabricks
from databricks_langchain.uc_ai import (
    UCFunctionToolkit, DatabricksFunctionClient, set_uc_function_client,
)
from langgraph.prebuilt import create_react_agent

client = DatabricksFunctionClient()
set_uc_function_client(client)

# As três funções UC viram ferramentas do agente
toolkit = UCFunctionToolkit(function_names=[
    f"{CATALOG}.{SCHEMA}.get_furnace_telemetry_stats",
    f"{CATALOG}.{SCHEMA}.get_furnace_quality",
    f"{CATALOG}.{SCHEMA}.get_furnace_failure_rate",
])
tools = toolkit.tools

llm = ChatDatabricks(endpoint=LLM_ENDPOINT, temperature=0.1)

SYSTEM_PROMPT = (
    "Você é um assistente de manutenção (RCA) das cubas eletrolíticas da CBA. "
    "Responda SEMPRE em português do Brasil, de forma técnica e objetiva. "
    "Use as ferramentas disponíveis para consultar telemetria, qualidade e taxa de falha "
    "de um forno antes de concluir. Quando identificar uma possível causa raiz (ex.: efeito "
    "anódico alto, desvio de temperatura, vibração elevada, baixa qualidade de superfície), "
    "explique o raciocínio e sugira uma ação de manutenção. Se faltar o número do forno, peça."
)

agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
print("Agente de RCA montado.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Testar perguntas em português

# COMMAND ----------

def ask(question: str):
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    answer = result["messages"][-1].content
    print(f"❓ {question}\n")
    print(f"🤖 {answer}\n")
    return answer

_ = ask("Por que a cuba 7 pode estar consumindo tanta energia? Investigue a telemetria.")

# COMMAND ----------

_ = ask("O forno 3 tem problema de qualidade? Qual a taxa de defeito e a qualidade de superfície?")

# COMMAND ----------

_ = ask("Compare a taxa de falha dos fornos 1 e 5 e diga qual exige mais atenção de manutenção.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. (Opcional) Vector Search sobre manuais de manutenção
# MAGIC Para responder *"qual o procedimento para efeito anódico recorrente?"*, o agente precisa de
# MAGIC **conhecimento textual** (manuais). Criamos manuais **sintéticos**, indexamos com **Mosaic AI
# MAGIC Vector Search** e adicionamos a busca como mais uma ferramenta.
# MAGIC
# MAGIC > Esta seção exige um **Vector Search endpoint**. Se a sala não tiver, pule — o agente já
# MAGIC > funciona só com as funções UC. O instrutor avisa se está disponível.
# MAGIC
# MAGIC ### 💬 Genie Code
# MAGIC > *"Crie uma tabela com 5 trechos de manuais de manutenção de fornos de alumínio (id, título,
# MAGIC > conteúdo) e habilite Change Data Feed nela."*

# COMMAND ----------

# Manuais sintéticos (conhecimento de domínio para o RAG)
manuais = [
    (1, "Efeito anódico recorrente",
     "Efeito anódico recorrente indica baixa concentração de alumina no banho. "
     "Verifique o sistema de alimentação de alumina (alumina_feed_rate), ajuste a dosagem "
     "e inspecione os anodos. Reduz consumo de energia e emissões de PFC."),
    (2, "Desvio de temperatura do banho",
     "A temperatura ideal do banho é ~960 C. Desvios acima de 965 C aumentam o consumo de "
     "energia (kWh/ton) e o desgaste do revestimento. Ajuste a corrente (amperage_ka) e a "
     "razão de banho (bath_ratio)."),
    (3, "Vibração elevada",
     "Vibração acima de 4 mm/s sugere desbalanceamento mecânico ou folga estrutural. "
     "Agende inspeção mecânica e verifique a fixação das barras catódicas."),
    (4, "Baixa qualidade de superfície",
     "Quedas em surface_quality_score correlacionam com porosidade e inclusões. "
     "Revise a filtragem do metal líquido e a temperatura de vazamento."),
    (5, "Alta taxa de falha",
     "Taxa de falha elevada combina efeito anódico, vibração e desvio térmico. "
     "Priorize manutenção preditiva no forno e monitore os três sinais em conjunto."),
]
df_manuais = spark.createDataFrame(manuais, ["id", "titulo", "conteudo"])
MANUALS_TABLE = f"{CATALOG}.{SCHEMA}.maintenance_manuals"
(df_manuais.write.mode("overwrite")
 .option("delta.enableChangeDataFeed", "true")
 .saveAsTable(MANUALS_TABLE))
print(f"Tabela de manuais criada: {MANUALS_TABLE}")

# COMMAND ----------

# Cria o índice de Vector Search (managed embeddings). Requer um VS endpoint existente.
from databricks.vector_search.client import VectorSearchClient

VS_ENDPOINT = "cba_trilha_vs"  # nome do endpoint de Vector Search (provisionado pelo instrutor)
VS_INDEX = f"{CATALOG}.{SCHEMA}.maintenance_manuals_index"

try:
    vsc = VectorSearchClient(disable_notice=True)
    vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT,
        index_name=VS_INDEX,
        source_table_name=MANUALS_TABLE,
        pipeline_type="TRIGGERED",
        primary_key="id",
        embedding_source_column="conteudo",
        embedding_model_endpoint_name="databricks-gte-large-en",
    )
    print(f"Índice de Vector Search criado: {VS_INDEX} (sincronizando...)")
except Exception as e:
    print(f"(Pulei o Vector Search — endpoint indisponível ou índice já existe: {e})")

# COMMAND ----------

# MAGIC %md
# MAGIC Adicionamos a busca vetorial como ferramenta de **retrieval** e remontamos o agente.
# MAGIC Agora ele combina **dados estruturados** (funções UC) com **conhecimento textual** (manuais).

# COMMAND ----------

try:
    from databricks_langchain import VectorSearchRetrieverTool

    retriever_tool = VectorSearchRetrieverTool(
        index_name=VS_INDEX,
        num_results=2,
        tool_name="buscar_manuais_manutencao",
        tool_description="Busca trechos de manuais de manutenção de fornos de alumínio por similaridade semântica.",
    )
    agent = create_react_agent(llm, tools + [retriever_tool], prompt=SYSTEM_PROMPT)
    _ = ask("Qual o procedimento de manutenção para efeito anódico recorrente no forno 7?")
except Exception as e:
    print(f"(Vector Search não disponível — seguindo apenas com as funções UC: {e})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Avaliar o agente com MLflow (LLM-as-judge)
# MAGIC Como saber se o agente está **bom**? Montamos um conjunto de avaliação e usamos
# MAGIC `mlflow.evaluate` com **juízes LLM** (relevância, fundamentação/groundedness, segurança).
# MAGIC Isso traz rigor de MLOps também para agentes.
# MAGIC
# MAGIC ### 💬 Genie Code
# MAGIC > *"Monte um DataFrame de avaliação com perguntas sobre fornos e use mlflow.evaluate com
# MAGIC > model_type 'databricks-agent' para avaliar o agente."*

# COMMAND ----------

import pandas as pd

eval_data = pd.DataFrame({
    "request": [
        "Por que a cuba 7 consome muita energia?",
        "O forno 3 tem problema de qualidade?",
        "Qual a taxa de falha do forno 1?",
        "O que fazer com efeito anódico recorrente?",
    ],
})

def agent_predict(model_input: pd.DataFrame) -> list[str]:
    out = []
    for q in model_input["request"]:
        res = agent.invoke({"messages": [{"role": "user", "content": q}]})
        out.append(res["messages"][-1].content)
    return out

mlflow.set_experiment(f"/Users/{current_user}/cba_rca_agent_eval")
with mlflow.start_run(run_name="rca_agent_eval"):
    results = mlflow.evaluate(
        model=lambda df: agent_predict(df),
        data=eval_data,
        model_type="databricks-agent",  # ativa os LLM judges do Mosaic AI Agent Eval
    )
    print("Métricas de avaliação do agente:")
    print(results.metrics)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Registrar e servir o agente
# MAGIC Empacotamos o agente como modelo MLflow (sabor LangChain) no Unity Catalog. A partir dele,
# MAGIC `agents.deploy(...)` cria um endpoint de serving com app de review embutido.
# MAGIC
# MAGIC > Em produção, o padrão recomendado é escrever o agente como `ChatAgent` em um arquivo
# MAGIC > `agent.py` e logar com `mlflow.pyfunc.log_model(... resources=[...])`. Aqui usamos o
# MAGIC > caminho LangChain por simplicidade didática.

# COMMAND ----------

from mlflow.models.resources import DatabricksFunction, DatabricksServingEndpoint

AGENT_MODEL = f"{CATALOG}.{SCHEMA}.rca_maintenance_agent"

with mlflow.start_run(run_name="rca_agent_register"):
    logged = mlflow.langchain.log_model(
        lc_model=agent,
        artifact_path="agent",
        registered_model_name=AGENT_MODEL,
        # Declarar os recursos garante que o serving tenha permissão para chamá-los
        resources=[
            DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT),
            DatabricksFunction(function_name=f"{CATALOG}.{SCHEMA}.get_furnace_telemetry_stats"),
            DatabricksFunction(function_name=f"{CATALOG}.{SCHEMA}.get_furnace_quality"),
            DatabricksFunction(function_name=f"{CATALOG}.{SCHEMA}.get_furnace_failure_rate"),
        ],
    )
print(f"Agente registrado no UC: {AGENT_MODEL}")

# COMMAND ----------

# Implanta o agente como endpoint (cria também o Review App). Pode levar alguns minutos.
try:
    from databricks import agents
    deployment = agents.deploy(
        model_name=AGENT_MODEL,
        model_version=logged.registered_model_version,
    )
    print(f"Agente implantado. Endpoint: {deployment.endpoint_name}")
    print("Abra o Review App para coletar feedback de especialistas (engenheiros de manutenção).")
except Exception as e:
    print(f"(Deploy opcional — pode exigir permissões/tempo: {e})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint do Módulo 7
# MAGIC - [ ] Criei **funções UC** como ferramentas do agente (telemetria, qualidade, falha).
# MAGIC - [ ] Montei o agente com `databricks-langchain` + Foundation Model e testei em português.
# MAGIC - [ ] (Opcional) Indexei manuais com **Vector Search** e adicionei retrieval ao agente.
# MAGIC - [ ] Avaliei o agente com **MLflow + LLM judges**.
# MAGIC - [ ] Registrei (e opcionalmente implantei) o agente no Unity Catalog.
# MAGIC
# MAGIC ### 🎯 Exercício
# MAGIC Adicione uma quarta função UC que retorne o **modelo e a planta** do forno (join com
# MAGIC `dim_fornos` e `dim_plantas`) e ligue-a ao agente. Pergunte: *"Em qual planta está o forno 7
# MAGIC e qual o modelo dele?"*. Depois, use o **AI Playground** para reproduzir o agente sem código.
# MAGIC
# MAGIC ---
# MAGIC ## 🎓 Encerramento da trilha
# MAGIC Você percorreu o ciclo **CRISP-DM** completo no Databricks: do **entendimento do negócio** e
# MAGIC **EDA** à **modelagem** (regressão + classificação), **avaliação/governança** (champion/
# MAGIC challenger no UC), **implantação** (serving + `ai_query`) e um **agente de IA** — sempre
# MAGIC apoiado pelo **Genie Code** para nivelar a turma. Do forno ao mercado, ponta a ponta.
