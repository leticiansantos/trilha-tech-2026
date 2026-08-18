# Apostila do Aluno
# Trilha Tech 2026 | Workshop Hands-on: Geração de Insights
### Companhia Brasileira de Alumínio (CBA) — perfil Data Analyst

---

## Bem-vindo(a)

Este workshop é **hands-on**: você vai sair daqui tendo construído, com as próprias mãos,
um **dashboard** e um **Genie space** que respondem perguntas reais de negócio da CBA. Você
**não precisa** ser fera em SQL. Vai aprender a usar o **Databricks Assistant** (copiloto de
SQL) e o **AI/BI Genie** (perguntas em português) para chegar lá — eles nivelam o grupo.

### Objetivos
Ao final, você será capaz de:
- Explorar tabelas no **SQL Editor** usando o **Databricks Assistant** (gerar, explicar e corrigir SQL).
- Entender e usar **UC Metric Views** como camada semântica única (a "fonte de verdade").
- Projetar um **AI/BI Dashboard "farol"** que entrega o resultado, não um amontoado de colunas.
- Criar e curar um **AI/BI Genie space** em português para perguntas em linguagem natural.
- Extrair e comunicar **insights acionáveis**.

### Pré-requisitos
- Acesso ao workspace Databricks da CBA e ao catálogo `cba_workshop_trilha_tech`.
- Um **SQL Warehouse Serverless** disponível.
- Permissão de leitura no schema `gold`.
- Navegador (Chrome/Edge). Nenhuma instalação local necessária.

### Agenda (~4h)

| Bloco | Duração | Módulo |
|-------|---------|--------|
| Abertura | 20 min | Narrativa, princípio do dashboard "farol", o que é Assistant e Genie |
| Módulo 1 | 45 min | `01_sql_explore.sql` — SQL com o Assistant |
| Módulo 2 | 35 min | `02_metric_views.sql` — Metric Views (camada semântica) |
| Café | 10 min | — |
| Módulo 3 | 45 min | `03_aibi_dashboard.md` — Dashboard farol |
| Módulo 4 | 35 min | `04_genie_space.md` — Genie space em português |
| Capstone | 60 min | `05_capstone.md` — construir + apresentar 3 insights |
| Encerramento | 10 min | Próximos passos |

---

## Abertura: a narrativa "Do Forno ao Mercado"

A CBA produz alumínio. Dois grandes números definem o resultado:
- **Custo de produção** — puxado principalmente pela **energia** dos fornos (telemetria
  "Gorila").
- **Preço de mercado** — o alumínio é cotado na **LME** (USD/ton) e convertido por **câmbio**
  (USD/BRL).

A diferença entre os dois é a **margem**. Nesta trilha consumimos as tabelas **GOLD/fato** e
respondemos: *produção, custo de energia, preço de mercado, margem e qualidade.*

### O princípio do dashboard "farol" 🔦
> "Não adianta plotar todas as colunas e fazer a pessoa perder 3–4 minutos garimpando.
> Se ela quer um resultado, **traga o resultado** — como um farol."

Antes de qualquer gráfico, pergunte: **"Qual é a UMA pergunta que esta tela responde?"**
- Comparação entre categorias → **barras**
- Evolução no tempo → **linha**
- Um número que importa → **KPI**
- Composição (poucas partes) → **donut**
- Tabela crua → só para **detalhe sob demanda**, nunca como visual principal.

### Seus dois copilotos
- **Databricks Assistant:** escreve, explica e corrige SQL para você. Atalho **Cmd/Ctrl + I**
  ou ícone ✨ na célula. Também sugere **gráficos** por IA.
- **AI/BI Genie:** responde perguntas em **português** sobre os dados, sem você escrever SQL.

---

## Power BI ↔ Databricks (leia se você vem do Power BI)

| No Power BI… | …no Databricks |
|--------------|----------------|
| Importar/atualizar dataset (.pbix) | Consulta direta à fonte governada (Unity Catalog), sem "refresh" |
| Power Query (M) para preparar dados | SQL no SQL Editor (com o Assistant ajudando) |
| Medidas DAX | **Metric Views** (medidas definidas uma vez, reaproveitadas por todos) |
| Modelo semântico no arquivo | Metric View **no catálogo**, versionada e certificada |
| Perguntas e Respostas (Q&A) | **AI/BI Genie** (com instruções e glossário em português) |
| Relatório / página | **AI/BI Dashboard (Lakeview)** |
| RLS (Row-Level Security) | Permissões e máscaras do **Unity Catalog** |
| "Sugerir visual" | **Sugestão de gráfico por IA** (Assistant) |

**Mensagem-chave:** você não está abandonando o que sabe — está ganhando uma camada governada
e copilotos de IA. E **não está limitado ao Power BI**: dá para entregar o insight direto no
Databricks.

---

## Módulo 1 — Explorar com SQL + Assistant
**Arquivo:** `notebooks/01_sql_explore.sql`

**Contexto CBA:** as tabelas GOLD já estão prontas (a Trilha de Engenharia montou o pipeline).
Seu trabalho é fazer perguntas a elas.

**Passo a passo:**
1. Abra o SQL Editor e selecione o **Warehouse Serverless**.
2. Rode `SHOW TABLES` e `DESCRIBE` para conhecer o terreno.
3. Use o Assistant para **gerar** "produção por planta", **explicar** uma tabela e **corrigir** um erro.
4. Gere um gráfico de barras e um de linha com a sugestão de IA.

> 💬 **Assistant — gerar:** *"Usando fact_production e dim_plantas, total de toneladas por
> plant_name, do maior para o menor."*
>
> 💬 **Assistant — explicar:** *"Explique o que cada coluna de fact_production significa, em
> português, para um analista de negócios."*
>
> 💬 **Assistant — corrigir:** *"Esta query deu este erro: <cole o erro>. Corrija e explique."*

**Exercícios:**
- E1.1: produção mensal (linha).
- E1.2: custo de energia por ton por planta (regra: `energy_kwh/1000*320`).
- E1.3: vendas por mercado (Interno × Externo) — volume e receita.

✅ **Checkpoints:** gerou 3 queries com o Assistant · corrigiu 1 erro · criou 1 gráfico por IA.

---

## Módulo 2 — Metric Views (camada semântica)
**Arquivo:** `notebooks/02_metric_views.sql`

**Contexto CBA:** se cada pessoa calcular "margem" de um jeito, o dashboard e o Genie
discordam. A Metric View resolve isso — a regra mora num lugar só.

**Passo a passo:**
1. Crie `mv_producao` (custo/ton + OEE de qualidade).
2. Crie `mv_vendas` (receita, preço, mercado, LME, câmbio).
3. Crie `mv_margem` (preço − custo = margem).
4. Consulte com `MEASURE(...)` e **certifique** as views (COMMENT).

> 💬 **Assistant — sua vez:** *"Crie uma UC Metric View mv_qualidade sobre furnace_inspections
> com dimensão defect_type e medida taxa_defeito_pct = AVG(is_defect)*100. Use WITH METRICS
> LANGUAGE YAML."*

**Exercício E2.1:** adicione à `mv_vendas` uma medida `ticket_medio_pedido` e teste por região.

✅ **Checkpoint:** consultou margem via `MEASURE(margem_brl_ton)` **sem reescrever a fórmula**.

---

## Módulo 3 — Dashboard "farol"
**Arquivo:** `notebooks/03_aibi_dashboard.md`

**Contexto CBA:** o gestor de fornos quer abrir uma tela e, em segundos, saber se a margem
está saudável e por quê.

**Passo a passo (resumo — detalhes no .md):**
1. Crie o dashboard "Do Forno ao Mercado — Margem CBA".
2. Crie os datasets (queries prontas no .md) sobre as Metric Views.
3. Monte: **KPI de margem** → **linha de tendência** → **linha dupla preço × custo** →
   **barras de produção** → **donut interno/externo** → **ranking de margem por liga**.
4. Use a **sugestão de gráfico por IA** e **revise** (nada de tabela com 10 colunas).
5. Adicione filtros de período, liga e mercado. **Publish** + **Share**.

> 💬 **Assistant no dashboard:** *"Mostre a margem por tonelada ao longo dos meses como linha,
> eixo Y em reais."*

**Exercício E3.1:** cronometre — alguém de fora entende a margem em **menos de 10 segundos**?

✅ **Checkpoint:** dashboard publicado passa no "teste do farol".

---

## Módulo 4 — Genie space em português
**Arquivo:** `notebooks/04_genie_space.md`

**Contexto CBA:** nem todo mundo vai abrir o dashboard. Muitos preferem **perguntar**. O Genie
nivela: quem não sabe SQL extrai insight em português.

**Passo a passo (resumo):**
1. Crie o space, adicione as **Metric Views**.
2. Escreva **instruções** em português (responder em PT-BR, usar mv_*, R$, etc.).
3. Preencha o **glossário** (margem, refugo, OEE, LME, câmbio...).
4. Adicione **sample queries**.
5. Teste as perguntas da seção 5 do .md e **itere** quando errar.

> 💬 **Genie — teste:** *"Qual liga é a mais lucrativa?"* · *"A margem caiu quando a energia
> subiu? Mostre num gráfico."*

**Exercício E4.1:** ache uma pergunta que o Genie erra, conserte via glossário/instruções e
faça ela acertar.

✅ **Checkpoint:** alguém que nunca escreveu SQL respondeu 3 perguntas pelo Genie.

---

## Capstone — Geração de Insights
**Arquivo:** `notebooks/05_capstone.md`

Cada grupo pega um domínio (Produção, Custo/Energia, Vendas/Mercado, Qualidade, Margem),
constrói **dashboard farol + Genie space** e apresenta **3 insights acionáveis** (formato:
*observação → recomendação*). Avaliação pela rubrica (0–20).

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| "Table or view not found" | catálogo/schema errados | rode `USE CATALOG cba_workshop_trilha_tech; USE SCHEMA gold;` ou use nome completo |
| Query lenta / "warehouse stopped" | warehouse parado/frio | selecione o Warehouse Serverless; aguarde o cold start (segundos) |
| Divisão por zero / NULL estranho | denominador zero | use `NULLIF(coluna, 0)` no divisor |
| Genie responde em inglês | falta instrução de idioma | reforce nas Instructions: "responda sempre em português" |
| Genie usa tabela errada | contexto fraco | reforce "use sempre mv_margem para margem"; adicione sample query |
| Margem do dashboard ≠ do Genie | definições diferentes | os dois devem usar **a mesma Metric View** (`mv_margem`) |
| Não consigo ver dados | sem `SELECT` no UC | peça `GRANT SELECT` ao owner / ao seu grupo |
| Gráfico "feio"/confuso | despejou colunas | volte ao princípio do farol: 1 pergunta por visual |

---

## Próximos passos
- Agende uma **atualização** (Schedule) do seu dashboard e compartilhe com sua squad.
- Transforme suas queries recorrentes em **Metric Views** e proponha como **certificadas**.
- Use o **Genie** no dia a dia antes de pedir um relatório novo — muitas respostas já estão lá.
- Explore **alerts** (Databricks SQL) para ser avisado quando a margem cair de um limite.
- Conecte com as outras trilhas: Engenharia (pipeline GOLD) e MLOps (previsões que alimentam
  novos insights).
