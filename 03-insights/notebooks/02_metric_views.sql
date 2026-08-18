-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 02 · Metric Views (UC) — uma camada semântica única
-- MAGIC ### Trilha Tech 2026 | Workshop Hands-on: Geração de Insights — CBA
-- MAGIC
-- MAGIC **Problema que isto resolve:** no módulo 01 escrevemos a regra de "custo de energia por
-- MAGIC ton", "margem", "receita" dentro de cada query. Se duas pessoas escreverem a margem de
-- MAGIC um jeito diferente, o dashboard e o Genie vão discordar. Isso é o pesadelo do
-- MAGIC "qual número está certo?".
-- MAGIC
-- MAGIC **Solução:** uma **UC Metric View** — uma camada semântica governada no Unity Catalog,
-- MAGIC onde **dimensões** e **medidas** são definidas **uma única vez** e reaproveitadas por
-- MAGIC dashboards AI/BI, Genie e SQL ad-hoc. Todo mundo usa a mesma definição de "margem".
-- MAGIC
-- MAGIC > 💡 **Power BI ↔ Databricks:** uma Metric View é o equivalente governado do seu
-- MAGIC > **modelo semântico / medidas DAX**, só que vive no catálogo (não no arquivo .pbix),
-- MAGIC > é versionada e pode ser consultada por qualquer ferramenta — inclusive o Genie em
-- MAGIC > linguagem natural.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 0 · Como uma Metric View é definida
-- MAGIC
-- MAGIC Uma Metric View é um objeto do Unity Catalog criado com `CREATE VIEW ... WITH METRICS`
-- MAGIC cujo corpo é um **YAML** com três blocos principais:
-- MAGIC
-- MAGIC - `source` — a tabela (ou join) base.
-- MAGIC - `dimensions` — atributos pelos quais você fatia (planta, mês, mercado...).
-- MAGIC - `measures` — agregações reutilizáveis (SUM, AVG...), que sempre são calculadas
-- MAGIC   corretamente, independente de como o usuário filtrar.
-- MAGIC
-- MAGIC Você consulta uma Metric View com a sintaxe `MEASURE(...)`:
-- MAGIC ```sql
-- MAGIC SELECT plant_name, MEASURE(total_tons) FROM cba_workshop_trilha_tech.gold.mv_producao GROUP BY plant_name;
-- MAGIC ```

-- COMMAND ----------

USE CATALOG cba_workshop_trilha_tech;
USE SCHEMA gold;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 1 · Metric View de Produção (custo por ton + OEE simplificado)

-- COMMAND ----------

CREATE OR REPLACE VIEW cba_workshop_trilha_tech.gold.mv_producao
(
  -- comentários de coluna ajudam o Genie a entender o negócio
  plant_name           COMMENT 'Nome da planta produtora',
  state                COMMENT 'UF da planta',
  alloy_name           COMMENT 'Nome da liga de alumínio',
  mes                  COMMENT 'Mês de referência (primeiro dia do mês)',
  total_tons           COMMENT 'Total de toneladas produzidas',
  total_energy_kwh     COMMENT 'Energia consumida em kWh',
  custo_energia_brl    COMMENT 'Custo de energia em R$ (kWh/1000 * 320 R$/MWh)',
  custo_energia_por_ton COMMENT 'Custo de energia por tonelada produzida (R$/ton)',
  total_defects        COMMENT 'Total de peças com defeito',
  oee_qualidade_pct    COMMENT 'OEE simplificado: % de produção sem defeito'
)
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: cba_workshop_trilha_tech.gold.fact_production
joins:
  - name: plantas
    source: cba_workshop_trilha_tech.gold.dim_plantas
    on: source.plant_id = plantas.plant_id
  - name: ligas
    source: cba_workshop_trilha_tech.gold.dim_ligas
    on: source.alloy_id = ligas.alloy_id
dimensions:
  - name: plant_name
    expr: plantas.plant_name
  - name: state
    expr: plantas.state
  - name: alloy_name
    expr: ligas.alloy_name
  - name: mes
    expr: DATE_TRUNC('MONTH', source.date)
measures:
  - name: total_tons
    expr: SUM(tons_produced)
  - name: total_energy_kwh
    expr: SUM(energy_kwh)
  - name: custo_energia_brl
    expr: SUM(energy_kwh) / 1000 * 320
  - name: custo_energia_por_ton
    expr: (SUM(energy_kwh) / 1000 * 320) / NULLIF(SUM(tons_produced), 0)
  - name: total_defects
    expr: SUM(defects)
  # OEE simplificado para o workshop: fração da produção que saiu sem defeito.
  # (OEE completo = Disponibilidade x Performance x Qualidade; aqui isolamos Qualidade.)
  - name: oee_qualidade_pct
    expr: (1 - SUM(defects) / NULLIF(SUM(tons_produced), 0)) * 100
$$;

-- COMMAND ----------

-- Testando a Metric View de produção
SELECT
  plant_name,
  MEASURE(total_tons)            AS total_tons,
  MEASURE(custo_energia_por_ton) AS custo_por_ton,
  MEASURE(oee_qualidade_pct)     AS oee_qualidade_pct
FROM cba_workshop_trilha_tech.gold.mv_producao
GROUP BY plant_name
ORDER BY total_tons DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > ✅ **Checkpoint:** repare que **não escrevemos a fórmula de custo de novo** — só
-- MAGIC > chamamos `MEASURE(custo_energia_por_ton)`. A regra de negócio mora num lugar só.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 2 · Metric View de Vendas (receita, preço, mercado)

-- COMMAND ----------

CREATE OR REPLACE VIEW cba_workshop_trilha_tech.gold.mv_vendas
(
  mes                COMMENT 'Mês de referência',
  market             COMMENT 'Mercado: Interno ou Externo',
  region             COMMENT 'Região de venda',
  customer_segment   COMMENT 'Segmento do cliente',
  alloy_name         COMMENT 'Nome da liga vendida',
  total_tons_vendidas COMMENT 'Toneladas vendidas',
  receita_brl        COMMENT 'Receita total em R$',
  preco_medio_brl_ton COMMENT 'Preço médio de venda (R$/ton)',
  lme_medio_usd_ton  COMMENT 'Preço LME médio (USD/ton)',
  usd_brl_medio      COMMENT 'Câmbio USD/BRL médio'
)
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: cba_workshop_trilha_tech.gold.fact_sales
joins:
  - name: ligas
    source: cba_workshop_trilha_tech.gold.dim_ligas
    on: source.alloy_id = ligas.alloy_id
dimensions:
  - name: mes
    expr: DATE_TRUNC('MONTH', source.date)
  - name: market
    expr: source.market
  - name: region
    expr: source.region
  - name: customer_segment
    expr: source.customer_segment
  - name: alloy_name
    expr: ligas.alloy_name
measures:
  - name: total_tons_vendidas
    expr: SUM(tons_sold)
  - name: receita_brl
    expr: SUM(revenue_brl)
  - name: preco_medio_brl_ton
    expr: SUM(revenue_brl) / NULLIF(SUM(tons_sold), 0)
  - name: lme_medio_usd_ton
    expr: AVG(lme_price_usd_ton)
  - name: usd_brl_medio
    expr: AVG(usd_brl)
$$;

-- COMMAND ----------

-- Testando a Metric View de vendas
SELECT
  market,
  MEASURE(total_tons_vendidas) AS tons,
  MEASURE(receita_brl)         AS receita,
  MEASURE(preco_medio_brl_ton) AS preco_medio
FROM cba_workshop_trilha_tech.gold.mv_vendas
GROUP BY market
ORDER BY receita DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3 · Metric View de Margem (o coração da narrativa)
-- MAGIC
-- MAGIC Margem é a ponte entre as duas pontas: o que custou produzir (forno) × o que o mercado
-- MAGIC pagou (LME × câmbio). Como custo e venda vivem em tabelas diferentes, montamos uma
-- MAGIC **fonte agregada por mês × liga** e definimos a margem em cima dela.

-- COMMAND ----------

CREATE OR REPLACE VIEW cba_workshop_trilha_tech.gold.mv_margem
(
  mes                  COMMENT 'Mês de referência',
  alloy_name           COMMENT 'Nome da liga',
  preco_medio_brl_ton  COMMENT 'Preço médio de venda (R$/ton)',
  custo_energia_por_ton COMMENT 'Custo de energia por ton (R$/ton)',
  margem_brl_ton       COMMENT 'Margem por tonelada = preço - custo de energia (R$/ton)',
  margem_pct           COMMENT 'Margem percentual sobre o preço de venda'
)
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: |
  SELECT
    DATE_TRUNC('MONTH', s.date)                                   AS mes,
    li.alloy_name                                                  AS alloy_name,
    SUM(s.revenue_brl)                                             AS revenue_brl,
    SUM(s.tons_sold)                                               AS tons_sold,
    SUM(p.energy_kwh) / 1000 * 320                                 AS custo_energia_brl,
    SUM(p.tons_produced)                                           AS tons_produced
  FROM cba_workshop_trilha_tech.gold.fact_sales s
  JOIN cba_workshop_trilha_tech.gold.dim_ligas li ON s.alloy_id = li.alloy_id
  LEFT JOIN cba_workshop_trilha_tech.gold.fact_production p
    ON p.alloy_id = s.alloy_id
   AND DATE_TRUNC('MONTH', p.date) = DATE_TRUNC('MONTH', s.date)
  GROUP BY DATE_TRUNC('MONTH', s.date), li.alloy_name
dimensions:
  - name: mes
    expr: mes
  - name: alloy_name
    expr: alloy_name
measures:
  - name: preco_medio_brl_ton
    expr: SUM(revenue_brl) / NULLIF(SUM(tons_sold), 0)
  - name: custo_energia_por_ton
    expr: SUM(custo_energia_brl) / NULLIF(SUM(tons_produced), 0)
  - name: margem_brl_ton
    expr: (SUM(revenue_brl) / NULLIF(SUM(tons_sold), 0))
        - (SUM(custo_energia_brl) / NULLIF(SUM(tons_produced), 0))
  - name: margem_pct
    expr: ( (SUM(revenue_brl) / NULLIF(SUM(tons_sold), 0))
          - (SUM(custo_energia_brl) / NULLIF(SUM(tons_produced), 0)) )
        / NULLIF(SUM(revenue_brl) / NULLIF(SUM(tons_sold), 0), 0) * 100
$$;

-- COMMAND ----------

-- Margem mensal: o gráfico-farol do dashboard executivo
SELECT
  mes,
  MEASURE(preco_medio_brl_ton)   AS preco,
  MEASURE(custo_energia_por_ton) AS custo,
  MEASURE(margem_brl_ton)        AS margem,
  MEASURE(margem_pct)            AS margem_pct
FROM cba_workshop_trilha_tech.gold.mv_margem
GROUP BY mes
ORDER BY mes;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 4 · Certifique as Metric Views (governança + descoberta)
-- MAGIC
-- MAGIC Para o Genie e os colegas confiarem nesses objetos, adicione descrições e marque como
-- MAGIC **Certified** no Catalog Explorer (Data → cba_workshop_trilha_tech → gold → mv_*). Via SQL:

-- COMMAND ----------

COMMENT ON VIEW cba_workshop_trilha_tech.gold.mv_margem IS
  'Camada semântica de MARGEM (Do Forno ao Mercado). Margem/ton = preço de venda - custo de energia. Fonte oficial para dashboards e Genie. CERTIFICADA.';

COMMENT ON VIEW cba_workshop_trilha_tech.gold.mv_producao IS
  'Camada semântica de PRODUÇÃO: toneladas, custo de energia/ton e OEE de qualidade. CERTIFICADA.';

COMMENT ON VIEW cba_workshop_trilha_tech.gold.mv_vendas IS
  'Camada semântica de VENDAS: receita, preço médio, mercado Interno/Externo, LME e câmbio. CERTIFICADA.';

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > 💬 **Databricks Assistant — sua vez**
-- MAGIC > Peça ao Assistant para criar uma 4ª Metric View de **qualidade** sobre
-- MAGIC > `furnace_inspections` com a medida `taxa_defeito_pct = AVG(is_defect)*100` e a
-- MAGIC > dimensão `defect_type`. Prompt:
-- MAGIC >
-- MAGIC > ```
-- MAGIC > Crie uma UC Metric View chamada mv_qualidade sobre cba_workshop_trilha_tech.gold.furnace_inspections,
-- MAGIC > com dimensões defect_type e mês (a partir da coluna de data), e medidas:
-- MAGIC > taxa_defeito_pct = AVG(is_defect)*100 e surface_quality_medio = AVG(surface_quality_score).
-- MAGIC > Use a sintaxe WITH METRICS LANGUAGE YAML.
-- MAGIC > ```
-- MAGIC
-- MAGIC > ✅ **Checkpoint final:** você tem 3 (ou 4) Metric Views certificadas. No módulo 03 o
-- MAGIC > dashboard vai consumir `mv_margem` e `mv_producao`; no módulo 04 o Genie vai usar as
-- MAGIC > mesmas views — garantindo que o número da margem seja **idêntico** nos dois lugares.
-- MAGIC >
-- MAGIC > ➡️ **Próximo:** `03_aibi_dashboard.md`
