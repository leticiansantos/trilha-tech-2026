# 05 · Capstone — "Geração de Insights"
### Trilha Tech 2026 | Workshop Hands-on: Geração de Insights — CBA

> **Missão:** cada grupo recebe **um domínio** da narrativa "Do Forno ao Mercado", constrói
> **um AI/BI Dashboard farol** + **um Genie space** sobre esse domínio e apresenta **3
> insights acionáveis** para a turma. Tempo: ~60 min de construção + 5 min de pitch por grupo.

---

## 1 · Domínios (1 por grupo)

| Grupo | Domínio | Tabelas / Metric Views | Pergunta central |
|-------|---------|------------------------|------------------|
| A | **Produção** | `mv_producao`, `fact_production`, `dim_plantas` | Onde produzimos mais e com que eficiência (OEE)? |
| B | **Custo / Energia** | `mv_producao`, `fact_production` | Onde a energia mais pesa no custo por tonelada? |
| C | **Vendas / Mercado** | `mv_vendas`, `fact_sales`, LME, câmbio | Interno × externo: onde está a receita e o preço? |
| D | **Qualidade** | `mv_qualidade`, `furnace_inspections` | Onde estão os defeitos e quanto custam? |
| (Integrador) | **Margem** | `mv_margem` | Como o custo do forno × preço de mercado define a margem? |

> Se houver poucos grupos, o domínio **Margem** vira o grupo "executivo" que consome os
> resultados dos demais.

---

## 2 · Entregáveis (o que cada grupo deve produzir)

1. **1 Dashboard "farol"** com no mínimo:
   - 1 **KPI** (o número que importa no domínio),
   - 1 **gráfico de tendência** (linha, no tempo),
   - 1 **comparação** (barras),
   - 1 **filtro** útil (período ou categoria).
   - Construído respeitando o princípio do farol: **resposta primeiro, detalhe depois**.
2. **1 Genie space** do domínio com: tabelas escolhidas, **instruções em português**,
   **glossário** (mín. 3 termos) e **2 sample queries**.
3. **3 insights acionáveis** escritos em 1 frase cada (formato: *"Observação → então
   recomendação"*). Ex.: *"A planta X tem custo de energia 18% acima da média → priorizar
   auditoria energética dos fornos dela."*

---

## 3 · Roteiro sugerido (60 min)

| Tempo | Atividade |
|-------|-----------|
| 0–10 | Explorar o domínio no SQL Editor com o **Assistant** (gerar 2–3 queries) |
| 10–20 | Conferir/usar as **Metric Views**; criar uma medida nova se faltar |
| 20–40 | Montar o **Dashboard farol** (KPI + tendência + comparação + filtro) |
| 40–50 | Criar o **Genie space**, escrever instruções + glossário + samples |
| 50–60 | Caçar os **3 insights** (use o Genie para perguntar à vontade) |

> 💬 **Dica:** use o Genie para *descobrir* os insights ("o que mudou mais no último
> trimestre?") e o Dashboard para *comunicá-los*.

---

## 4 · Pitch (5 min por grupo)

1. Mostrar o **dashboard** e explicar **em 30s** qual a pergunta que ele responde (teste do farol).
2. Fazer **1 pergunta ao vivo no Genie**, em português.
3. Apresentar os **3 insights acionáveis**.

---

## 5 · Rubrica de avaliação (0–20 pontos)

| Critério | Peso | O que buscamos | Pontos |
|----------|------|----------------|--------|
| **Farol / clareza** | 5 | A resposta aparece em segundos; sem despejo de colunas; bom uso de KPI/linha/barra | 0–5 |
| **Correção dos números** | 4 | Usou Metric Views; margem/custo batem com a definição oficial | 0–4 |
| **Uso de IA (Assistant + Genie)** | 4 | Gerou SQL com Assistant; Genie responde bem em português (instruções/glossário/samples) | 0–4 |
| **Insights acionáveis** | 4 | 3 insights claros, no formato observação → recomendação | 0–4 |
| **Design & storytelling** | 3 | Layout em ordem de leitura; filtros úteis; pitch convincente | 0–3 |

**Faixas:** 17–20 excelente · 13–16 bom · 9–12 satisfatório · <9 revisar conceitos.

> ✅ **Critério de aprovação do workshop:** todo participante (1) gerou SQL com o Assistant,
> (2) construiu ou contribuiu para 1 dashboard farol, (3) curou e consultou 1 Genie space, e
> (4) entregou pelo menos 1 insight acionável.

---

## 6 · Insights de referência (gabarito para o facilitador)

Use para guiar grupos travados (não revele antes do pitch):

- **Produção:** a planta com maior volume não é necessariamente a mais eficiente (OEE) —
  cruzar `total_tons` × `oee_qualidade_pct`.
- **Custo/Energia:** custo de energia por ton varia entre plantas; a de maior custo merece
  auditoria. Picos mensais costumam acompanhar paradas/retomadas de fornos.
- **Vendas/Mercado:** mercado externo tende a ter preço (R$/ton) sensível ao câmbio — quando
  o dólar sobe, a receita por ton externa sobe mesmo com volume estável.
- **Qualidade:** poucos `defect_type` concentram a maior parte dos defeitos (Pareto) — agir
  nos 2–3 principais.
- **Margem:** a margem aperta quando o custo de energia sobe **e/ou** o LME×câmbio cai;
  o farol é a linha dupla preço × custo.
