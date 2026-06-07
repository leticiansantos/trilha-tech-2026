"""
Trilha Tech 2026 | CBA - Gerador de dados sintéticos
=====================================================
Narrativa "Do Forno ao Mercado": custo de producao (telemetria de fornos / Gorila)
x preco de mercado (aluminio LME + dolar) -> margem.

Gera um conjunto de dados coeso, com labels e contexto CBA (aluminio), para as 3 trilhas:
  - Engenharia: telemetria de fornos (volume alto), mercado (CSV + API), dimensoes.
  - MLOps:      labels de falha (classificacao binaria) e energia/temperatura (regressao).
  - Insights:   producao, vendas, preco e margem (fatos para dashboards).

Determinístico (seed fixa). Workspace-agnostico: grava arquivos locais em ./output.
Identificadores em ingles; rotulos de negocio em PT-BR.

Uso:
    python generate_synthetic_data.py                # volume padrao (~1M linhas de telemetria)
    python generate_synthetic_data.py --scale 0.1    # versao rapida p/ testar (~100k)
    python generate_synthetic_data.py --out ./output # diretorio de saida
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import numpy as np
import polars as pl

SEED = 42

# ----------------------------------------------------------------------------
# Catalogo de negocio CBA (sintetico, porem plausivel para aluminio)
# ----------------------------------------------------------------------------
PLANTS = [
    # (plant_id, plant_name, state, city, num_potlines)
    (1, "Aluminio - SP", "SP", "Aluminio", 4),
    (2, "Miraí - MG", "MG", "Miraí", 2),
    (3, "Poços de Caldas - MG", "MG", "Poços de Caldas", 3),
    (4, "Zona da Mata - MG", "MG", "Juiz de Fora", 1),
]

# Ligas de aluminio (series reais da norma; uso tipico)
ALLOYS = [
    # (alloy_id, alloy_code, alloy_name, primary_use)
    (1, "1050", "Aluminio puro 99,5%", "Eletrico / quimico"),
    (2, "3003", "Al-Mn", "Telhas / utensilios"),
    (3, "5052", "Al-Mg", "Naval / tanques"),
    (4, "6061", "Al-Mg-Si", "Estrutural / extrusao"),
    (5, "6063", "Al-Mg-Si", "Esquadrias / perfis"),
    (6, "8011", "Al-Fe-Si", "Embalagem / foil"),
]

# Produtos de aluminio
PRODUCTS = [
    # (product_id, product_name, alloy_id, unit)
    (1, "Lingote", 1, "ton"),
    (2, "Tarugo (billet)", 4, "ton"),
    (3, "Placa (slab)", 3, "ton"),
    (4, "Bobina (coil)", 2, "ton"),
    (5, "Vergalhão (wire rod)", 1, "ton"),
    (6, "Folha (foil)", 6, "ton"),
    (7, "Perfil extrudado", 5, "ton"),
]

REGIONS = ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte", "Exterior"]
CUSTOMER_SEGMENTS = ["Automotivo", "Construcao", "Embalagem", "Eletrico", "Bens de consumo"]
FURNACE_MODELS = ["Pot-180kA", "Pot-240kA", "Pot-320kA", "Pot-400kA"]


def _rng() -> np.random.Generator:
    return np.random.default_rng(SEED)


# ----------------------------------------------------------------------------
# Dimensoes
# ----------------------------------------------------------------------------
def build_dim_plantas() -> pl.DataFrame:
    return pl.DataFrame(
        PLANTS,
        schema=["plant_id", "plant_name", "state", "city", "num_potlines"],
        orient="row",
    )


def build_dim_ligas() -> pl.DataFrame:
    return pl.DataFrame(
        ALLOYS,
        schema=["alloy_id", "alloy_code", "alloy_name", "primary_use"],
        orient="row",
    )


def build_dim_produtos() -> pl.DataFrame:
    return pl.DataFrame(
        PRODUCTS,
        schema=["product_id", "product_name", "alloy_id", "unit"],
        orient="row",
    )


def build_dim_fornos(n_furnaces: int) -> pl.DataFrame:
    """Cubas eletroliticas (fornos) distribuidas entre plantas/potlines."""
    rng = _rng()
    rows = []
    plant_ids = [p[0] for p in PLANTS]
    potlines_by_plant = {p[0]: p[4] for p in PLANTS}
    for fid in range(1, n_furnaces + 1):
        plant_id = plant_ids[(fid - 1) % len(plant_ids)]
        potline = int(rng.integers(1, potlines_by_plant[plant_id] + 1))
        model = FURNACE_MODELS[int(rng.integers(0, len(FURNACE_MODELS)))]
        commission_year = int(rng.integers(2005, 2023))
        capacity = float(np.round(rng.uniform(1.8, 3.2), 2))  # ton/dia por cuba
        rows.append(
            (fid, plant_id, potline, model,
             f"{commission_year}-01-01", capacity)
        )
    return pl.DataFrame(
        rows,
        schema=["furnace_id", "plant_id", "potline", "model",
                "commission_date", "capacity_ton_day"],
        orient="row",
    )


# ----------------------------------------------------------------------------
# Telemetria de fornos (Gorila) - VOLUME ALTO, com label de falha
# ----------------------------------------------------------------------------
def build_furnace_telemetry(n_furnaces: int, n_days: int, freq_min: int) -> pl.DataFrame:
    """
    Leituras de sensores por cuba eletrolitica.
    Variaveis correlacionadas (boas para EDA):
      - energy_kwh_ton cresce com temperature_c e amperage_ka
      - is_failure correlaciona com anode_effect, vibration e desvio de temperatura
    """
    rng = _rng()
    readings_per_day = (24 * 60) // freq_min
    n_steps = n_days * readings_per_day
    start = dt.datetime(2026, 1, 1, 0, 0, 0)

    # base por forno (heterogeneidade entre cubas)
    base_temp = rng.normal(960.0, 4.0, n_furnaces)        # banho ~960 C
    base_amp = rng.normal(320.0, 30.0, n_furnaces)        # kA por modelo
    base_energy = rng.normal(13500.0, 250.0, n_furnaces)  # kWh/ton (smelting)

    frames = []
    ts = np.datetime64(start) + np.arange(n_steps) * np.timedelta64(freq_min, "m")
    for f_idx in range(n_furnaces):
        fid = f_idx + 1

        # ruido e tendencias suaves
        drift = np.sin(np.linspace(0, 6 * np.pi, n_steps)) * 1.5
        temperature = base_temp[f_idx] + drift + rng.normal(0, 1.2, n_steps)
        amperage = base_amp[f_idx] + rng.normal(0, 4.0, n_steps)
        bath_ratio = rng.normal(1.15, 0.03, n_steps)
        alumina_feed = rng.normal(2.0, 0.15, n_steps)            # ton/h
        pressure = rng.normal(101325, 250, n_steps)             # Pa
        vibration = np.abs(rng.normal(2.0, 0.6, n_steps))       # mm/s

        # efeito anodico: eventos raros (contagem por leitura)
        anode_effect = rng.poisson(0.04, n_steps).astype(np.int64)

        # energia correlacionada (temperatura alta + amperagem alta + efeito anodico => mais energia)
        energy = (
            base_energy[f_idx]
            + (temperature - 960.0) * 35.0
            + (amperage - 320.0) * 2.0
            + anode_effect * 120.0
            + rng.normal(0, 60.0, n_steps)
        )

        # label de falha: probabilidade sobe com efeito anodico, vibracao e desvio de temperatura
        temp_dev = np.abs(temperature - 960.0)
        logit = (-5.2
                 + 1.3 * anode_effect
                 + 0.55 * (vibration - 2.0)
                 + 0.18 * temp_dev)
        prob = 1.0 / (1.0 + np.exp(-logit))
        is_failure = (rng.uniform(0, 1, n_steps) < prob).astype(np.int64)

        # injeta alguns valores nulos (para o modulo de qualidade de dados / EDA)
        null_mask = rng.uniform(0, 1, n_steps) < 0.01
        vibration_with_nulls = np.where(null_mask, np.nan, vibration)

        frames.append(pl.DataFrame({
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
    return pl.concat(frames).with_columns(
        # NaN -> null real (celula vazia no CSV) para o modulo de EDA / qualidade de dados
        pl.when(pl.col("vibration_mm_s").is_nan())
        .then(None)
        .otherwise(pl.col("vibration_mm_s"))
        .alias("vibration_mm_s")
    )


# ----------------------------------------------------------------------------
# Inspecoes de qualidade (classificacao binaria is_defect)
# ----------------------------------------------------------------------------
def build_furnace_inspections(n_furnaces: int, n_inspections: int) -> pl.DataFrame:
    rng = _rng()
    fids = rng.integers(1, n_furnaces + 1, n_inspections)
    alloy_ids = rng.integers(1, len(ALLOYS) + 1, n_inspections)
    product_ids = rng.integers(1, len(PRODUCTS) + 1, n_inspections)
    start = dt.datetime(2026, 1, 1)
    hours = rng.integers(0, 24 * 90, n_inspections)
    ts = np.datetime64(start) + hours.astype("timedelta64[h]")
    surface = np.clip(rng.normal(0.82, 0.12, n_inspections), 0, 1)
    defect_types = np.array(["porosidade", "trinca", "inclusao", "rebarba", "ok"])
    # defeito correlaciona com baixa qualidade de superficie
    prob_defect = np.clip(0.9 - surface, 0.02, 0.95)
    is_defect = (rng.uniform(0, 1, n_inspections) < prob_defect).astype(np.int64)
    dtype_idx = np.where(
        is_defect == 1,
        rng.integers(0, 4, n_inspections),  # algum defeito
        4,                                  # "ok"
    )
    return pl.DataFrame({
        "inspection_id": np.arange(1, n_inspections + 1, dtype=np.int64),
        "furnace_id": fids.astype(np.int64),
        "ts": ts,
        "alloy_id": alloy_ids.astype(np.int64),
        "product_id": product_ids.astype(np.int64),
        "defect_type": defect_types[dtype_idx],
        "surface_quality_score": np.round(surface, 3),
        "is_defect": is_defect,
    })


# ----------------------------------------------------------------------------
# Mercado: preco do aluminio (LME) + cambio USD/BRL (CSV + base p/ API mock)
# ----------------------------------------------------------------------------
def build_market(n_days: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    rng = _rng()
    start = dt.date(2026, 1, 1)
    dates = [start + dt.timedelta(days=d) for d in range(n_days)]

    # preco LME (USD/ton) - random walk em torno de ~2400
    lme = 2400 + np.cumsum(rng.normal(0, 18, n_days))
    lme = np.clip(lme, 1900, 3200)

    # cambio USD/BRL - random walk em torno de ~5.10
    fx = 5.10 + np.cumsum(rng.normal(0, 0.012, n_days))
    fx = np.clip(fx, 4.6, 6.2)

    lme_df = pl.DataFrame({
        "date": dates,
        "lme_price_usd_ton": np.round(lme, 2),
    })
    fx_df = pl.DataFrame({
        "date": dates,
        "usd_brl": np.round(fx, 4),
    })
    return lme_df, fx_df


# ----------------------------------------------------------------------------
# Fatos de producao e vendas (trilha de Insights)
# ----------------------------------------------------------------------------
def build_fact_production(n_furnaces: int, lme_df: pl.DataFrame,
                          fx_df: pl.DataFrame, n_days: int) -> pl.DataFrame:
    rng = _rng()
    start = dt.date(2026, 1, 1)
    rows = []
    pid = 1
    for d in range(n_days):
        cur_date = start + dt.timedelta(days=d)
        for fid in range(1, n_furnaces + 1):
            tons = float(np.round(rng.uniform(1.8, 3.2), 3))
            energy = float(np.round(tons * rng.normal(13500, 300), 1))
            defects = int(rng.poisson(0.6))
            alloy_id = int(rng.integers(1, len(ALLOYS) + 1))
            product_id = int(rng.integers(1, len(PRODUCTS) + 1))
            plant_id = ((fid - 1) % len(PLANTS)) + 1
            rows.append((pid, cur_date, plant_id, fid, alloy_id, product_id,
                         tons, energy, defects))
            pid += 1
    prod = pl.DataFrame(
        rows,
        schema=["production_id", "date", "plant_id", "furnace_id", "alloy_id",
                "product_id", "tons_produced", "energy_kwh", "defects"],
        orient="row",
    )
    # custo de energia (R$/MWh fixo didatico) -> custo por ton
    energy_cost_brl_mwh = 320.0
    prod = prod.with_columns(
        (pl.col("energy_kwh") / 1000.0 * energy_cost_brl_mwh).round(2).alias("energy_cost_brl")
    )
    return prod


def build_fact_sales(lme_df: pl.DataFrame, fx_df: pl.DataFrame, n_sales: int) -> pl.DataFrame:
    rng = _rng()
    market = lme_df.join(fx_df, on="date")
    n_days = market.height
    idx = rng.integers(0, n_days, n_sales)
    sale_dates = market["date"].to_numpy()[idx]
    lme_prices = market["lme_price_usd_ton"].to_numpy()[idx]
    fx_rates = market["usd_brl"].to_numpy()[idx]

    product_ids = rng.integers(1, len(PRODUCTS) + 1, n_sales)
    alloy_ids = rng.integers(1, len(ALLOYS) + 1, n_sales)
    region_idx = rng.integers(0, len(REGIONS), n_sales)
    seg_idx = rng.integers(0, len(CUSTOMER_SEGMENTS), n_sales)
    regions = np.array(REGIONS)[region_idx]
    markets = np.where(regions == "Exterior", "Externo", "Interno")
    segments = np.array(CUSTOMER_SEGMENTS)[seg_idx]
    tons = np.round(rng.uniform(5, 120, n_sales), 2)
    # premio sobre o LME por liga/produto (5% a 25%)
    premium = rng.uniform(1.05, 1.25, n_sales)
    price_usd = np.round(lme_prices * premium, 2)
    price_brl = np.round(price_usd * fx_rates, 2)

    return pl.DataFrame({
        "sale_id": np.arange(1, n_sales + 1, dtype=np.int64),
        "date": sale_dates,
        "product_id": product_ids.astype(np.int64),
        "alloy_id": alloy_ids.astype(np.int64),
        "region": regions,
        "market": markets,
        "customer_segment": segments,
        "tons_sold": tons,
        "lme_price_usd_ton": np.round(lme_prices, 2),
        "usd_brl": np.round(fx_rates, 4),
        "price_usd_ton": price_usd,
        "price_brl_ton": price_brl,
        "revenue_brl": np.round(tons * price_brl, 2),
    })


# ----------------------------------------------------------------------------
# Orquestracao
# ----------------------------------------------------------------------------
def write(df: pl.DataFrame, out: Path, name: str, parquet: bool = False) -> None:
    df.write_csv(out / f"{name}.csv")
    if parquet:
        df.write_parquet(out / f"{name}.parquet")
    print(f"  - {name:<22} {df.height:>9,} linhas  ({df.width} colunas)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Gerador de dados sinteticos CBA - Trilha Tech 2026")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="fator de escala do volume de telemetria (1.0 = ~1M linhas)")
    ap.add_argument("--out", type=str, default="output", help="diretorio de saida")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sample").mkdir(exist_ok=True)

    # dimensionamento
    n_furnaces = max(5, int(50 * args.scale))
    n_days_telemetry = max(5, int(60 * args.scale))
    freq_min = 5
    n_days_market = 365
    n_inspections = max(200, int(20_000 * args.scale))
    n_sales = max(500, int(50_000 * args.scale))
    n_days_prod = max(10, int(60 * args.scale))

    print(f"\nGerando dados CBA (scale={args.scale}) em '{out}/' ...\n")

    print("Dimensoes:")
    write(build_dim_plantas(), out, "dim_plantas")
    write(build_dim_ligas(), out, "dim_ligas")
    write(build_dim_produtos(), out, "dim_produtos")
    write(build_dim_fornos(n_furnaces), out, "dim_fornos")

    print("\nMercado (consultoria + API):")
    lme_df, fx_df = build_market(n_days_market)
    write(lme_df, out, "aluminum_lme_price")
    write(fx_df, out, "fx_usdbrl")

    print("\nTelemetria de fornos (Gorila):")
    telemetry = build_furnace_telemetry(n_furnaces, n_days_telemetry, freq_min)
    write(telemetry, out, "furnace_telemetry", parquet=True)
    # amostra pequena para o modulo "subir CSV"
    telemetry.head(10_000).write_csv(out / "sample" / "furnace_telemetry_sample.csv")
    print("  - sample/furnace_telemetry_sample.csv  10,000 linhas (para upload no modulo 2)")

    print("\nQualidade:")
    write(build_furnace_inspections(n_furnaces, n_inspections), out, "furnace_inspections")

    print("\nFatos (Insights):")
    write(build_fact_production(n_furnaces, lme_df, fx_df, n_days_prod), out, "fact_production")
    write(build_fact_sales(lme_df, fx_df, n_sales), out, "fact_sales")

    print(f"\nPronto. Arquivos em: {out.resolve()}\n")


if __name__ == "__main__":
    main()
