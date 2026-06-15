#!/usr/bin/env bash
# =============================================================================
# Trilha Tech 2026 | CBA — Deploy do ambiente das 3 trilhas
# =============================================================================
# Provisiona o workspace de testes da CBA:
#   1. valida autenticação (Databricks CLI)
#   2. cria catálogo + schema raw + Volume landing
#   3. sobe os CSVs sintéticos para o Volume
#   4. sobe os notebooks das trilhas para /Workspace/Shared/cba-trilha-tech-2026/
#   5. faz deploy do bundle (setup_load_gold.py + job)
#   6. roda o job que carrega a camada gold canônica
#
# Pré-requisitos:
#   - Databricks CLI v0.2x+:  brew install databricks/tap/databricks
#     autenticado com:        databricks auth login --host <WORKSPACE_URL>
#   - Terraform v1.0+:        brew install terraform
#     (necessário para bundle deploy: CLI usa DATABRICKS_TF_EXEC_PATH para evitar download com chave PGP expirada)
#   - Dados gerados:          (cd ../data-generation && python generate_synthetic_data.py)
#
# Uso:
#   ./deploy.sh [DATABRICKS_PROFILE] [CATALOG] [CATALOG_LOCATION]
#   ex.:  ./deploy.sh cba cba_trilha_tech
#   ex. (sem storage root):  ./deploy.sh cba cba_trilha_tech "abfss://container@account.dfs.core.windows.net/cba"
# =============================================================================
set -euo pipefail

PROFILE="${1:-DEFAULT}"
CATALOG="${2:-cba_trilha_tech}"
CATALOG_LOCATION="${3:-}"
RAW_SCHEMA="raw"
VOLUME="landing"
VOLUME_PATH="/Volumes/${CATALOG}/${RAW_SCHEMA}/${VOLUME}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA_DIR="${REPO_ROOT}/00-setup/data-generation/output"
WS_NOTEBOOKS="/Workspace/Shared/cba-trilha-tech-2026"
DBX="databricks --profile ${PROFILE}"

echo "==> Perfil: ${PROFILE} | Catálogo: ${CATALOG}${CATALOG_LOCATION:+ | Location: ${CATALOG_LOCATION}}"

# 1. valida auth
echo "==> Validando autenticação..."
${DBX} current-user me >/dev/null || { echo "ERRO: CLI não autenticado. Rode: databricks auth login --host <URL>"; exit 1; }

# 2. catálogo, schema, volume
echo "==> Criando catálogo/schema/volume (se necessário)..."
${DBX} catalogs create "${CATALOG}" 2>/dev/null || echo "   catálogo já existe"
${DBX} schemas create "${RAW_SCHEMA}" "${CATALOG}" 2>/dev/null || echo "   schema raw já existe"
${DBX} volumes create "${CATALOG}" "${RAW_SCHEMA}" "${VOLUME}" MANAGED 2>/dev/null || echo "   volume já existe"

# 3. upload dos dados
if [ ! -d "${DATA_DIR}" ]; then
  echo "ERRO: ${DATA_DIR} não existe. Gere os dados: (cd ../data-generation && python generate_synthetic_data.py)"; exit 1
fi
echo "==> Subindo CSVs/Parquet para ${VOLUME_PATH} ..."
for f in "${DATA_DIR}"/*.csv "${DATA_DIR}"/*.parquet; do
  [ -e "$f" ] || continue
  echo "   -> $(basename "$f")"
  ${DBX} fs cp "$f" "dbfs:${VOLUME_PATH}/$(basename "$f")" --overwrite
done
# amostra para o módulo "subir CSV" da Trilha 1
if [ -f "${DATA_DIR}/sample/furnace_telemetry_sample.csv" ]; then
  ${DBX} fs mkdir "dbfs:${VOLUME_PATH}/sample" 2>/dev/null || true
  ${DBX} fs cp "${DATA_DIR}/sample/furnace_telemetry_sample.csv" \
      "dbfs:${VOLUME_PATH}/sample/furnace_telemetry_sample.csv" --overwrite
fi

# 4. upload dos notebooks das trilhas para o workspace compartilhado
echo "==> Subindo notebooks das trilhas para ${WS_NOTEBOOKS} ..."
for trilha in 01-engenharia 02-mlops 03-insights; do
  nb_dir="${REPO_ROOT}/${trilha}/notebooks"
  [ -d "${nb_dir}" ] || continue
  echo "   -> ${trilha}"
  ${DBX} workspace import-dir "${nb_dir}" "${WS_NOTEBOOKS}/${trilha}/notebooks" \
    --overwrite 2>/dev/null || \
  ${DBX} workspace import-dir "${nb_dir}" "${WS_NOTEBOOKS}/${trilha}/notebooks" --overwrite
done

# 6. deploy do bundle
echo "==> Deploy do bundle (setup_load_gold + job)..."
TF_BIN="$(which terraform)"
TF_VER="$(terraform version -json | python3 -c 'import sys,json; print(json.load(sys.stdin)["terraform_version"])')"
( cd "$(dirname "$0")" && \
  DATABRICKS_TF_EXEC_PATH="${TF_BIN}" DATABRICKS_TF_VERSION="${TF_VER}" ${DBX} bundle validate -t dev && \
  DATABRICKS_TF_EXEC_PATH="${TF_BIN}" DATABRICKS_TF_VERSION="${TF_VER}" ${DBX} bundle deploy -t dev )

# 7. roda a carga da gold
echo "==> Carregando a camada GOLD canônica..."
BUNDLE_RUN_ARGS="-t dev"
if [ -n "${CATALOG_LOCATION}" ]; then
  BUNDLE_RUN_ARGS="${BUNDLE_RUN_ARGS} --var=catalog_location=${CATALOG_LOCATION}"
fi
( cd "$(dirname "$0")" && ${DBX} bundle run setup_gold ${BUNDLE_RUN_ARGS} )

echo "==> Concluído. Ambiente pronto em '${CATALOG}'."
echo "    gold: ${CATALOG}.gold.*  |  raw volume: ${VOLUME_PATH}"
echo "    notebooks: ${WS_NOTEBOOKS}/"
