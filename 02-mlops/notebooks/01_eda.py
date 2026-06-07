# Databricks notebook source
# MAGIC %md
# MAGIC # 🏭 Módulo 1 — CRISP-DM: Entendimento do Negócio & Análise Exploratória (EDA)
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA (Companhia Brasileira de Alumínio)**
# MAGIC
# MAGIC ## Narrativa: "Do Forno ao Mercado"
# MAGIC O custo de produção do alumínio é dominado pela **energia** consumida nas cubas eletrolíticas
# MAGIC (sistema **Gorila** de telemetria). O preço de venda depende do **mercado** (LME + dólar).
# MAGIC A margem da CBA = (preço de mercado) − (custo de produção). Nesta trilha de **MLOps**,
# MAGIC consumimos as tabelas **GOLD** produzidas pela trilha de Engenharia e construímos:
# MAGIC
# MAGIC 1. 🔢 **Regressão** — prever `energy_kwh_ton` (eficiência energética do forno) → ataca o **custo**.
# MAGIC 2. ⚠️ **Classificação binária** — prever `is_defect` (qualidade) → ataca a **perda/retrabalho**.
# MAGIC 3. 🤖 **Agente de RCA** — assistente de análise de causa raiz de manutenção dos fornos.
# MAGIC
# MAGIC ## O ciclo CRISP-DM (nosso mapa do workshop)
# MAGIC `Entendimento do Negócio → Entendimento dos Dados (EDA) → Preparação → Modelagem → Avaliação → Implantação`
# MAGIC
# MAGIC Este módulo cobre as duas primeiras etapas. **Vamos entender o problema e os dados antes de modelar.**
# MAGIC
# MAGIC ---
# MAGIC ### 💬 Genie Code ("vibe code") neste workshop
# MAGIC Em **todos** os módulos você vai gerar código a partir de linguagem natural usando o
# MAGIC **Databricks Assistant**. Abra o painel do Assistant (ícone ✨ na barra lateral ou `Ctrl/Cmd + I`
# MAGIC dentro de uma célula) e digite o prompt em **português**. Depois:
# MAGIC - Use **/explain** para que o Assistant explique linha a linha o código gerado.
# MAGIC - Use **/fix** se aparecer um erro — cole a mensagem e peça a correção.
# MAGIC - **Sempre leia e entenda** o código antes de executar. O Assistant acelera, mas você decide.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração do ambiente
# MAGIC Definimos o catálogo compartilhado `cba_trilha_tech` e um **schema por usuário** (para que
# MAGIC cada aluno trabalhe isolado, sem sobrescrever o colega).

# COMMAND ----------

# Catálogo compartilhado da trilha (criado pela trilha de Engenharia)
CATALOG = "cba_trilha_tech"

# Schema por usuário: deriva do e-mail logado -> evita conflito entre alunos
current_user = spark.sql("SELECT current_user()").collect()[0][0]
user_prefix = current_user.split("@")[0].replace(".", "_").replace("-", "_")
SCHEMA = f"mlops_{user_prefix}"

print(f"Usuário ........: {current_user}")
print(f"Catálogo .......: {CATALOG}")
print(f"Seu schema .....: {SCHEMA}")

# Cria o schema do aluno (se ainda não existe) e define o contexto
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# As tabelas GOLD de origem ficam no schema 'gold' do catálogo da trilha
GOLD = f"{CATALOG}.gold"
print(f"Schema GOLD ....: {GOLD}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Entendimento dos dados — o que temos disponível?
# MAGIC As tabelas que vamos usar nesta trilha:
# MAGIC
# MAGIC | Tabela | Conteúdo | Uso |
# MAGIC |---|---|---|
# MAGIC | `furnace_telemetry` | Telemetria das cubas (Gorila): temperatura, amperagem, energia, vibração, `is_failure` | Regressão (energia) + manutenção preditiva |
# MAGIC | `furnace_inspections` | Inspeções de qualidade: `surface_quality_score`, `defect_type`, `is_defect` | **Classificação binária (alvo principal)** |
# MAGIC | `dim_fornos`, `dim_plantas`, `dim_ligas`, `dim_produtos` | Dimensões de negócio | Enriquecimento / contexto |
# MAGIC | `aluminum_lme_price`, `fx_usdbrl` | Mercado (LME + câmbio) | Contexto de margem |
# MAGIC
# MAGIC > **Nota didática:** se na sua sala as tabelas estiverem no schema padrão e não em `gold`,
# MAGIC > ajuste a variável `GOLD` acima. O instrutor confirma o nome no início do módulo.

# COMMAND ----------

# Lista as tabelas disponíveis no schema GOLD
display(spark.sql(f"SHOW TABLES IN {GOLD}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 💬 Genie Code
# MAGIC Em vez de digitar SQL na mão, peça ao Assistant. Em uma célula **SQL** (`%sql`), abra o
# MAGIC Assistant e digite:
# MAGIC
# MAGIC > *"Mostre as 20 primeiras linhas da tabela `cba_trilha_tech.gold.furnace_telemetry`
# MAGIC > ordenadas por ts."*
# MAGIC
# MAGIC Reveja o SQL gerado, rode, e use **/explain** para entender cada cláusula.

# COMMAND ----------

# Carregamos a telemetria em um DataFrame Spark e olhamos a estrutura
df_telemetry = spark.table(f"{GOLD}.furnace_telemetry")
print(f"Linhas de telemetria: {df_telemetry.count():,}")
df_telemetry.printSchema()
display(df_telemetry.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Estatísticas descritivas
# MAGIC Antes de modelar, precisamos conhecer a **escala**, a **dispersão** e os **valores típicos**
# MAGIC de cada variável. `describe()` dá um resumo rápido.

# COMMAND ----------

# Resumo estatístico das colunas numéricas da telemetria
display(df_telemetry.describe(
    "temperature_c", "amperage_ka", "bath_ratio", "anode_effect",
    "alumina_feed_rate", "energy_kwh_ton", "pressure_pa", "vibration_mm_s"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 💬 Genie Code
# MAGIC > *"Crie um DataFrame pandas com uma amostra de 50 mil linhas de
# MAGIC > `cba_trilha_tech.gold.furnace_telemetry` para eu fazer gráficos com matplotlib/seaborn."*
# MAGIC
# MAGIC Trabalhar com uma **amostra** em pandas é mais rápido para visualização. Para o
# MAGIC treino do modelo, voltaremos ao dataset completo (módulo 2).

# COMMAND ----------

# Amostra para visualização (pandas é confortável para gráficos)
pdf = (
    df_telemetry
    .select("temperature_c", "amperage_ka", "bath_ratio", "anode_effect",
            "alumina_feed_rate", "energy_kwh_ton", "vibration_mm_s", "is_failure")
    .sample(fraction=0.05, seed=42)
    .limit(50_000)
    .toPandas()
)
print(f"Amostra para EDA: {len(pdf):,} linhas")
pdf.head()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Tratamento de valores nulos
# MAGIC O sensor de **vibração** (`vibration_mm_s`) tem ~1% de leituras faltantes (sensor offline).
# MAGIC Decidir o que fazer com nulos é parte central da **preparação dos dados** (CRISP-DM).

# COMMAND ----------

from pyspark.sql import functions as F

# Conta nulos por coluna no dataset COMPLETO (não na amostra)
null_counts = df_telemetry.select([
    F.sum(F.col(c).isNull().cast("int")).alias(c)
    for c in ["temperature_c", "amperage_ka", "bath_ratio", "anode_effect",
              "alumina_feed_rate", "energy_kwh_ton", "pressure_pa",
              "vibration_mm_s", "is_failure"]
])
display(null_counts)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 💬 Genie Code
# MAGIC > *"Calcule o percentual de valores nulos em `vibration_mm_s` na tabela
# MAGIC > `cba_trilha_tech.gold.furnace_telemetry` e mostre o resultado em porcentagem."*
# MAGIC
# MAGIC **Estratégia adotada:** como é ~1% e a vibração não é feature da regressão de energia,
# MAGIC vamos **imputar pela mediana** quando ela for usada (manutenção preditiva). Para a
# MAGIC regressão de energia, as features escolhidas não têm nulos.

# COMMAND ----------

# Imputação pela mediana (demonstração) — útil no módulo de manutenção preditiva
median_vibration = df_telemetry.approxQuantile("vibration_mm_s", [0.5], 0.01)[0]
print(f"Mediana da vibração (para imputação): {median_vibration:.3f} mm/s")

df_telemetry_imputed = df_telemetry.fillna({"vibration_mm_s": median_vibration})
remaining_nulls = df_telemetry_imputed.filter(F.col("vibration_mm_s").isNull()).count()
print(f"Nulos restantes após imputação: {remaining_nulls}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Correlações — a relação central: energia × temperatura
# MAGIC A hipótese de negócio é que **a energia consumida cresce com a temperatura e a amperagem**.
# MAGIC Se confirmarmos isso, temos boas *features* para a regressão. Vamos medir e visualizar.

# COMMAND ----------

import matplotlib.pyplot as plt
import seaborn as sns

# Matriz de correlação na amostra
corr = pdf[["temperature_c", "amperage_ka", "bath_ratio", "anode_effect",
            "alumina_feed_rate", "energy_kwh_ton", "vibration_mm_s"]].corr()

fig, ax = plt.subplots(figsize=(9, 7))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax)
ax.set_title("Matriz de correlação — telemetria dos fornos")
plt.tight_layout()
display(fig)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 💬 Genie Code
# MAGIC > *"Faça um gráfico de dispersão (scatter) de `temperature_c` no eixo x e `energy_kwh_ton`
# MAGIC > no eixo y usando o DataFrame pandas `pdf`, com uma linha de tendência."*
# MAGIC
# MAGIC Espere ver uma **relação positiva**: quanto mais quente o banho, mais energia por tonelada.

# COMMAND ----------

# Dispersão energia × temperatura (a relação que vamos modelar na regressão)
fig, ax = plt.subplots(figsize=(8, 6))
sample_plot = pdf.sample(n=min(5000, len(pdf)), random_state=42)
sns.regplot(data=sample_plot, x="temperature_c", y="energy_kwh_ton",
            scatter_kws={"alpha": 0.15, "s": 10}, line_kws={"color": "red"}, ax=ax)
ax.set_title("Energia por tonelada × Temperatura do banho")
ax.set_xlabel("Temperatura (°C)")
ax.set_ylabel("Energia (kWh/ton)")
plt.tight_layout()
display(fig)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Distribuição dos rótulos (labels)
# MAGIC Em problemas de **classificação**, precisamos saber se as classes são **desbalanceadas** —
# MAGIC isso muda a escolha de métricas (acurácia engana quando 98,5% é "sem falha").
# MAGIC
# MAGIC - `is_failure` (telemetria) ≈ 1,5% → manutenção preditiva (variação).
# MAGIC - `is_defect` (inspeções) ≈ 10% → **alvo principal da classificação**.

# COMMAND ----------

# Distribuição de is_failure na telemetria
display(
    df_telemetry.groupBy("is_failure").count()
    .withColumn("percentual", F.round(F.col("count") / df_telemetry.count() * 100, 2))
    .orderBy("is_failure")
)

# COMMAND ----------

# Carrega inspeções de qualidade (alvo principal da classificação) e vê a distribuição
df_inspections = spark.table(f"{GOLD}.furnace_inspections")
print(f"Linhas de inspeções: {df_inspections.count():,}")

display(
    df_inspections.groupBy("is_defect").count()
    .withColumn("percentual", F.round(F.col("count") / df_inspections.count() * 100, 2))
    .orderBy("is_defect")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 💬 Genie Code
# MAGIC > *"Mostre a contagem de cada `defect_type` na tabela
# MAGIC > `cba_trilha_tech.gold.furnace_inspections` em um gráfico de barras."*

# COMMAND ----------

# Relação entre qualidade de superfície e defeito — a feature mais preditiva
pdf_insp = df_inspections.select(
    "surface_quality_score", "is_defect", "defect_type"
).toPandas()

fig, ax = plt.subplots(figsize=(8, 5))
sns.boxplot(data=pdf_insp, x="is_defect", y="surface_quality_score", ax=ax)
ax.set_title("Qualidade de superfície × Defeito")
ax.set_xlabel("is_defect (0 = OK, 1 = defeito)")
ax.set_ylabel("surface_quality_score")
plt.tight_layout()
display(fig)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Checkpoint do Módulo 1
# MAGIC Você deve conseguir responder:
# MAGIC - [ ] Qual variável vamos **prever na regressão**? (`energy_kwh_ton`)
# MAGIC - [ ] Qual variável vamos **prever na classificação**? (`is_defect`)
# MAGIC - [ ] A energia **sobe ou desce** com a temperatura? (sobe — correlação positiva)
# MAGIC - [ ] As classes de `is_defect` estão balanceadas? (não — ~10% de defeitos)
# MAGIC - [ ] Como tratamos os nulos de `vibration_mm_s`? (imputação pela mediana)
# MAGIC
# MAGIC ### 🎯 Exercício
# MAGIC Usando o **Genie Code**, peça um gráfico da distribuição de `energy_kwh_ton`
# MAGIC (histograma) e identifique se ela é aproximadamente normal. Depois, peça a correlação
# MAGIC entre `amperage_ka` e `energy_kwh_ton` e compare com a de temperatura.
# MAGIC
# MAGIC **Próximo módulo:** preparação dos dados e Feature Engineering em Unity Catalog.
