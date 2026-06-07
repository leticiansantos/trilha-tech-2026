#!/usr/bin/env bash
# =============================================================================
# Trilha Tech 2026 | CBA — Deploy do ambiente das 3 trilhas
# =============================================================================
# Provisiona o workspace de testes da CBA:
#   1. valida autenticação (Databricks CLI)
#   2. cria catálogo + schema raw + Volume landing
#   3. sobe os CSVs sintéticos para o Volume
#   4. faz deploy do bundle (notebooks + job)
#   5. roda o job que carrega a camada gold canônica
#
# Pré-requisitos:
#   - Databricks CLI v0.2x+ autenticado:  databricks auth login --host <WORKSPACE_URL>
#   - Dados gerados:  (cd ../data-generation && python generate_synthetic_data.py)
#
# Uso:
#   ./deploy.sh [DATABRICKS_PROFILE] [CATALOG]
#   ex.:  ./deploy.sh cba cba_trilha_tech
# =============================================================================
set -euo pipefail

PROFILE="${1:-DEFAULT}"
CATALOG="${2:-cba_trilha_tech}"
RAW_SCHEMA="raw"
VOLUME="landing"
VOLUME_PATH="/Volumes/${CATALOG}/${RAW_SCHEMA}/${VOLUME}"
DATA_DIR="$(cd "$(dirname "$0")/../data-generation/output" && pwd)"
DBX="databricks --profile ${PROFILE}"

echo "==> Perfil: ${PROFILE} | Catálogo: ${CATALOG}"

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
  ${DBX} fs cp "${DATA_DIR}/sample/furnace_telemetry_sample.csv" \
      "dbfs:${VOLUME_PATH}/sample/furnace_telemetry_sample.csv" --overwrite
fi

# 4. deploy do bundle
echo "==> Deploy do bundle (notebooks + job)..."
( cd "$(dirname "$0")" && ${DBX} bundle validate -t dev && ${DBX} bundle deploy -t dev )

# 5. roda a carga da gold
echo "==> Carregando a camada GOLD canônica..."
( cd "$(dirname "$0")" && ${DBX} bundle run setup_gold -t dev )

echo "==> Concluído. Ambiente pronto em '${CATALOG}'."
echo "    gold: ${CATALOG}.gold.*  |  raw volume: ${VOLUME_PATH}"
