# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup do Ambiente — Trilha Tech 2026 | Engenharia
# MAGIC
# MAGIC ## "Do Forno ao Mercado" 🏭 → 💰
# MAGIC
# MAGIC Bem-vindo(a) à **Trilha de Engenharia de Dados**! Ao longo do workshop vamos:
# MAGIC
# MAGIC 1. **Ingerir** a telemetria dos fornos da CBA (o sistema **Gorila** das salas fornos)
# MAGIC    e os dados de **mercado** (preço do alumínio na LME + câmbio USD/BRL).
# MAGIC 2. **Integrar** as bases através de chaves (IDs).
# MAGIC 3. **Transformar** tudo numa **arquitetura medalhão** (bronze → prata → ouro)
# MAGIC    para chegar à **margem**: quanto custa produzir × por quanto o mercado paga.
# MAGIC
# MAGIC > 💡 **Genie Code / Databricks Assistant é o nosso copiloto.** Em cada módulo você verá
# MAGIC > um quadro **💬 Genie Code** com o texto exato para digitar no Assistant (em português!),
# MAGIC > deixar ele gerar o código, e então **revisar e entender**. Use `/explain` para ele explicar
# MAGIC > qualquer célula e `/fix` quando der erro. Ninguém precisa decorar sintaxe hoje. 😉
# MAGIC
# MAGIC ---
# MAGIC ### O que este notebook faz
# MAGIC - Verifica seu acesso ao Unity Catalog.
# MAGIC - Cria o catálogo `cba_trilha_tech` e os schemas (`raw` + o **seu schema pessoal**).
# MAGIC - Cria o **Volume** `raw.landing` onde ficam os arquivos brutos.
# MAGIC - Confirma que os arquivos CSV/Parquet foram carregados pelo instrutor.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração padrão (rode esta célula primeiro em TODOS os notebooks)
# MAGIC
# MAGIC Aqui definimos o catálogo, o schema bruto compartilhado e **um schema só seu** —
# MAGIC assim 30 pessoas trabalham no mesmo catálogo sem pisar no trabalho um do outro.

# COMMAND ----------

# Catálogo e schema bruto são COMPARTILHADOS pela turma toda
CATALOG = "cba_trilha_tech"
RAW_SCHEMA = "raw"

# Descobrimos quem é você e derivamos um schema pessoal: ws_<seu_usuario>
username = spark.sql("SELECT current_user()").collect()[0][0]
user_schema = "ws_" + username.split("@")[0].replace(".", "_").replace("-", "_")

print(f"👤 Usuário ......: {username}")
print(f"📦 Catálogo .....: {CATALOG}")
print(f"🗂️  Schema bruto .: {RAW_SCHEMA}  (compartilhado)")
print(f"🙋 Seu schema ...: {user_schema}  (só seu)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Criar catálogo e schemas
# MAGIC
# MAGIC > 💬 **Genie Code** — experimente digitar no Assistant:
# MAGIC > *"Crie o catálogo cba_trilha_tech e dois schemas: raw e um schema pessoal a partir do usuário atual, se não existirem, e selecione o catálogo."*
# MAGIC >
# MAGIC > Compare o que o Assistant gerar com o código abaixo. Use `/explain` para entender cada comando.

# COMMAND ----------

catalogos = [row.catalog for row in spark.sql("SHOW CATALOGS").collect()]
if CATALOG not in catalogos:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{RAW_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{user_schema}")

# A partir daqui, tabelas sem prefixo caem no SEU schema
spark.sql(f"USE SCHEMA {user_schema}")
print(f"✅ Pronto. Trabalhando em {CATALOG}.{user_schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Criar o Volume `raw.landing` (área de pouso dos arquivos brutos)
# MAGIC
# MAGIC Um **Volume** do Unity Catalog é uma pasta governada para arquivos (CSV, Parquet, JSON…).
# MAGIC É onde o instrutor sobe os dados brutos da CBA. O caminho é sempre:
# MAGIC `/Volumes/<catálogo>/<schema>/<volume>/...`

# COMMAND ----------

spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{RAW_SCHEMA}.landing")
LANDING = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/landing"
print(f"✅ Volume pronto: {LANDING}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Carregar os dados brutos no Volume
# MAGIC
# MAGIC **Quem sobe os arquivos?** O **instrutor** sobe os CSV/Parquet uma vez para a turma toda,
# MAGIC via:
# MAGIC - **Catalog Explorer** → `cba_trilha_tech` → `raw` → `landing` → botão **Upload to this volume**, ou
# MAGIC - Databricks CLI: `databricks fs cp ./output/ dbfs:/Volumes/cba_trilha_tech/raw/landing/ --recursive`
# MAGIC
# MAGIC Esperamos encontrar no Volume:
# MAGIC - `furnace_telemetry.csv` (telemetria completa do Gorila, ~864 mil linhas)
# MAGIC - `furnace_telemetry.parquet` (mesma coisa, formato colunar)
# MAGIC - `sample/furnace_telemetry_sample.csv` (10 mil linhas, para o módulo "subir CSV")
# MAGIC - `dim_plantas.csv`, `dim_ligas.csv`, `dim_produtos.csv`, `dim_fornos.csv`
# MAGIC - `furnace_inspections.csv`
# MAGIC - `aluminum_lme_price.csv`, `fx_usdbrl.csv`
# MAGIC - `fact_production.csv`, `fact_sales.csv`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Verificar — quais arquivos estão no Volume?
# MAGIC
# MAGIC > 💬 **Genie Code:** *"Liste todos os arquivos do volume /Volumes/cba_trilha_tech/raw/landing,
# MAGIC > incluindo as subpastas, mostrando nome e tamanho."*

# COMMAND ----------

import os

def listar_volume(caminho: str):
    achados = []
    for dirpath, _dirs, files in os.walk(caminho):
        for f in files:
            full = os.path.join(dirpath, f)
            achados.append((full.replace(caminho, "").lstrip("/"), os.path.getsize(full)))
    return sorted(achados)

arquivos = listar_volume(LANDING)
if not arquivos:
    print("⚠️  Nenhum arquivo encontrado. Peça ao instrutor para subir os dados no Volume.")
else:
    print(f"✅ {len(arquivos)} arquivo(s) no Volume:\n")
    for nome, tamanho in arquivos:
        print(f"  {nome:<45} {tamanho/1_048_576:8.2f} MB")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Teste rápido de leitura
# MAGIC
# MAGIC Vamos espiar 5 linhas da telemetria só para confirmar que está tudo legível.

# COMMAND ----------

try:
    df_peek = spark.read.csv(f"{LANDING}/dim_plantas.csv", header=True, inferSchema=True)
    print("Plantas da CBA neste workshop:")
    df_peek.show(truncate=False)
except Exception as e:
    print(f"⚠️  Não consegui ler dim_plantas.csv ({e}). Verifique o upload no passo 4.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint
# MAGIC Você deve ver:
# MAGIC - O catálogo `cba_trilha_tech` e seu schema pessoal `ws_...` criados.
# MAGIC - O Volume `raw.landing` listando os arquivos da CBA.
# MAGIC - As 4 plantas da CBA na última célula (Alumínio-SP, Miraí, Poços de Caldas, Zona da Mata).
# MAGIC
# MAGIC **Próximo:** `01_upload_csv` — como subir e consumir um CSV (o básico, do zero).
