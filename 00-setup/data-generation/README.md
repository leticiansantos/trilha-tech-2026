# Dados sintéticos — Trilha Tech 2026 CBA

Gera o conjunto de dados coeso da narrativa **"Do Forno ao Mercado"** (custo de produção via
telemetria de fornos × preço de mercado do alumínio → margem). Contexto CBA (alumínio), labels
prontos para ML, identificadores em inglês e rótulos de negócio em PT-BR.

## Como rodar

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# volume padrão (~864 mil linhas de telemetria, ~70 MB CSV)
python generate_synthetic_data.py

# versão rápida para teste (~86 mil linhas)
python generate_synthetic_data.py --scale 0.1 --out output_test
```

Os arquivos saem em `output/` (CSV para todas as tabelas; `furnace_telemetry` também em Parquet;
amostra de 10 mil linhas em `output/sample/` para o módulo "subir CSV").

## API mock de mercado (trilha de Engenharia)

Simula a B3/LME (preço do alumínio) e o Banco Central (câmbio USD/BRL), citados na reunião.

```bash
python generate_synthetic_data.py            # gera os CSVs que a API serve
uvicorn mock_market_api:app --port 8000
# GET http://localhost:8000/aluminum/lme?start=2026-01-01&end=2026-03-31
# GET http://localhost:8000/fx/usdbrl?start=2026-01-01&end=2026-03-31
```

## Dicionário de dados

### Dimensões
| Tabela | Colunas | Descrição |
|---|---|---|
| `dim_plantas` | `plant_id, plant_name, state, city, num_potlines` | 4 plantas CBA (Alumínio-SP, Miraí-MG, Poços de Caldas-MG, Zona da Mata-MG) |
| `dim_ligas` | `alloy_id, alloy_code, alloy_name, primary_use` | 6 ligas (1050, 3003, 5052, 6061, 6063, 8011) |
| `dim_produtos` | `product_id, product_name, alloy_id, unit` | 7 produtos (lingote, tarugo, placa, bobina, vergalhão, folha, perfil) |
| `dim_fornos` | `furnace_id, plant_id, potline, model, commission_date, capacity_ton_day` | 50 cubas eletrolíticas |

### Telemetria de fornos (Gorila) — volume alto
`furnace_telemetry` (~864 mil linhas): `furnace_id, ts, temperature_c, amperage_ka, bath_ratio,
anode_effect, alumina_feed_rate, energy_kwh_ton, pressure_pa, vibration_mm_s, is_failure`
- `ts`: leitura a cada 5 min, 50 fornos × 60 dias.
- **Correlações** (para EDA): `energy_kwh_ton` ↑ com `temperature_c` (~0,84) e `amperage_ka`.
- **`vibration_mm_s`**: ~1% de valores **nulos** (módulo de qualidade de dados / EDA).
- **`is_failure`** (label binário, ~1,5%): falha correlacionada com `anode_effect`, `vibration_mm_s` e desvio de temperatura → modelo de **manutenção preditiva**.

### Qualidade
`furnace_inspections` (20 mil linhas): `inspection_id, furnace_id, ts, alloy_id, product_id,
defect_type, surface_quality_score, is_defect`
- **`is_defect`** (label binário, ~10%): alvo principal de **classificação binária** (trilha MLOps). Correlaciona com `surface_quality_score`.

### Mercado
| Arquivo | Colunas | Origem simulada |
|---|---|---|
| `aluminum_lme_price.csv` | `date, lme_price_usd_ton` | "CSV de consultoria" / API B3-LME |
| `fx_usdbrl.csv` | `date, usd_brl` | API Banco Central |

### Fatos (Insights)
| Tabela | Colunas-chave |
|---|---|
| `fact_production` | `date, plant_id, furnace_id, alloy_id, product_id, tons_produced, energy_kwh, defects, energy_cost_brl` |
| `fact_sales` | `date, product_id, alloy_id, region, market (Interno/Externo), customer_segment, tons_sold, lme_price_usd_ton, usd_brl, price_usd_ton, price_brl_ton, revenue_brl` |

### Métricas didáticas derivadas
- **Custo de energia/ton** = `energy_kwh / 1000 * 320 R$/MWh` (em `fact_production.energy_cost_brl`).
- **Margem** = `price_brl_ton` (vendas) − custo de produção/ton (energia + overhead).
- **Preço BRL** = `price_usd_ton * usd_brl` (mostra a sensibilidade ao câmbio citada na reunião).

> Determinístico (seed 42): mesma entrada → mesma saída, para reprodutibilidade entre turmas.
