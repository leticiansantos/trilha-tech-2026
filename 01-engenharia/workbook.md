# Apostila do Aluno — Trilha Tech 2026
## Workshop Hands-on: Engenharia na prática (CBA)

> **Narrativa do dia: "Do Forno ao Mercado" 🏭 → 💰**
> A margem da CBA nasce de dois lados: quanto **custa produzir** o alumínio (energia dos fornos,
> medida pela telemetria do sistema **Gorila**) e por **quanto o mercado paga** (preço do alumínio na
> LME × câmbio USD/BRL). Nesta trilha você vai **ingerir** os dois mundos, **integrá-los por IDs** e
> **transformá-los** numa arquitetura medalhão (bronze → prata → ouro) até chegar à margem.

---

## 🎯 Objetivos
Ao final, você será capaz de:
1. Subir e consumir um CSV no Databricks, do zero.
2. Ingerir dados em volume com **Auto Loader** (incremental, com checkpoint).
3. Construir a **arquitetura medalhão** (bronze → prata → ouro) com Delta (ACID + time travel).
4. **Conectar bases por um ID** (joins) e entender chaves PK/FK.
5. **Consumir uma API externa** e integrar dados de mercado.
6. Recriar o fluxo de forma **declarativa** com **Lakeflow Declarative Pipelines (DLT)**.
7. **Orquestrar** tudo num **Job/Workflow** agendado.
8. Usar o **Databricks Assistant / Genie Code** como copiloto em cada passo.

## 🤖 Como o Genie Code nivela a turma
A turma é diversa: tem quem programa pouco e quem já manda bem (vindo de Power BI). Para **nivelar**,
o **Databricks Assistant ("Genie Code" / vibe code)** é o fio condutor do dia:

- **Você descreve em português** o que quer; o Assistant **gera o código**.
- Você **lê, ajusta e entende** — o foco é compreender, não decorar sintaxe.
- Comandos que vamos usar o tempo todo:
  - **`/explain`** — selecione uma célula e peça para o Assistant explicar linha a linha.
  - **`/fix`** — quando aparecer erro vermelho, ele sugere a correção.
  - **`/doc`** — gera comentários/documentação.
- Em cada módulo há um quadro **💬 Genie Code** com o **texto exato** para digitar.

> 💡 **Regra de ouro:** se travou na sintaxe, **pergunte ao Assistant**. Ninguém é cobrado por decorar.

## ✅ Pré-requisitos
- Acesso ao workspace Databricks da turma e ao catálogo `cba_trilha_tech`.
- Permissão de **USE CATALOG** + criação de schema pessoal (o instrutor já provisiona).
- Os notebooks `00`–`07` importados na sua pasta de usuário.
- Noções básicas de tabela/linha/coluna (Excel ou Power BI já bastam).

---

## 🗓️ Agenda (~4h, meio período)

| Bloco | Módulo | Tempo |
|---|---|---|
| Abertura | Narrativa, ambiente e Genie Code (nb `00`) | 20 min |
| 1 | Subir e consumir um CSV (`01`) | 30 min |
| 2 | Auto Loader → Bronze (`02`) | 30 min |
| ☕ | **Intervalo** | 10 min |
| 3 | Medalhão: Prata → Ouro + Time Travel (`03`) | 40 min |
| 4 | Conectar bases por ID (`04`) | 30 min |
| 5 | Ingestão via API + Margem (`05`) | 35 min |
| ☕ | **Intervalo** | 10 min |
| 6 | Lakeflow Declarative Pipelines / DLT (`06`) | 35 min |
| 7 | Orquestração: Job/Workflow (`07`) | 25 min |
| Fecho | Troubleshooting, próximos passos, Q&A | 15 min |

---

## Módulo 0 · Setup do ambiente
**Contexto:** preparar o "chão de fábrica" digital antes de produzir.

**Passo a passo**
1. Abra `00_setup`.
2. Rode a **célula de configuração** (descobre seu usuário e cria `ws_<voce>`).
3. Crie catálogo, schemas e o Volume `raw.landing`.
4. Liste os arquivos do Volume e confirme que estão lá.

**💬 Genie Code:** *"Crie o catálogo cba_trilha_tech e os schemas raw e o meu schema pessoal a partir do
usuário atual, se não existirem, e selecione o catálogo."*

**✅ Você deve ver:** seu schema `ws_...` criado e as 4 plantas da CBA listadas.

---

## Módulo 1 · Subir e consumir um CSV
**Contexto CBA:** a sala de fornos exporta a telemetria do Gorila em CSV. Vamos pegar uma amostra de
10 mil leituras e transformá-la em tabela consultável.

**Passo a passo**
1. Olhe as primeiras linhas do CSV **cru** (texto).
2. Entenda como subir um CSV pela UI (Catalog → Upload to this volume).
3. Leia com `spark.read.csv(..., header=True, inferSchema=True)`.
4. Inspecione o schema (`printSchema`).
5. Salve como tabela Delta (`saveAsTable`).
6. Consulte em SQL (`%sql`).

**💬 Genie Code:** *"Leia o CSV em /Volumes/cba_trilha_tech/raw/landing/sample/furnace_telemetry_sample.csv
com cabeçalho e inferência de schema e mostre as 10 primeiras linhas."*

**Exercícios**
- Conte as leituras com `is_failure = 1`.
- Calcule a vibração média e quantos nulos há em `vibration_mm_s`.

**✅ Você deve ver:** a tabela `telemetry_csv_demo` no seu schema e o resultado do `SELECT`.

---

## Módulo 2 · Auto Loader → Bronze
**Contexto CBA:** o Gorila não manda um arquivo só — manda continuamente. Auto Loader processa **só o
que é novo**.

**Passo a passo**
1. Aponte o Auto Loader para a telemetria completa.
2. Configure `cloudFiles.format`, `schemaLocation`, evolução de schema.
3. Grave com `checkpointLocation` e `trigger(availableNow=True)`.
4. Confira a contagem (~864 mil) e rode de novo: nada é reprocessado.

**💬 Genie Code:** *"Use o Auto Loader (cloudFiles) para ler em streaming os CSVs de telemetria com
cabeçalho, salvando a localização do schema, e adicione o nome do arquivo de origem e o horário de ingestão."*

**Exercício:** ingerir `furnace_inspections.csv` numa bronze própria (checkpoint separado!).

**✅ Você deve ver:** ~864 mil linhas em `telemetry_bronze`; 2ª execução não muda a contagem.

---

## Módulo 3 · Medalhão: Prata → Ouro
**Contexto CBA:** bronze é "tudo cru"; o negócio precisa de dado **limpo** (prata) e de **indicadores
diários** (ouro): energia, taxa de falha, OEE.

**Passo a passo**
1. **Prata:** tipar colunas, **imputar nulos de vibração com a mediana por forno** (com flag), filtrar
   temperaturas absurdas, **deduplicar** por (`furnace_id`, `ts`).
2. **Ouro:** agregar por forno/dia (energia média, temp média, efeitos anódicos, taxa de falha, OEE).
3. **Time travel:** `DESCRIBE HISTORY`, `VERSION AS OF`, `RESTORE`.

**💬 Genie Code:** *"A partir de telemetry_bronze, converta tipos, remova duplicatas por furnace_id e ts e
preencha os nulos de vibration_mm_s com a mediana por forno."*

**Exercícios**
- Crie uma ouro **por planta/dia** (adianta o módulo 4).
- Qual forno tem a pior taxa de falha?

**✅ Você deve ver:** prata sem nulos de vibração; ouro com OEE; ≥ 2 versões no histórico.

> **OEE simplificado:** usamos `(1 − taxa de falha) × 100` como proxy de disponibilidade. É didático, não
> a definição oficial (que é Disponibilidade × Performance × Qualidade).

---

## Módulo 4 · Conectar bases por um ID
**Contexto CBA:** a telemetria sabe o `furnace_id`, mas não a planta nem a liga. Os **joins** conectam.

**Passo a passo**
1. Carregue as 4 dimensões como tabelas.
2. Entenda PK (id único da dimensão) e FK (id que aponta para a dimensão).
3. Junte ouro × `dim_fornos` × `dim_plantas` (por `furnace_id` e `plant_id`).
4. Compare `inner` vs `left` (cardinalidade, órfãos).
5. Responda: energia e falha **por planta**.

**💬 Genie Code:** *"Junte telemetry_gold_forno_dia com dim_fornos pelo furnace_id e depois com
dim_plantas pelo plant_id, trazendo nome da planta, estado, modelo e capacidade."*

**Exercícios**
- Junte `furnace_inspections` com `dim_ligas`/`dim_produtos`: qual liga tem mais defeito?
- Faça um join com chave errada de propósito e use `/fix`.

**✅ Você deve ver:** telemetria com `plant_name`; `inner` = `left` (sem órfãos); ranking por planta.

> ⚠️ **Pegadinha:** se a chave repete no lado direito, o join **multiplica linhas**. Dimensão = PK única.

---

## Módulo 5 · Ingestão via API + Margem
**Contexto CBA:** o Gorila vai expor uma **API**, e o preço do alumínio/câmbio também vêm de **APIs**
(LME/B3 e Banco Central). Vamos consumir uma API mock e calcular a **margem preliminar**.

**Passo a passo**
1. Configure o widget `api_base` com a URL da API (instrutor passa).
2. `requests.get` em `/aluminum/lme` e `/fx/usdbrl`; `raise_for_status()`.
3. Normalize o JSON (`data`) em DataFrame; salve Delta.
4. Junte `fact_production` × LME × câmbio pela **data**; calcule `preco_brl_ton` e `margem`.

**💬 Genie Code:** *"Faça GET em {api_base}/aluminum/lme com start e end, verifique o status e crie um
DataFrame com date e lme_price_usd_ton."*

**Exercícios**
- Traga o período inteiro (sem filtro de data).
- Em que dia a margem foi mínima? O que o câmbio fez?

**✅ Você deve ver:** JSON 200; `market_*_bronze`; `gold_margem_preliminar` com preço e margem em BRL.

> **Fonte real:** câmbio = PTAX do Banco Central (olinda.bcb.gov.br); preço = B3/LME ou provedor licenciado.
> A margem aqui é **preliminar** (só custo de energia).

---

## Módulo 6 · Lakeflow Declarative Pipelines (DLT)
**Contexto CBA:** o mesmo medalhão, agora **declarativo** — você descreve as tabelas, o Lakeflow
orquestra, versiona e mede **qualidade**.

**Passo a passo**
1. Entenda que este notebook é **fonte de pipeline** (não roda célula a célula).
2. `@dlt.table` para bronze (streaming + Auto Loader), prata (limpeza + `dlt.expect`), ouro (MV agregada).
3. Crie o pipeline na UI (Jobs & Pipelines → ETL pipeline), aponte para o notebook, destino = seu schema,
   parâmetro `landing_path`.
4. **Start** e acompanhe o grafo + aba **Data quality**.

**💬 Genie Code:** *"Crie uma tabela DLT silver lendo a bronze, com expectativas: temperatura entre 800 e
1100 (descartar), furnace_id não nulo (falhar) e vibração não nula (apenas registrar)."*

**Exercício:** adicione tabela DLT para inspeções (taxa de defeito por liga); quebre e conserte uma expectativa.

**✅ Você deve ver:** grafo bronze→silver→gold verde; tabelas `*_dlt`; métricas de qualidade.

---

## Módulo 7 · Orquestração: Job/Workflow
**Contexto CBA:** colocar o fluxo para rodar **sozinho** toda madrugada, na ordem certa, com aviso de falha.

**Passo a passo**
1. Crie um **Job** com 3 tarefas: `preparar_dimensoes` + `ingest_mercado` (paralelas) → `pipeline_medalhao`.
2. Configure **dependências**, **schedule** diário (03:00) e **notificação** de falha.
3. **Run now** e acompanhe o grafo.
4. Veja o equivalente em **JSON** e em **YAML (DABs)**.

**💬 Genie Code:** *"Gere o JSON de um Job com duas tarefas de notebook em paralelo e uma de pipeline que
depende das duas, com schedule diário às 3h e notificação por e-mail."*

**Exercício:** adicione tarefa de validação no fim + retry na tarefa da API.

**✅ Você deve ver:** Job com grafo de dependências, execução verde, agendamento e notificação ativos.

---

## 🆘 Troubleshooting
| Sintoma | Causa provável | Solução |
|---|---|---|
| `Table or view not found` | rodou módulo fora de ordem / schema errado | rode a célula de config; confirme `USE SCHEMA ws_...` |
| Auto Loader não lê nada | caminho errado ou checkpoint reaproveitado | confira `SOURCE_PATH`; use checkpoint/schemaLocation **únicos** por fonte |
| `PERMISSION_DENIED` no catálogo | falta grant | avise o instrutor (precisa de USE CATALOG + CREATE SCHEMA) |
| Join "explodiu" (linhas demais) | chave duplicada na dimensão | verifique PK única; faça `dropDuplicates` na dimensão |
| API `ConnectionError`/timeout | URL errada ou API fora do ar | confira o widget `api_base`; teste `/health`; use retry |
| Pipeline DLT falha em `expect_or_fail` | regra crítica violada | é o comportamento esperado; ajuste a regra ou o dado |
| Nulos persistem após imputação | forno só com nulos (sem mediana) | use mediana global como fallback (peça ao Assistant) |
| Erro de sintaxe qualquer | — | selecione a célula → **`/fix`** no Assistant |

## 🚀 Próximos passos
- **Trilha MLOps:** usar `is_failure`/`is_defect` para **manutenção preditiva** e treinar/servir modelos.
- **Trilha Insights:** dashboards de margem e **Genie Spaces** (perguntas em linguagem natural).
- Aprofundar: **Unity Catalog** (governança/lineage), **Liquid Clustering**, **Lakeflow Connect**
  (conectores gerenciados), **DABs** no Git para CI/CD.
- Documentação: `docs.databricks.com` → Auto Loader, Lakeflow Declarative Pipelines, Jobs, Delta.

> Lembre: o **Assistant** continua disponível no seu dia a dia. Descreva, gere, **entenda**, repita. 🤖
