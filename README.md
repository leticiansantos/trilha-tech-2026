# Trilha Tech 2026 | CBA — Workshops Hands-on de Databricks

Material hands-on dos três workshops de Databricks da **CBA** (Companhia Brasileira de Alumínio).
Tudo em português, com dados sintéticos de contexto de alumínio e uma narrativa única ponta-a-ponta.

## Narrativa — "Do Forno ao Mercado"

Custo de produção (telemetria das salas-fornos, sistema "Gorila") × preço de mercado do alumínio
(LME + dólar) → **margem**. A mesma história conecta as três trilhas.

| Pasta | Workshop | Perfil | O que você faz |
|---|---|---|---|
| [`01-engenharia/`](01-engenharia/) | Engenharia na prática | Engenheiro de Dados | Ingerir, integrar e transformar (medalhão bronze→silver→gold) |
| [`02-mlops/`](02-mlops/) | MLOps na prática | Ciência de Dados, MLOps e Agentes | Prever falha/eficiência do forno + criar um agente de RCA |
| [`03-insights/`](03-insights/) | Geração de Insights | Analista de Dados | Dashboards "farol" + AI/BI Genie sobre produção, custo e margem |

Cada trilha é de **meio período (~4h)**. Em todos os módulos usamos o **Databricks Assistant /
Genie Code ("vibe code")** para gerar e entender o código — descreva em português, revise e rode.

## Como começar

### 1. Trazer este repositório para o workspace (recomendado: Git Folders)
No Databricks: **Workspace → Repos / Git folders → Add → Clone** com a URL deste repositório.
Assim os notebooks já aparecem no workspace, prontos para rodar.

### 2. Preparar o ambiente (uma vez, antes dos workshops)
Siga o [`00-setup/`](00-setup/): gerar os dados sintéticos e provisionar o catálogo
`cba_workshop_trilha_tech` (camada `gold` + Volume `raw.landing`).

### 3. Conduzir cada trilha
Abra a pasta da trilha, leia o `workbook.md` (apostila do aluno) e siga os notebooks na ordem numérica.

## Pré-requisitos
- Workspace Databricks com Unity Catalog, SQL Warehouse (serverless) e Databricks Assistant habilitado.
- Trilha 2 (MLOps): cluster com Runtime ML, Model Serving e um Foundation Model disponível.
- Trilha 3 (Insights): AI/BI Dashboards e Genie habilitados.

## Estrutura

```
00-setup/         # gerar dados (data-generation) + provisionar ambiente (deployment)
01-engenharia/    # 8 notebooks + workbook
02-mlops/         # 7 notebooks + workbook
03-insights/      # 5 notebooks/guias + workbook
```

> Dados 100% sintéticos e determinísticos (seed fixa). Identificadores de código em inglês;
> conteúdo didático em português.
