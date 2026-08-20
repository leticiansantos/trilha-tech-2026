# Databricks notebook source
# MAGIC %md
# MAGIC # 🏭 Módulo 0 — Setup dos dados (autocontido)
# MAGIC
# MAGIC **Trilha Tech 2026 | Workshop Hands-on: MLOps na prática — CBA (Companhia Brasileira de Alumínio)**
# MAGIC
# MAGIC Este notebook prepara **todo** o dado necessário para a trilha de MLOps **sem depender da trilha
# MAGIC de Engenharia**. Ele:
# MAGIC
# MAGIC 1. Cria o **seu schema pessoal** (`mlops_<seu_usuario>`) no catálogo compartilhado.
# MAGIC 2. Gera os **dados sintéticos** da narrativa "Do Forno ao Mercado" (mesma lógica do gerador
# MAGIC    oficial da trilha) e grava como **tabelas Delta dentro do seu schema**.
# MAGIC
# MAGIC > ⚠️ **Rode este notebook UMA vez, antes dos demais módulos.** Os módulos 1 a 7 leem os dados
# MAGIC > direto do seu schema (variável `GOLD` = seu schema).
# MAGIC
# MAGIC **Pré-requisito de ambiente:** o catálogo `cba_workshop_trilha_tech` já deve existir (um admin
# MAGIC cria uma vez) e você precisa ter `CREATE SCHEMA` nele. Se não existir, peça ao instrutor.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuração do ambiente
# MAGIC Catálogo compartilhado + **um schema por usuário** (para cada aluno trabalhar isolado).

# COMMAND ----------

# Catálogo compartilhado da trilha (um admin cria uma vez; você só precisa de CREATE SCHEMA nele)
CATALOG = "cba_workshop_trilha_tech"

# Schema por usuário: deriva do e-mail logado -> evita conflito entre alunos
current_user = spark.sql("SELECT current_user()").collect()[0][0]
user_prefix = current_user.split("@")[0].replace(".", "_").replace("-", "_")
SCHEMA = f"mlops_{user_prefix}"

print(f"Usuário ........: {current_user}")
print(f"Catálogo .......: {CATALOG}")
print(f"Seu schema .....: {SCHEMA}")

# Garante o catálogo (se você tiver permissão) e cria o SEU schema.
existing_catalogs = [r.catalog for r in spark.sql("SHOW CATALOGS").collect()]
if CATALOG not in existing_catalogs:
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
        print(f"Catálogo {CATALOG} criado.")
    except Exception as e:
        raise RuntimeError(
            f"O catálogo '{CATALOG}' não existe e você não tem permissão para criá-lo. "
            f"Peça a um admin para criar o catálogo uma vez antes do workshop. Detalhe: {e}"
        )

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# A partir de agora, as tabelas-fonte ficam no SEU schema (é o que os módulos 1-7 usam como GOLD)
GOLD = f"{CATALOG}.{SCHEMA}"
print(f"Schema de dados (GOLD): {GOLD}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Gerador de dados sintéticos
# MAGIC Mesma lógica (e `seed=42`) do gerador oficial da trilha, portada para numpy + pandas — assim o
# MAGIC setup é **determinístico** (todos os alunos obtêm os mesmos dados) e **autocontido** (não precisa
# MAGIC de Volume, CSV nem `polars`). Escala **reduzida** (~100 mil linhas de telemetria), suficiente para
# MAGIC EDA, regressão, classificação e AutoML, e rápida de gerar por aluno.

# COMMAND ----------

import numpy as np
import pandas as pd
from pyspark.sql import functions as F

SEED = 42

# --- Escala reduzida para workshop (~100k linhas de telemetria) ---
N_FURNACES = 10
N_DAYS_TELEMETRY = 35
FREQ_MIN = 5           # leitura a cada 5 min -> 288 leituras/dia
N_INSPECTIONS = 10_000
N_DAYS_MARKET = 365

# --- Catálogo de negócio CBA (sintético, porém plausível para alumínio) ---
# (plant_id, plant_name, state, city, num_potlines)
PLANTS = [
    (1, "Aluminio - SP", "SP", "Aluminio", 4),
    (2, "Miraí - MG", "MG", "Miraí", 2),
    (3, "Poços de Caldas - MG", "MG", "Poços de Caldas", 3),
    (4, "Zona da Mata - MG", "MG", "Juiz de Fora", 1),
]
# (alloy_id, alloy_code, alloy_name, primary_use)
ALLOYS = [
    (1, "1050", "Aluminio puro 99,5%", "Eletrico / quimico"),
    (2, "3003", "Al-Mn", "Telhas / utensilios"),
    (3, "5052", "Al-Mg", "Naval / tanques"),
    (4, "6061", "Al-Mg-Si", "Estrutural / extrusao"),
    (5, "6063", "Al-Mg-Si", "Esquadrias / perfis"),
    (6, "8011", "Al-Fe-Si", "Embalagem / foil"),
]
# (product_id, product_name, alloy_id, unit)
PRODUCTS = [
    (1, "Lingote", 1, "ton"),
    (2, "Tarugo (billet)", 4, "ton"),
    (3, "Placa (slab)", 3, "ton"),
    (4, "Bobina (coil)", 2, "ton"),
    (5, "Vergalhão (wire rod)", 1, "ton"),
    (6, "Folha (foil)", 6, "ton"),
    (7, "Perfil extrudado", 5, "ton"),
]
FURNACE_MODELS = ["Pot-180kA", "Pot-240kA", "Pot-320kA", "Pot-400kA"]


def _rng():
    """RNG determinístico (seed fixa) — mesmo padrão do gerador oficial."""
    return np.random.default_rng(SEED)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 Dimensões

# COMMAND ----------

def build_dim_plantas():
    return pd.DataFrame(PLANTS, columns=["plant_id", "plant_name", "state", "city", "num_potlines"])


def build_dim_ligas():
    return pd.DataFrame(ALLOYS, columns=["alloy_id", "alloy_code", "alloy_name", "primary_use"])


def build_dim_produtos():
    return pd.DataFrame(PRODUCTS, columns=["product_id", "product_name", "alloy_id", "unit"])


def build_dim_fornos(n_furnaces):
    """Cubas eletrolíticas (fornos) distribuídas entre plantas/potlines."""
    rng = _rng()
    plant_ids = [p[0] for p in PLANTS]
    potlines_by_plant = {p[0]: p[4] for p in PLANTS}
    rows = []
    for fid in range(1, n_furnaces + 1):
        plant_id = plant_ids[(fid - 1) % len(plant_ids)]
        potline = int(rng.integers(1, potlines_by_plant[plant_id] + 1))
        model = FURNACE_MODELS[int(rng.integers(0, len(FURNACE_MODELS)))]
        commission_year = int(rng.integers(2005, 2023))
        capacity = float(np.round(rng.uniform(1.8, 3.2), 2))  # ton/dia por cuba
        rows.append((fid, plant_id, potline, model, f"{commission_year}-01-01", capacity))
    return pd.DataFrame(
        rows,
        columns=["furnace_id", "plant_id", "potline", "model", "commission_date", "capacity_ton_day"],
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 Telemetria dos fornos (Gorila) — com label de falha e nulos em `vibration_mm_s`
# MAGIC Variáveis correlacionadas de propósito (boas para o EDA):
# MAGIC - `energy_kwh_ton` **cresce** com `temperature_c` e `amperage_ka` (base da regressão).
# MAGIC - `is_failure` correlaciona com `anode_effect`, vibração e desvio de temperatura (~1,5% positivos).

# COMMAND ----------

def build_furnace_telemetry(n_furnaces, n_days, freq_min):
    rng = _rng()
    readings_per_day = (24 * 60) // freq_min
    n_steps = n_days * readings_per_day
    start = np.datetime64("2026-01-01T00:00:00")
    ts = start + np.arange(n_steps) * np.timedelta64(freq_min, "m")

    # base por forno (heterogeneidade entre cubas)
    base_temp = rng.normal(960.0, 4.0, n_furnaces)        # banho ~960 C
    base_amp = rng.normal(320.0, 30.0, n_furnaces)        # kA por modelo
    base_energy = rng.normal(13500.0, 250.0, n_furnaces)  # kWh/ton (smelting)

    frames = []
    for f_idx in range(n_furnaces):
        fid = f_idx + 1
        drift = np.sin(np.linspace(0, 6 * np.pi, n_steps)) * 1.5
        temperature = base_temp[f_idx] + drift + rng.normal(0, 1.2, n_steps)
        amperage = base_amp[f_idx] + rng.normal(0, 4.0, n_steps)
        bath_ratio = rng.normal(1.15, 0.03, n_steps)
        alumina_feed = rng.normal(2.0, 0.15, n_steps)          # ton/h
        pressure = rng.normal(101325, 250, n_steps)            # Pa
        vibration = np.abs(rng.normal(2.0, 0.6, n_steps))      # mm/s
        anode_effect = rng.poisson(0.04, n_steps).astype(np.int64)  # eventos raros

        # energia correlacionada (temperatura + amperagem + efeito anódico)
        energy = (
            base_energy[f_idx]
            + (temperature - 960.0) * 35.0
            + (amperage - 320.0) * 2.0
            + anode_effect * 120.0
            + rng.normal(0, 60.0, n_steps)
        )

        # label de falha (logit): sobe com efeito anódico, vibração e desvio de temperatura
        temp_dev = np.abs(temperature - 960.0)
        logit = -5.2 + 1.3 * anode_effect + 0.55 * (vibration - 2.0) + 0.18 * temp_dev
        prob = 1.0 / (1.0 + np.exp(-logit))
        is_failure = (rng.uniform(0, 1, n_steps) < prob).astype(np.int64)

        # ~1% de nulos em vibração (sensor offline) para o módulo de qualidade de dados
        null_mask = rng.uniform(0, 1, n_steps) < 0.01
        vibration_with_nulls = np.where(null_mask, np.nan, vibration)

        frames.append(pd.DataFrame({
            "furnace_id": np.full(n_steps, fid, dtype=np.int64),
            "ts": ts,
            "temperature_c": np.round(temperature, 2),
            "amperage_ka": np.round(amperage, 2),
            "bath_ratio": np.round(bath_ratio, 4),
            "anode_effect": anode_effect,
            "alumina_feed_rate": np.round(alumina_feed, 3),
            "energy_kwh_ton": np.round(energy, 1),
            "pressure_pa": np.round(pressure, 1),
            "vibration_mm_s": np.round(vibration_with_nulls, 3),
            "is_failure": is_failure,
        }))
    return pd.concat(frames, ignore_index=True)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 Inspeções de qualidade (alvo da classificação binária `is_defect`)

# COMMAND ----------

def build_furnace_inspections(n_furnaces, n_inspections):
    rng = _rng()
    fids = rng.integers(1, n_furnaces + 1, n_inspections)
    alloy_ids = rng.integers(1, len(ALLOYS) + 1, n_inspections)
    product_ids = rng.integers(1, len(PRODUCTS) + 1, n_inspections)
    start = np.datetime64("2026-01-01T00:00:00")
    hours = rng.integers(0, 24 * 90, n_inspections)
    ts = start + hours.astype("timedelta64[h]")
    surface = np.clip(rng.normal(0.82, 0.12, n_inspections), 0, 1)
    defect_types = np.array(["porosidade", "trinca", "inclusao", "rebarba", "ok"])
    # defeito correlaciona com baixa qualidade de superfície
    prob_defect = np.clip(0.9 - surface, 0.02, 0.95)
    is_defect = (rng.uniform(0, 1, n_inspections) < prob_defect).astype(np.int64)
    dtype_idx = np.where(is_defect == 1, rng.integers(0, 4, n_inspections), 4)  # 4 = "ok"
    return pd.DataFrame({
        "inspection_id": np.arange(1, n_inspections + 1, dtype=np.int64),
        "furnace_id": fids.astype(np.int64),
        "ts": ts,
        "alloy_id": alloy_ids.astype(np.int64),
        "product_id": product_ids.astype(np.int64),
        "defect_type": defect_types[dtype_idx],
        "surface_quality_score": np.round(surface, 3),
        "is_defect": is_defect,
    })

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 Mercado — preço do alumínio (LME) + câmbio USD/BRL (contexto de margem)

# COMMAND ----------

def build_market(n_days):
    rng = _rng()
    start = np.datetime64("2026-01-01")
    dates = start + np.arange(n_days).astype("timedelta64[D]")
    # preço LME (USD/ton) — random walk em torno de ~2400
    lme = np.clip(2400 + np.cumsum(rng.normal(0, 18, n_days)), 1900, 3200)
    # câmbio USD/BRL — random walk em torno de ~5.10
    fx = np.clip(5.10 + np.cumsum(rng.normal(0, 0.012, n_days)), 4.6, 6.2)
    lme_df = pd.DataFrame({"date": dates, "lme_price_usd_ton": np.round(lme, 2)})
    fx_df = pd.DataFrame({"date": dates, "usd_brl": np.round(fx, 4)})
    return lme_df, fx_df

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Gravação das tabelas Delta no seu schema

# COMMAND ----------

def save_delta(pdf, table, fix_nan_col=None):
    """Grava um DataFrame pandas como tabela Delta no schema do aluno.
    fix_nan_col: nome de coluna cujos NaN devem virar NULL real (para o EDA)."""
    sdf = spark.createDataFrame(pdf)
    if fix_nan_col:
        sdf = sdf.withColumn(
            fix_nan_col,
            F.when(F.isnan(F.col(fix_nan_col)), None).otherwise(F.col(fix_nan_col)),
        )
    (sdf.write.format("delta").mode("overwrite").option("overwriteSchema", True)
        .saveAsTable(f"{CATALOG}.{SCHEMA}.{table}"))
    print(f"  ✓ {CATALOG}.{SCHEMA}.{table}  ({sdf.count():,} linhas)")


print("Dimensões:")
save_delta(build_dim_plantas(), "dim_plantas")
save_delta(build_dim_ligas(), "dim_ligas")
save_delta(build_dim_produtos(), "dim_produtos")
save_delta(build_dim_fornos(N_FURNACES), "dim_fornos")

print("\nMercado:")
lme_df, fx_df = build_market(N_DAYS_MARKET)
save_delta(lme_df, "aluminum_lme_price")
save_delta(fx_df, "fx_usdbrl")

print("\nTelemetria (Gorila):")
save_delta(build_furnace_telemetry(N_FURNACES, N_DAYS_TELEMETRY, FREQ_MIN),
           "furnace_telemetry", fix_nan_col="vibration_mm_s")

print("\nQualidade:")
save_delta(build_furnace_inspections(N_FURNACES, N_INSPECTIONS), "furnace_inspections")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Validação

# COMMAND ----------

print("Tabelas no seu schema:")
display(spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}"))

# COMMAND ----------

# Sanidade: contagens e balanceamento dos rótulos (o que veremos no EDA)
tel = spark.table(f"{GOLD}.furnace_telemetry")
insp = spark.table(f"{GOLD}.furnace_inspections")
print(f"furnace_telemetry ..: {tel.count():,} linhas")
print(f"furnace_inspections : {insp.count():,} linhas")

display(
    tel.groupBy("is_failure").count()
    .withColumn("percentual", F.round(F.col("count") / tel.count() * 100, 2))
    .orderBy("is_failure")
)
display(
    insp.groupBy("is_defect").count()
    .withColumn("percentual", F.round(F.col("count") / insp.count() * 100, 2))
    .orderBy("is_defect")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Setup concluído
# MAGIC Seu schema `mlops_<usuario>` agora contém: `furnace_telemetry`, `furnace_inspections`,
# MAGIC `dim_plantas`, `dim_ligas`, `dim_produtos`, `dim_fornos`, `aluminum_lme_price`, `fx_usdbrl`.
# MAGIC
# MAGIC Os próximos módulos leem esses dados via a variável **`GOLD` = seu schema**. Siga para o
# MAGIC **Módulo 1 — EDA** (`01_eda.py`).
