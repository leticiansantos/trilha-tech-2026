# 04 · Criando um AI/BI Genie space em português
### Trilha Tech 2026 | Workshop Hands-on: Geração de Insights — CBA

> **O que é o Genie?** Um **AI/BI Genie space** deixa qualquer pessoa **perguntar em
> português** ("qual foi a margem da liga X em março?") e receber a resposta com tabela e
> gráfico — sem escrever SQL. É o grande **nivelador** do grupo: quem nunca escreveu uma
> query consegue extrair insight; quem é avançado ganha velocidade.
>
> 💡 **Power BI ↔ Databricks:** é parecido com o "Perguntas e Respostas (Q&A)" do Power BI,
> mas roda direto sobre as tabelas/Metric Views governadas no Unity Catalog e usa as
> instruções e o glossário que **você** escreve para acertar a linguagem da CBA.

A qualidade do Genie vem de **3 coisas**: (1) escolher as tabelas certas, (2) escrever boas
**instruções/contexto** e **glossário**, (3) dar **sample queries** (perguntas exemplo
com a SQL correta). Vamos fazer as três.

---

## 1 · Criar o space e escolher as tabelas

1. Menu lateral → **Genie** → **New** (ou **Genie** dentro do SQL/Dashboards → **New space**).
2. Nome: **"Genie — Do Forno ao Mercado (CBA)"**.
3. Selecione o **SQL Warehouse Serverless**.
4. Em **Data**, adicione (priorize as **Metric Views**, pois já têm a regra de negócio):
   - `cba_trilha_tech.gold.mv_margem`
   - `cba_trilha_tech.gold.mv_producao`
   - `cba_trilha_tech.gold.mv_vendas`
   - (opcional, detalhe) `fact_production`, `fact_sales`, `dim_plantas`, `dim_ligas`
5. **Save**.

> Menos é mais: comece com as 3 Metric Views. Tabela demais confunde o Genie (e o usuário).

---

## 2 · Instruções / contexto do space (escreva em português)

Cole isto no campo **Instructions** (engrenagem do space → **Instructions**):

```
Você é o assistente de análise da CBA (Companhia Brasileira de Alumínio).
Responda sempre em português do Brasil, de forma direta e orientada à decisão.

Contexto de negócio:
- A CBA produz alumínio. O maior custo de produção é energia elétrica.
- A narrativa central é "Do Forno ao Mercado": cruzamos o custo de produção
  (telemetria dos fornos) com o preço de mercado (LME em USD/ton e câmbio USD/BRL)
  para chegar na MARGEM.
- Use SEMPRE as Metric Views (mv_margem, mv_producao, mv_vendas) como fonte de verdade.
- Valores monetários em Reais (R$). Toneladas com 1 casa decimal.
- Quando o usuário não informar período, considere os últimos 12 meses.
- Ao mostrar margem, prefira margem por tonelada (R$/ton) e também a margem percentual.
- Quando fizer sentido, traga um gráfico de linha para tendências e barras para comparações.
```

---

## 3 · Glossário de negócio (term → definição)

Adicione em **Instructions** (ou na seção de **glossary**, se disponível) os termos da casa.
Isso evita que o Genie "invente" o cálculo:

```
- "margem": margem por tonelada = preço médio de venda (R$/ton) menos custo de energia por ton (R$/ton). Use mv_margem (medida margem_brl_ton).
- "margem percentual": medida margem_pct de mv_margem.
- "custo de energia por ton": (energy_kwh/1000 * 320 R$/MWh) / toneladas produzidas. Use mv_producao (custo_energia_por_ton).
- "refugo" / "defeito": peças fora de especificação; ver coluna defects (produção) ou is_defect (inspeções).
- "OEE": neste workshop, OEE simplificado = % da produção sem defeito (medida oee_qualidade_pct de mv_producao).
- "mercado interno": vendas com market = 'Interno'. "mercado externo": market = 'Externo'.
- "LME": London Metal Exchange, preço de referência do alumínio em USD/ton (lme_price_usd_ton).
- "câmbio": cotação USD/BRL (usd_brl); preço em R$ = preço em USD x câmbio.
- "planta": unidade produtora (dim_plantas.plant_name). "liga": tipo de alumínio (dim_ligas.alloy_name).
```

---

## 4 · Sample queries (ensine o Genie com exemplos certos)

Em **Sample queries / Example questions**, adicione pares pergunta → SQL. O Genie aprende o
padrão e passa a acertar perguntas parecidas.

**Exemplo 1 — "Qual a margem média por liga nos últimos 12 meses?"**
```sql
SELECT alloy_name, MEASURE(margem_brl_ton) AS margem_brl_ton
FROM cba_trilha_tech.gold.mv_margem
WHERE mes >= DATE_TRUNC('MONTH', ADD_MONTHS(CURRENT_DATE(), -12))
GROUP BY alloy_name
ORDER BY margem_brl_ton DESC;
```

**Exemplo 2 — "Como evoluiu o custo de energia por tonelada por planta?"**
```sql
SELECT mes, plant_name, MEASURE(custo_energia_por_ton) AS custo_por_ton
FROM cba_trilha_tech.gold.mv_producao
GROUP BY mes, plant_name
ORDER BY mes;
```

**Exemplo 3 — "Vendemos mais para o mercado interno ou externo este ano?"**
```sql
SELECT market, MEASURE(total_tons_vendidas) AS tons, MEASURE(receita_brl) AS receita
FROM cba_trilha_tech.gold.mv_vendas
WHERE mes >= DATE_TRUNC('YEAR', CURRENT_DATE())
GROUP BY market
ORDER BY receita DESC;
```

---

## 5 · Perguntas para os alunos testarem (em português)

Peça para a turma digitar no Genie e conferir se a resposta faz sentido:

1. *Qual foi a margem por tonelada no último mês?*
2. *Qual planta tem o maior custo de energia por tonelada?*
3. *Mostre a evolução do preço LME e do câmbio nos últimos 12 meses.*
4. *Qual liga é a mais lucrativa?*
5. *A margem caiu quando o custo de energia subiu? Mostre num gráfico.*
6. *Qual a receita no mercado externo por região?*
7. *Qual a taxa de defeito por tipo de defeito?* (se tiver criado a `mv_qualidade`)

---

## 6 · Iterar na qualidade das respostas

Quando o Genie errar (cálculo estranho, tabela errada, resposta em inglês):

1. Clique no **👎 / "Provide feedback"** abaixo da resposta.
2. Abra a query que ele gerou ("Show generated code"): veja **onde** errou.
3. Conserte na fonte certa:
   - errou o **cálculo** → adicione/ajuste o termo no **glossário**;
   - usou a **tabela errada** → reforce nas **instruções** ("use sempre mv_margem para margem");
   - acertou? → salve como **Sample query / Trusted asset** para reforçar o padrão.
4. Re-teste a mesma pergunta. Genie melhora com a curadoria — trate como produto vivo.

> ✅ **Checkpoint:** uma pergunta que errava na 1ª tentativa agora acerta depois de você
> ajustar instruções/glossário. Isso é o loop de melhoria do Genie.

---

## 7 · Permissões (Unity Catalog)

- O Genie respeita as permissões do **Unity Catalog**: o usuário só vê dados das tabelas/
  Metric Views às quais ele (ou seu grupo) tem `SELECT`.
- Compartilhe o space: **Share** → grupo `cba_analistas` → **Can view** (perguntar) ou
  **Can edit** (curar instruções/samples).
- Garanta `SELECT` nas Metric Views/tabelas para o grupo:
  ```sql
  GRANT SELECT ON VIEW cba_trilha_tech.gold.mv_margem   TO `cba_analistas`;
  GRANT SELECT ON VIEW cba_trilha_tech.gold.mv_producao TO `cba_analistas`;
  GRANT SELECT ON VIEW cba_trilha_tech.gold.mv_vendas   TO `cba_analistas`;
  ```
- **Boa prática:** dê acesso via **Metric Views certificadas** em vez das tabelas cruas —
  o usuário pergunta sobre "margem" sem nunca tocar nas colunas brutas.

> ✅ **Checkpoint final do módulo:** alguém que **nunca escreveu SQL** conseguiu, sozinho,
> responder 3 das perguntas da seção 5. O Genie nivelou o grupo. 🎯
>
> ➡️ **Próximo:** `05_capstone.md` — cada grupo constrói seu próprio dashboard + Genie e
> apresenta 3 insights.
