# Apostila do Aluno — Workshop Hands-on: MLOps na prática

**Trilha Tech 2026 | CBA (Companhia Brasileira de Alumínio)**
**Perfil:** Ciência de Dados, MLOps e Agentes · **Duração:** ~4h (meio período)

---

## Bem-vindo(a) à trilha "Do Forno ao Mercado"

O alumínio da CBA nasce nas **cubas eletrolíticas** (fornos), monitoradas pelo sistema de
telemetria **Gorila**, e termina vendido a um **preço de mercado** que depende do índice **LME**
e do **dólar**. A margem da empresa é a diferença entre esse preço e o **custo de produção** — e
o maior componente do custo é a **energia**.

Nesta trilha de **MLOps** você vai consumir as tabelas **GOLD** preparadas pela trilha de
Engenharia e construir, ponta a ponta, uma solução de Machine Learning que ataca custo e
qualidade — e ainda um **agente de IA** para apoiar a manutenção.

### O que você vai construir
1. 🔢 **Regressão** — prever a energia por tonelada (`energy_kwh_ton`) dos fornos.
2. ⚠️ **Classificação binária** — prever defeitos de qualidade (`is_defect`).
3. 🤖 **Agente de RCA** — assistente de análise de causa raiz de manutenção.

### A metodologia: CRISP-DM
Vamos seguir o ciclo clássico de projetos de dados:

`Entendimento do Negócio → Entendimento dos Dados (EDA) → Preparação → Modelagem → Avaliação → Implantação`

Cada módulo do workshop corresponde a uma ou mais etapas desse ciclo.

### A ferramenta que nivela a turma: Genie Code (Databricks Assistant)
Você **não precisa decorar sintaxe**. Em todos os módulos vamos gerar código a partir de
**linguagem natural em português** usando o **Databricks Assistant** (o "vibe code"):
- Abra o painel com o ícone ✨ na barra lateral, ou `Ctrl/Cmd + I` dentro de uma célula.
- Digite o que você quer em português.
- Reveja o código gerado, rode, e use **/explain** para entender e **/fix** para corrigir erros.
- **Regra de ouro:** entenda o código antes de executar. O Assistant acelera; você decide.

---

## Pré-requisitos
- Acesso ao workspace Databricks da CBA e ao catálogo `cba_workshop_trilha_tech`.
- Um cluster (ou compute) com **Databricks Runtime for Machine Learning** (traz scikit-learn,
  MLflow, AutoML, XGBoost).
- Noções básicas de Python e SQL ajudam, mas **não são obrigatórias** — o Genie Code cobre a lacuna.
- Permissão para criar seu schema pessoal e endpoints de serving (o instrutor confirma).

---

## Agenda (~4h)

| Tempo | Módulo | Etapa CRISP-DM | Notebook |
|---|---|---|---|
| 0:00–0:20 | **Abertura** — narrativa, CRISP-DM, MLOps no Databricks, o que é Genie Code e o que é um agente | Entendimento do Negócio | — |
| 0:20–0:50 | **Módulo 1** — EDA: estatísticas, correlações, nulos, distribuição de labels | Entendimento dos Dados | `01_eda.py` |
| 0:50–1:20 | **Módulo 2** — Feature Engineering em Unity Catalog, split treino/teste | Preparação | `02_feature_engineering.py` |
| 1:20–1:50 | **Módulo 3** — Regressão (energia) com MLflow autolog, comparação de runs | Modelagem | `03_train_regression.py` |
| 1:50–2:00 | ☕ **Intervalo** | — | — |
| 2:00–2:35 | **Módulo 4** — Classificação (defeito) com Databricks AutoML (glass-box) | Modelagem | `04_automl_classification.py` |
| 2:35–3:05 | **Módulo 5** — Registro no UC, aliases @champion/@challenger, governança | Avaliação | `05_mlflow_registry_champion.py` |
| 3:05–3:30 | **Módulo 6** — Model Serving (scale-to-zero), inferência em lote e `ai_query` | Implantação | `06_model_serving_ai_query.py` |
| 3:30–4:00 | **Módulo 7** — Agente de RCA (Agent Framework), avaliação, deploy | Implantação | `07_rca_agent.py` |

---

## Módulo 1 — EDA: entender os dados antes de modelar

**Contexto CBA:** energia é o maior custo do alumínio. Antes de prever qualquer coisa, precisamos
saber como a energia se relaciona com as variáveis do forno.

**Passo a passo:**
1. Abra `01_eda.py`. Rode a célula de configuração (cria seu schema `mlops_<seu_usuario>`).
2. Inspecione `furnace_telemetry`: schema, contagem, amostra.
3. Gere as **estatísticas descritivas** das colunas numéricas.
4. Conte os **nulos** — note ~1% em `vibration_mm_s` — e veja a estratégia de imputação pela mediana.
5. Monte a **matriz de correlação** e o **scatter energia × temperatura**.
6. Veja a **distribuição dos labels** `is_failure` (~1,5%) e `is_defect` (~10%).

> 💬 **Genie Code:** *"Crie um DataFrame pandas com uma amostra de 50 mil linhas de
> `cba_workshop_trilha_tech.gold.furnace_telemetry` para gráficos."*

**✅ Checkpoint:** Você consegue dizer qual variável prever na regressão e na classificação, e que
a energia **sobe** com a temperatura.

**🎯 Exercício:** Peça via Genie Code um histograma de `energy_kwh_ton` e a correlação de
`amperage_ka` com a energia.

---

## Módulo 2 — Preparação & Feature Engineering em Unity Catalog

**Contexto CBA:** queremos features **reutilizáveis e governadas**. Registrar features no UC evita
que treino e produção usem cálculos diferentes (*training-serving skew*).

**Passo a passo:**
1. Monte o dataset de **regressão** com a chave `reading_id` (forno + timestamp).
2. Crie a **Feature Table** `furnace_energy_features` com `FeatureEngineeringClient`.
3. Faça o **split** 80/20 (seed 42) → tabelas `energy_train` / `energy_test`.
4. Monte o dataset de **classificação** juntando `furnace_inspections` com a telemetria média por forno.
5. Salve `defect_dataset`.

> 💬 **Genie Code:** *"Crie uma feature table no Unity Catalog com chave primária `reading_id`."*

**✅ Checkpoint:** Feature Table criada; `energy_train`/`energy_test` e `defect_dataset` salvos.

**🎯 Exercício:** Adicione a feature "desvio de temperatura" `abs(temperature_c - 960)` e recrie a
feature table.

---

## Módulo 3 — Modelagem: regressão de energia com MLflow

**Contexto CBA:** prever o consumo de energia ajuda a identificar fornos ineficientes e a planejar.

**Passo a passo:**
1. Ative `mlflow.sklearn.autolog()` e defina `mlflow.set_registry_uri("databricks-uc")`.
2. Treine o **baseline** (Regressão Linear) — RMSE, R², MAE no teste.
3. Treine o **desafiante** (Gradient Boosting) e compare.
4. Use `mlflow.search_runs` (ou a UI **Experiments**) para achar o melhor.
5. **Registre** o melhor modelo como `furnace_energy_regressor` no UC.

> 💬 **Genie Code:** *"Treine uma regressão linear com mlflow.autolog para prever `energy_kwh_ton`."*

**✅ Checkpoint:** Dois runs comparados; modelo vencedor registrado no UC.

**🎯 Exercício:** Treine um `RandomForestRegressor` via Genie Code. Bate o Gradient Boosting?

---

## Módulo 4 — Modelagem: classificação de defeitos com AutoML

**Contexto CBA:** antecipar defeitos reduz refugo e retrabalho — perda direta de margem.

**Passo a passo:**
1. Prepare a entrada removendo IDs (`inspection_id`, `furnace_id`).
2. Rode `automl.classify(..., primary_metric="f1", pos_label=1)` (F1 para classe desbalanceada).
3. Abra o **notebook glass-box** do melhor modelo (`summary.best_trial.notebook_path`) e leia o código.
4. **Registre** o classificador no UC e faça uma previsão de teste.

> 💬 **Genie Code:** *"Como rodar um experimento de classificação com a API do databricks.automl?"*

**✅ Checkpoint:** AutoML rodado, glass-box aberto, classificador registrado.

**🎯 Exercício:** No glass-box, ache a matriz de confusão e a importância das features. Depois,
monte o mesmo experimento para `is_failure` (manutenção preditiva).

---

## Módulo 5 — Avaliação & Governança: champion/challenger no UC

**Contexto CBA:** decidir qual modelo vai para produção precisa ser **baseado em dados** e auditável.

**Passo a passo:**
1. Liste as **versões** do modelo com `MlflowClient`.
2. Defina o alias **`@champion`** (versão em produção).
3. Registre um **`@challenger`** (modelo candidato).
4. **Compare** champion × challenger no mesmo teste (RMSE).
5. **Promova** o challenger se for melhor. Adicione **tags/descrição** e veja o **lineage** na UI.

> 💬 **Genie Code:** *"Use o MlflowClient para definir o alias `champion` na versão 1."*

**✅ Checkpoint:** Aliases definidos, comparação feita, regra de promoção aplicada.

**🎯 Exercício:** Faça champion/challenger para o classificador, usando **F1** como critério.

---

## Módulo 6 — Implantação: Model Serving + `ai_query`

**Contexto CBA:** um modelo só vale quando alguém usa. Analistas precisam consumir previsões sem Python.

**Passo a passo:**
1. Crie um **endpoint de serving** com **scale-to-zero** servindo o `@champion`.
2. Faça **inferência em lote** com `spark_udf` → tabela `energy_predictions`.
3. Consulte o endpoint via **REST** e via **`ai_query()`** no SQL.
4. Monte um **alerta** de fornos cuja energia real excede a prevista.

> 💬 **Genie Code:** *"Crie um endpoint de Model Serving com scale-to-zero servindo o @champion."*

**✅ Checkpoint:** Endpoint criado; lote e `ai_query` funcionando; alerta montado.

**🎯 Exercício:** Sirva o classificador e use `ai_query` para marcar inspeções de alto risco.
Lembre-se de **excluir o endpoint** ao final.

---

## Módulo 7 — Agente de RCA de Manutenção (Mosaic AI Agent Framework)

**Contexto CBA:** dar ao engenheiro um assistente que investiga sozinho a telemetria e a qualidade
de um forno e sugere ações.

**Comece pelo AI Playground:** escolha um Foundation Model, anexe funções UC como tools e teste
sem código. Depois formalize no notebook.

**Passo a passo:**
1. Instale as libs do Agent Framework.
2. Crie **funções UC** como ferramentas: telemetria, qualidade e taxa de falha por forno.
3. Monte o agente com `databricks-langchain` + Foundation Model + `create_react_agent`.
4. Teste perguntas em **português**.
5. (Opcional) Indexe **manuais de manutenção** com **Vector Search** e adicione o retrieval.
6. **Avalie** com `mlflow.evaluate(model_type="databricks-agent")` (LLM judges).
7. **Registre** e (opcional) **implante** o agente.

> 💬 **Genie Code:** *"Crie uma função SQL no UC que recebe um furnace_id e retorna as médias de
> telemetria desse forno."*

**✅ Checkpoint:** Agente respondendo em PT, avaliado com MLflow, registrado no UC.

**🎯 Exercício:** Adicione uma função que retorne a planta e o modelo do forno (join com dimensões)
e reproduza o agente no AI Playground.

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---|---|---|
| `Table or view not found` no schema `gold` | Tabelas em outro schema na sua sala | Ajuste a variável `GOLD` (o instrutor informa o nome) |
| `mlflow.register_model` falha com permissão | Registry apontando para o Workspace legado | Garanta `mlflow.set_registry_uri("databricks-uc")` |
| `databricks.automl` não importa | Cluster sem Runtime ML | Troque para um cluster **ML** |
| Endpoint de serving fica em `NOT_READY` por muito tempo | Provisionamento inicial | Aguarde 5–10 min; rode a célula de consulta de novo |
| `ai_query` retorna erro de endpoint | Endpoint ainda não `READY` | Espere o endpoint ficar pronto |
| Agente: `endpoint not found` no LLM | Foundation Model não disponível na workspace | Troque `LLM_ENDPOINT` por um FM listado em Serving → Foundation models |
| Vector Search falha | Sem VS endpoint na sala | Pule a seção opcional; o agente funciona só com funções UC |
| `/explain` ou `/fix` não aparecem | Assistant desabilitado | Peça ao instrutor para habilitar o Databricks Assistant |

---

## Próximos passos
- **Lakehouse Monitoring** sobre as previsões e as features (detectar *drift*).
- **Jobs / Workflows** para retreino agendado com a regra champion/challenger automatizada.
- **Databricks Asset Bundles (DAB)** para versionar e promover os notebooks entre ambientes.
- **Genie Spaces** para que o negócio converse com os dados/previsões em linguagem natural.
- Expandir o agente com mais ferramentas (custos, mercado LME) ligando custo e margem.
