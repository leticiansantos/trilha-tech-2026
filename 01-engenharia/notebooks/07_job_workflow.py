# Databricks notebook source
# MAGIC %md
# MAGIC # 07 · Orquestração: Jobs & Workflows
# MAGIC ### "Criar um job" — colocar o pipeline para rodar sozinho, no horário certo
# MAGIC
# MAGIC Já temos as peças: ingestão (módulos 01–05) e o pipeline declarativo (módulo 06). Mas hoje rodamos
# MAGIC tudo **na mão**. Em produção, isso precisa rodar **automaticamente** — toda madrugada, na ordem certa,
# MAGIC e avisar alguém se falhar. É o papel do **Job / Workflow** do Databricks (Lakeflow Jobs).
# MAGIC
# MAGIC Um Job é um **grafo de tarefas** com **dependências** e **agendamento**. Vamos montar:
# MAGIC
# MAGIC ```
# MAGIC [1] ingest_mercado (notebook 05)  ─┐
# MAGIC                                    ├─►  [3] pipeline_medalhao (DLT do módulo 06)
# MAGIC [2] preparar_dimensoes (nb 04)   ─┘
# MAGIC ```
# MAGIC
# MAGIC > 💬 Você pode pedir o JSON/YAML do Job ao Assistant e revisar. As duas formas (UI e código) levam ao mesmo lugar.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Criar o Job pela UI (caminho recomendado para a turma)
# MAGIC
# MAGIC 1. Menu lateral → **Jobs & Pipelines** → **Create** → **Job**.
# MAGIC 2. Nome: `cba_engenharia_forno_ao_mercado_<seu_nome>`.
# MAGIC 3. **Tarefa 1 — `preparar_dimensoes`**
# MAGIC    - Type: **Notebook** → selecione `04_join_by_id`.
# MAGIC 4. **Tarefa 2 — `ingest_mercado`**
# MAGIC    - Type: **Notebook** → `05_market_api_ingest`.
# MAGIC    - Em **Parameters**, passe `api_base` com a URL da API.
# MAGIC    - **Depends on:** (deixe vazio — roda em paralelo com a 1).
# MAGIC 5. **Tarefa 3 — `pipeline_medalhao`**
# MAGIC    - Type: **Pipeline** → selecione o pipeline DLT criado no módulo 06.
# MAGIC    - **Depends on:** `preparar_dimensoes` **e** `ingest_mercado`.
# MAGIC 6. **Schedule:** botão **Add trigger** → **Scheduled** → diário às **03:00** (cron `0 0 3 * * ?`).
# MAGIC 7. **Notifications:** adicione seu e-mail em **on failure**.
# MAGIC 8. **Run now** para testar.
# MAGIC
# MAGIC > ✅ A grande sacada: a tarefa 3 só começa quando 1 **e** 2 terminam com sucesso. Isso são as **dependências**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. O mesmo Job como código (JSON da API de Jobs)
# MAGIC A UI gera exatamente isto por baixo. Útil para versionar no Git / Asset Bundles.
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Gere o JSON de um Databricks Job com três tarefas: duas de notebook em paralelo
# MAGIC > e uma terceira de pipeline que depende das duas, com agendamento diário às 3h e notificação por e-mail."*

# COMMAND ----------

job_json = """
{
  "name": "cba_engenharia_forno_ao_mercado",
  "tasks": [
    {
      "task_key": "preparar_dimensoes",
      "notebook_task": { "notebook_path": "/Workspace/.../notebooks/04_join_by_id" }
    },
    {
      "task_key": "ingest_mercado",
      "notebook_task": {
        "notebook_path": "/Workspace/.../notebooks/05_market_api_ingest",
        "base_parameters": { "api_base": "https://SUA_API_AQUI" }
      }
    },
    {
      "task_key": "pipeline_medalhao",
      "depends_on": [
        { "task_key": "preparar_dimensoes" },
        { "task_key": "ingest_mercado" }
      ],
      "pipeline_task": { "pipeline_id": "<ID_DO_PIPELINE_DO_MODULO_06>" }
    }
  ],
  "schedule": {
    "quartz_cron_expression": "0 0 3 * * ?",
    "timezone_id": "America/Sao_Paulo",
    "pause_status": "UNPAUSED"
  },
  "email_notifications": { "on_failure": ["seu.email@cba.com.br"] },
  "queue": { "enabled": true }
}
"""
print(job_json)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. O mesmo Job como YAML (Databricks Asset Bundles — DABs)
# MAGIC Para quem vai versionar no Git, o padrão moderno é o **Databricks Asset Bundle**: você descreve o Job
# MAGIC em YAML e faz `databricks bundle deploy`. É o que usamos no `deployment/` deste workshop.

# COMMAND ----------

# MAGIC %md
# MAGIC ```yaml
# MAGIC # resources/forno_ao_mercado.job.yml
# MAGIC resources:
# MAGIC   jobs:
# MAGIC     forno_ao_mercado:
# MAGIC       name: cba_engenharia_forno_ao_mercado
# MAGIC       schedule:
# MAGIC         quartz_cron_expression: "0 0 3 * * ?"
# MAGIC         timezone_id: America/Sao_Paulo
# MAGIC       email_notifications:
# MAGIC         on_failure: ["seu.email@cba.com.br"]
# MAGIC       tasks:
# MAGIC         - task_key: preparar_dimensoes
# MAGIC           notebook_task:
# MAGIC             notebook_path: ../notebooks/04_join_by_id.py
# MAGIC         - task_key: ingest_mercado
# MAGIC           notebook_task:
# MAGIC             notebook_path: ../notebooks/05_market_api_ingest.py
# MAGIC             base_parameters:
# MAGIC               api_base: ${var.api_base}
# MAGIC         - task_key: pipeline_medalhao
# MAGIC           depends_on:
# MAGIC             - task_key: preparar_dimensoes
# MAGIC             - task_key: ingest_mercado
# MAGIC           pipeline_task:
# MAGIC             pipeline_id: ${resources.pipelines.medalhao.id}
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Disparar / monitorar pelo SDK (opcional, avançado)
# MAGIC Dá para controlar Jobs por código com o **Databricks SDK** (já instalado no Runtime).
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Use o databricks-sdk para listar os jobs cujo nome contém 'cba_engenharia'
# MAGIC > e mostrar o id e o nome."*

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
encontrados = [j for j in w.jobs.list() if "cba_engenharia" in (j.settings.name or "")]
if encontrados:
    for j in encontrados:
        print(f"job_id={j.job_id}  nome={j.settings.name}")
    # Para disparar: w.jobs.run_now(job_id=encontrados[0].job_id)
else:
    print("Nenhum job 'cba_engenharia' ainda. Crie pela UI (passo 1) e rode esta célula de novo.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Exercício
# MAGIC 1. Adicione uma **4ª tarefa** que roda um notebook de **validação** (ex.: confere que
# MAGIC    `telemetry_gold_dlt` tem linhas) **depois** do pipeline, e que **envia e-mail no sucesso**.
# MAGIC 2. Configure **retry** (2 tentativas) na tarefa de ingestão da API — APIs externas falham às vezes.
# MAGIC
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - Um Job com 3 tarefas e o grafo de dependências desenhado.
# MAGIC - Uma execução (**Run now**) verde ponta a ponta.
# MAGIC - O agendamento diário configurado e a notificação de falha no seu e-mail.
# MAGIC
# MAGIC 🎉 **Fim da trilha!** Do CSV bruto ao Job agendado que entrega a margem "Do Forno ao Mercado".
