-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 01 · Explorando os dados com SQL + Databricks Assistant
-- MAGIC ### Trilha Tech 2026 | Workshop Hands-on: Geração de Insights — CBA
-- MAGIC
-- MAGIC **Narrativa "Do Forno ao Mercado":** custo de produção (telemetria dos fornos "Gorila")
-- MAGIC × preço de mercado do alumínio (LME + USD/BRL) → **margem**.
-- MAGIC Nesta trilha (Insights) consumimos as tabelas GOLD/fato e respondemos perguntas de
-- MAGIC negócio: produção, custo de energia, preço de mercado, margem e qualidade.
-- MAGIC
-- MAGIC **Objetivo deste módulo:** ganhar confiança no SQL Editor do Databricks usando o
-- MAGIC **Databricks Assistant** para *gerar*, *explicar* e *corrigir* SQL. Você não precisa
-- MAGIC saber SQL de cor — precisa saber *perguntar bem*.
-- MAGIC
-- MAGIC > 💡 **Vem do Power BI?** Pense neste notebook como o "Power Query + DAX" do Databricks,
-- MAGIC > só que tudo em SQL e rodando direto sobre a fonte (sem importar/atualizar dataset).
-- MAGIC > O Assistant faz o papel de um copiloto que escreve a query para você.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 0 · Preparação (rode uma vez)
-- MAGIC
-- MAGIC 1. No topo do SQL Editor, selecione um **SQL Warehouse Serverless** (canto superior direito).
-- MAGIC 2. Confirme que você tem acesso ao catálogo `cba_workshop_trilha_tech`.
-- MAGIC 3. Para abrir o Assistant: clique no ícone ✨ (Assistant) na barra lateral da célula,
-- MAGIC    ou pressione **Cmd/Ctrl + I** dentro de uma célula de código.

-- COMMAND ----------

-- Define catálogo e schema padrão para não repetir o prefixo o tempo todo
USE CATALOG cba_workshop_trilha_tech;
USE SCHEMA gold;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 1 · Conhecendo as tabelas
-- MAGIC
-- MAGIC Antes de perguntar qualquer coisa, descubra **o que existe**. No Databricks isso é SQL puro.

-- COMMAND ----------

-- Quais tabelas existem no schema gold?
SHOW TABLES IN cba_workshop_trilha_tech.gold;

-- COMMAND ----------

-- Quais colunas e tipos a tabela de produção tem?
DESCRIBE TABLE cba_workshop_trilha_tech.gold.fact_production;

-- COMMAND ----------

-- Espie 20 linhas para entender o "jeitão" do dado
SELECT * FROM fact_production LIMIT 20;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > 💬 **Databricks Assistant — EXPLICAR**
-- MAGIC > Selecione a query acima, abra o Assistant (✨) e digite:
-- MAGIC >
-- MAGIC > ```
-- MAGIC > Explique o que esta tabela fact_production representa e o que cada coluna significa,
-- MAGIC > em português, de forma simples para um analista de negócios.
-- MAGIC > ```
-- MAGIC >
-- MAGIC > O Assistant lê o schema e devolve uma descrição em linguagem de negócio. Use isso
-- MAGIC > toda vez que cair numa tabela nova.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 2 · Primeira pergunta de negócio: produção por planta
-- MAGIC
-- MAGIC **Pergunta:** "Quanto cada planta produziu (toneladas) no período?"
-- MAGIC
-- MAGIC Vamos gerar isso com o Assistant em vez de digitar na mão.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > 💬 **Databricks Assistant — GERAR**
-- MAGIC > Em uma célula vazia, abra o Assistant (✨ / Cmd+I) e digite:
-- MAGIC >
-- MAGIC > ```
-- MAGIC > Usando cba_workshop_trilha_tech.gold.fact_production e dim_plantas, me dê o total de
-- MAGIC > toneladas produzidas (tons_produced) por nome de planta (plant_name),
-- MAGIC > ordenado do maior para o menor.
-- MAGIC > ```
-- MAGIC >
-- MAGIC > Revise o que ele gerou e clique em **Aceitar**. Deve sair algo como a query abaixo.

-- COMMAND ----------

-- Produção total por planta
SELECT
  p.plant_name,
  p.state,
  ROUND(SUM(f.tons_produced), 1) AS total_tons
FROM fact_production f
JOIN dim_plantas p ON f.plant_id = p.plant_id
GROUP BY p.plant_name, p.state
ORDER BY total_tons DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > 📊 **Sugestão de gráfico por IA:** depois de rodar, clique em **+ → Visualization**
-- MAGIC > e use o botão de **sugestão de gráfico**. Para "total por categoria", um **gráfico de
-- MAGIC > barras** é o farol certo (não uma tabela com 12 colunas).
-- MAGIC
-- MAGIC > ✅ **Checkpoint:** você consegue dizer, em 1 segundo olhando o gráfico, qual planta
-- MAGIC > produziu mais? Se sim, o gráfico está cumprindo o papel de farol.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3 · Adicionando tempo: produção por mês
-- MAGIC
-- MAGIC **Pergunta:** "Como a produção evoluiu mês a mês?"

-- COMMAND ----------

-- Produção mensal (tendência)
SELECT
  DATE_TRUNC('MONTH', f.date) AS mes,
  ROUND(SUM(f.tons_produced), 1) AS total_tons
FROM fact_production f
GROUP BY DATE_TRUNC('MONTH', f.date)
ORDER BY mes;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > 📊 Para evolução no tempo, o farol é **linha** (line chart), eixo X = `mes`.
-- MAGIC >
-- MAGIC > 💡 **Power BI ↔ Databricks:** `DATE_TRUNC('MONTH', date)` faz aqui o papel da
-- MAGIC > hierarquia de data automática do Power BI. Você agrupa por mês sem precisar de uma
-- MAGIC > tabela calendário separada.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 4 · Custo de energia por tonelada
-- MAGIC
-- MAGIC Regra de negócio CBA (definida no projeto):
-- MAGIC **custo de energia por ton = (energy_kwh / 1000) × 320 R$/MWh**, onde 320 R$/MWh é o
-- MAGIC preço de referência da energia. Energia é o maior custo na produção de alumínio.

-- COMMAND ----------

-- Custo de energia por tonelada, por planta
SELECT
  pl.plant_name,
  ROUND(SUM(f.energy_kwh) / 1000 * 320, 0)                              AS custo_energia_brl,
  ROUND(SUM(f.tons_produced), 1)                                        AS total_tons,
  ROUND( (SUM(f.energy_kwh) / 1000 * 320) / NULLIF(SUM(f.tons_produced), 0), 2)
                                                                        AS custo_energia_por_ton
FROM fact_production f
JOIN dim_plantas pl ON f.plant_id = pl.plant_id
GROUP BY pl.plant_name
ORDER BY custo_energia_por_ton DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > 💬 **Databricks Assistant — CORRIGIR/OTIMIZAR**
-- MAGIC > Se uma query der erro (ex.: dividiu por zero, nome de coluna errado), **não apague tudo**.
-- MAGIC > Selecione a query com erro, abra o Assistant e digite:
-- MAGIC >
-- MAGIC > ```
-- MAGIC > Esta query deu o seguinte erro: <cole a mensagem de erro>. Corrija e explique o que estava errado.
-- MAGIC > ```
-- MAGIC >
-- MAGIC > Repare que usamos `NULLIF(..., 0)` justamente para evitar divisão por zero. O Assistant
-- MAGIC > costuma sugerir esse padrão sozinho.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > ✅ **Checkpoint:** a planta com maior custo de energia por tonelada é a mesma que mais
-- MAGIC > produz? Esse cruzamento já é um insight — e é exatamente o tipo de pergunta que o
-- MAGIC > Genie vai responder no módulo 04.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 5 · Vendas por mercado (Interno × Externo)
-- MAGIC
-- MAGIC **Pergunta:** "Vendemos mais para o mercado interno ou externo? E qual fatura mais?"

-- COMMAND ----------

-- Volume e receita por mercado
SELECT
  market,
  ROUND(SUM(tons_sold), 1)        AS total_tons_vendidas,
  ROUND(SUM(revenue_brl), 0)      AS receita_brl,
  ROUND(SUM(revenue_brl) / NULLIF(SUM(tons_sold), 0), 2) AS receita_por_ton
FROM fact_sales
GROUP BY market
ORDER BY receita_brl DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 6 · Preço médio de mercado (LME) e câmbio
-- MAGIC
-- MAGIC O preço do alumínio é cotado em USD/ton na LME. Como a CBA fatura em reais, o câmbio
-- MAGIC `usd_brl` é decisivo. **Preço BRL = price_usd_ton × usd_brl.**

-- COMMAND ----------

-- Preço LME médio e câmbio médio por mês
SELECT
  DATE_TRUNC('MONTH', date)                      AS mes,
  ROUND(AVG(lme_price_usd_ton), 2)               AS lme_usd_ton_medio,
  ROUND(AVG(usd_brl), 4)                          AS usd_brl_medio,
  ROUND(AVG(lme_price_usd_ton * usd_brl), 2)     AS preco_brl_ton_medio
FROM fact_sales
GROUP BY DATE_TRUNC('MONTH', date)
ORDER BY mes;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC > 💬 **Databricks Assistant — desafio guiado**
-- MAGIC > Peça ao Assistant:
-- MAGIC >
-- MAGIC > ```
-- MAGIC > A partir de cba_workshop_trilha_tech.gold.fact_sales, calcule a margem por tonelada como
-- MAGIC > price_brl_ton menos o custo de energia por ton. O custo de energia por ton vem de
-- MAGIC > fact_production: (energy_kwh/1000*320)/tons_produced, agregado por mês. Junte os dois
-- MAGIC > por mês e mostre a margem média mensal.
-- MAGIC > ```
-- MAGIC >
-- MAGIC > Esse é o cálculo central da narrativa "Do Forno ao Mercado". Guarde a query —
-- MAGIC > vamos transformá-la em **Metric View** no módulo 02 para não reescrever nunca mais.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 7 · Síntese: as 5 perguntas que todo dashboard CBA responde
-- MAGIC
-- MAGIC | # | Pergunta de negócio | Tabela base | Visual farol |
-- MAGIC |---|---------------------|-------------|--------------|
-- MAGIC | 1 | Quanto produzimos? | fact_production | KPI + linha |
-- MAGIC | 2 | Quanto custa a energia? | fact_production | KPI + barras |
-- MAGIC | 3 | Quanto e para quem vendemos? | fact_sales | barras (mercado) |
-- MAGIC | 4 | A que preço o mercado paga? | fact_sales / LME | linha (LME × câmbio) |
-- MAGIC | 5 | Qual a margem? | sales × production | KPI grande + linha |
-- MAGIC
-- MAGIC > ✅ **Checkpoint final do módulo:** você gerou pelo menos 3 queries com o Assistant,
-- MAGIC > corrigiu 1 erro com o Assistant e gerou 1 gráfico com sugestão de IA.
-- MAGIC >
-- MAGIC > ➡️ **Próximo:** `02_metric_views.sql` — transformar essas regras em uma camada
-- MAGIC > semântica reutilizável, para que dashboard e Genie falem a mesma língua.
