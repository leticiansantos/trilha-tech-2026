# 03 · Construindo um AI/BI Dashboard "Farol"
### Trilha Tech 2026 | Workshop Hands-on: Geração de Insights — CBA

> **Princípio do farol (a regra de ouro deste workshop):**
> Um dashboard não é um depósito de colunas. Ele é um **farol**: a pessoa olha e, em
> segundos, **já enxerga o resultado** e o que fazer. Se o usuário precisa "garimpar"
> 3–4 minutos para descobrir a resposta, o dashboard falhou.
> Pergunte sempre: *"Qual é a UMA pergunta que esta tela responde?"*

Vamos construir um **AI/BI Dashboard (Lakeview)** chamado **"Do Forno ao Mercado — Margem CBA"**
sobre as Metric Views do módulo 02.

---

## 1 · As perguntas de negócio (defina ANTES de arrastar gráfico)

| Pergunta | Visual farol | Por quê |
|----------|--------------|---------|
| Qual a margem atual por ton? | **KPI grande** (counter) | é o número que o executivo quer ver primeiro |
| A margem está subindo ou caindo? | **linha** (mês) | tendência > foto do instante |
| Preço de venda x custo de energia? | **linha dupla** | mostra o "aperto" da margem |
| Produzimos quanto e onde? | **barras** (planta) | comparação entre categorias |
| Vendemos mais interno ou externo? | **donut/barras** (market) | composição simples |
| Quais ligas dão mais margem? | **barras ordenadas** | rankeia a ação |

> 💡 **Regra prática:** comparação entre categorias → **barras**; evolução no tempo → **linha**;
> um número que importa → **KPI**; composição → **donut** (só com poucas fatias). Evite tabela
> crua como visual principal — tabela é para detalhe sob demanda, não é farol.

---

## 2 · Datasets do dashboard (queries prontas)

No AI/BI Dashboard, cada gráfico se liga a um **dataset** (uma query salva). Crie estes
datasets na aba **Data** do dashboard. Eles usam as Metric Views — então a margem é sempre
a mesma definição do módulo 02.

**Dataset `margem_mensal`:**
```sql
SELECT
  mes,
  MEASURE(preco_medio_brl_ton)   AS preco_brl_ton,
  MEASURE(custo_energia_por_ton) AS custo_brl_ton,
  MEASURE(margem_brl_ton)        AS margem_brl_ton,
  MEASURE(margem_pct)            AS margem_pct
FROM cba_workshop_trilha_tech.gold.mv_margem
GROUP BY mes
ORDER BY mes;
```

**Dataset `margem_kpi`** (último mês, para o KPI grande):
```sql
SELECT
  MEASURE(margem_brl_ton) AS margem_atual,
  MEASURE(margem_pct)     AS margem_pct
FROM cba_workshop_trilha_tech.gold.mv_margem
WHERE mes = (SELECT MAX(mes) FROM cba_workshop_trilha_tech.gold.mv_margem);
```

**Dataset `producao_por_planta`:**
```sql
SELECT
  plant_name,
  MEASURE(total_tons)            AS total_tons,
  MEASURE(custo_energia_por_ton) AS custo_por_ton
FROM cba_workshop_trilha_tech.gold.mv_producao
GROUP BY plant_name
ORDER BY total_tons DESC;
```

**Dataset `vendas_por_mercado`:**
```sql
SELECT
  market,
  MEASURE(total_tons_vendidas) AS tons,
  MEASURE(receita_brl)         AS receita
FROM cba_workshop_trilha_tech.gold.mv_vendas
GROUP BY market;
```

**Dataset `margem_por_liga`:**
```sql
SELECT
  alloy_name,
  MEASURE(margem_brl_ton) AS margem_brl_ton
FROM cba_workshop_trilha_tech.gold.mv_margem
GROUP BY alloy_name
ORDER BY margem_brl_ton DESC;
```

---

## 3 · Passo a passo na UI (AI/BI Dashboards / Lakeview)

1. No menu lateral esquerdo, clique em **Dashboards** → botão **Create dashboard**.
2. Dê o nome **"Do Forno ao Mercado — Margem CBA"** (clique no título no topo).
3. Confirme o **SQL Warehouse Serverless** no seletor superior direito.
4. Abra a aba **Data** (rodapé) → **+ Create from SQL** → cole o dataset `margem_mensal`
   → **Run** → renomeie o dataset para `margem_mensal`. Repita para os 5 datasets acima.
5. Volte para a aba **Canvas**.

**Criar o KPI de margem (o farol principal):**
6. Clique em **Add a visualization** (ícone de gráfico) e desenhe um retângulo no topo.
7. No painel direito, **Dataset** = `margem_kpi`; **Visualization** = **Counter**.
8. Field = `margem_atual`; em **Format**, prefixo `R$ `, sufixo ` /ton`, 2 casas.
9. Posicione no **canto superior esquerdo, grande**. É a primeira coisa que o olho vê.

**Criar a linha de tendência da margem:**
10. **Add a visualization** ao lado do KPI. **Dataset** = `margem_mensal`.
11. **Visualization** = **Line**; X = `mes`; Y = `margem_brl_ton`.
12. Título do widget: *"Margem por tonelada (R$) — tendência mensal"*.

**Criar a linha dupla preço × custo (o "aperto" da margem):**
13. Novo widget, dataset `margem_mensal`, **Line**, X = `mes`, Y = `preco_brl_ton` **e**
    `custo_brl_ton` (duas séries). Título: *"Preço de venda × Custo de energia (R$/ton)"*.

**Produção por planta + vendas por mercado:**
14. Widget **Bar**, dataset `producao_por_planta`, X = `plant_name`, Y = `total_tons`.
15. Widget **Bar** (ou **Pie/Donut**), dataset `vendas_por_mercado`, categoria = `market`,
    valor = `receita`.

**Ranking de margem por liga:**
16. Widget **Bar (horizontal)**, dataset `margem_por_liga`, ordenado desc. Título:
    *"Quais ligas dão mais margem?"*.

---

## 4 · Sugestão de gráficos por IA (Databricks Assistant no dashboard)

> 💬 **Databricks Assistant — gerar visual por linguagem natural**
> No dashboard, clique em **Add a visualization** e use o campo de **Assistant / "Ask the
> Assistant"** dentro do widget. Digite, por exemplo:
>
> ```
> Mostre a margem por tonelada ao longo dos meses como um gráfico de linha,
> com o eixo Y formatado em reais.
> ```
>
> O Assistant escolhe o tipo de gráfico, os eixos e a formatação. **Sempre revise:** se ele
> sugerir uma tabela com 10 colunas, troque por barras/linha — lembre do princípio do farol.

---

## 5 · Filtros e parâmetros (deixe o usuário explorar sem virar bagunça)

17. Na aba **Canvas**, clique em **Add a filter** (ícone de funil).
18. Adicione um filtro **Date range** ligado ao campo `mes` de `margem_mensal`.
19. Adicione um filtro **Single/Multi select** por `alloy_name` (ligado a `margem_por_liga`).
20. Adicione um filtro por `market` (Interno/Externo).

> **Farol também vale para filtro:** 3 filtros bem escolhidos > 10 filtros. O usuário tem
> que entender em 1 segundo o que cada filtro faz.

---

## 6 · Layout do farol (ordem de leitura)

```
┌──────────────┬───────────────────────────────────────┐
│  KPI MARGEM  │   Linha: margem por ton (tendência)    │  ← resposta imediata + direção
│  R$ /ton     │                                        │
├──────────────┴───────────────────────────────────────┤
│   Linha dupla: preço de venda × custo de energia      │  ← por que a margem mexeu
├───────────────────────┬───────────────────────────────┤
│ Barras: produção/planta│ Donut: receita interno×externo│  ← contexto operacional/comercial
├───────────────────────┴───────────────────────────────┤
│   Barras: margem por liga (ranking)                   │  ← onde agir
└────────────────────────────────────────────────────────┘
```
Leitura de cima para baixo, esquerda para direita: **resultado → direção → causa → contexto → ação.**

---

## 7 · Publicar e compartilhar

21. Clique em **Publish** (canto superior direito) para gerar a versão consumível.
22. Clique em **Share** → adicione os usuários/grupos → permissão **Can view** (consumidores)
    ou **Can edit** (analistas). Use grupos do Unity Catalog, não e-mails soltos.
23. Para consumidores externos à área, marque **Run as owner** para que vejam os dados sem
    precisar de acesso direto às tabelas (respeitando a governança definida pelo owner).
24. (Opcional) Configure **Schedule** para enviar um snapshot por e-mail toda segunda 8h.

> ✅ **Checkpoint do módulo:** abra o dashboard publicado e cronometre — em **menos de 10
> segundos** alguém de fora consegue dizer "a margem está em R$ X/ton e está subindo/caindo
> porque o custo de energia subiu"? Se sim, você construiu um farol. 🔦
>
> ➡️ **Próximo:** `04_genie_space.md` — deixar qualquer pessoa perguntar isso em português,
> sem abrir o dashboard.
