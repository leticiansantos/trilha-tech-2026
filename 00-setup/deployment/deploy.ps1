# =============================================================================
# Trilha Tech 2026 | CBA — Deploy do ambiente das 3 trilhas (Windows/PowerShell)
# =============================================================================
# Provisiona o workspace de testes da CBA:
#   1. valida autenticação (Databricks CLI)
#   2. cria catálogo + schema raw + Volume landing
#   3. sobe os CSVs sintéticos para o Volume
#   4. sobe os notebooks das trilhas para /Workspace/Shared/cba-trilha-tech-2026/
#   5. deploya a API mock de mercado como Databricks App e patcha a URL no notebook 05
#   6. faz deploy do bundle (setup_load_gold.py + job)
#   7. roda o job que carrega a camada gold canônica
#
# Pré-requisitos:
#   - Databricks CLI v0.2x+:  winget install Databricks.DatabricksCLI
#     autenticado com:        databricks auth login --host <WORKSPACE_URL>
#   - Terraform v1.0+:        winget install Hashicorp.Terraform
#     (necessário para bundle deploy: evita download com chave PGP expirada)
#   - Python 3.8+:            winget install Python.Python.3
#   - Dados gerados:          cd ..\data-generation; python generate_synthetic_data.py
#
# Uso:
#   .\deploy.ps1 [PROFILE] [CATALOG] [CATALOG_LOCATION]
#   ex.:  .\deploy.ps1 cba cba_workshop_trilha_tech
#   ex.:  .\deploy.ps1 cba cba_workshop_trilha_tech "abfss://container@account.dfs.core.windows.net/cba"
# =============================================================================
param(
    [string]$Profile         = "DEFAULT",
    [string]$Catalog         = "cba_workshop_trilha_tech",
    [string]$CatalogLocation = ""
)

$ErrorActionPreference = "Stop"

$RawSchema   = "raw"
$Volume      = "landing"
$VolumePath  = "/Volumes/$Catalog/$RawSchema/$Volume"
$RepoRoot    = (Resolve-Path "$PSScriptRoot\..\.." ).Path
$DataDir     = "$RepoRoot\00-setup\data-generation\output"
$WsNotebooks = "/Workspace/Shared/cba-trilha-tech-2026"
$AppName     = "cba-market-api"
$AppWsPath   = "$WsNotebooks/market-api-app"
$Dbx         = "databricks --profile $Profile"

$locationMsg = if ($CatalogLocation) { " | Location: $CatalogLocation" } else { "" }
Write-Host "==> Perfil: $Profile | Catalogo: $Catalog$locationMsg"

# ---------------------------------------------------------------------------
# 1. valida auth
# ---------------------------------------------------------------------------
Write-Host "==> Validando autenticacao..."
try {
    Invoke-Expression "$Dbx current-user me" | Out-Null
} catch {
    Write-Error "ERRO: CLI nao autenticado. Rode: databricks auth login --host <URL>"
    exit 1
}

# ---------------------------------------------------------------------------
# 2. catalogo, schema, volume
# ---------------------------------------------------------------------------
Write-Host "==> Criando catalogo/schema/volume (se necessario)..."
Invoke-Expression "$Dbx catalogs create `"$Catalog`"" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "   catalogo ja existe" }

Invoke-Expression "$Dbx schemas create `"$RawSchema`" `"$Catalog`"" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "   schema raw ja existe" }

Invoke-Expression "$Dbx volumes create `"$Catalog`" `"$RawSchema`" `"$Volume`" MANAGED" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "   volume ja existe" }

# ---------------------------------------------------------------------------
# 3. upload dos dados
# ---------------------------------------------------------------------------
if (-not (Test-Path $DataDir)) {
    Write-Error "ERRO: $DataDir nao existe. Gere os dados: cd ..\data-generation; python generate_synthetic_data.py"
    exit 1
}

Write-Host "==> Subindo CSVs/Parquet para $VolumePath ..."
Get-ChildItem -Path $DataDir -Include "*.csv","*.parquet" -File | ForEach-Object {
    Write-Host "   -> $($_.Name)"
    Invoke-Expression "$Dbx fs cp `"$($_.FullName)`" `"dbfs:$VolumePath/$($_.Name)`" --overwrite"
}

# amostra para o modulo "subir CSV" da Trilha 1
$SampleFile = "$DataDir\sample\furnace_telemetry_sample.csv"
if (Test-Path $SampleFile) {
    Invoke-Expression "$Dbx fs mkdir `"dbfs:$VolumePath/sample`"" 2>$null
    Invoke-Expression "$Dbx fs cp `"$SampleFile`" `"dbfs:$VolumePath/sample/furnace_telemetry_sample.csv`" --overwrite"
}

# ---------------------------------------------------------------------------
# 4. upload dos notebooks das trilhas
# ---------------------------------------------------------------------------
Write-Host "==> Subindo notebooks das trilhas para $WsNotebooks ..."
foreach ($trilha in @("01-engenharia","02-mlops","03-insights")) {
    $NbDir = "$RepoRoot\$trilha\notebooks"
    if (-not (Test-Path $NbDir)) { continue }
    Write-Host "   -> $trilha"
    Invoke-Expression "$Dbx workspace import-dir `"$NbDir`" `"$WsNotebooks/$trilha/notebooks`" --overwrite"
}

# ---------------------------------------------------------------------------
# 5. deploy da API mock como Databricks App
# ---------------------------------------------------------------------------
Write-Host "==> Deploy da API mock de mercado como Databricks App..."
Invoke-Expression "$Dbx workspace import-dir `"$RepoRoot\00-setup\market-api-app`" `"$AppWsPath`" --overwrite"

$appExists = $false
try {
    Invoke-Expression "$Dbx apps get `"$AppName`"" | Out-Null
    $appExists = $true
} catch { }

if (-not $appExists) {
    Write-Host "   -> criando app $AppName..."
    Invoke-Expression "$Dbx apps create `"$AppName`""
} else {
    Write-Host "   -> app $AppName ja existe"
}

Invoke-Expression "$Dbx apps deploy `"$AppName`" --source-code-path `"$AppWsPath`""

$AppUrl = ""
try {
    $appJson = Invoke-Expression "$Dbx apps get `"$AppName`" --output json"
    $AppUrl  = ($appJson | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('url',''))").Trim()
} catch { }

Write-Host "   App URL: $(if ($AppUrl) { $AppUrl } else { '(aguardando start — consulte a UI em Apps)' })"

# ---------------------------------------------------------------------------
# 5b. patch no notebook 05 com a URL real do app e re-upload
# ---------------------------------------------------------------------------
$Nb05Src = "$RepoRoot\01-engenharia\notebooks\05_market_api_ingest.py"
$Nb05Ws  = "$WsNotebooks/01-engenharia/notebooks/05_market_api_ingest"
if ($AppUrl -and (Test-Path $Nb05Src)) {
    Write-Host "==> Atualizando notebook 05 com URL do app: $AppUrl"
    $Nb05Tmp = [System.IO.Path]::GetTempFileName()
    (Get-Content $Nb05Src -Raw) -replace [regex]::Escape("http://localhost:8000"), $AppUrl |
        Set-Content $Nb05Tmp -Encoding UTF8
    Invoke-Expression "$Dbx workspace import `"$Nb05Ws`" --file `"$Nb05Tmp`" --format SOURCE --language PYTHON --overwrite"
    Remove-Item $Nb05Tmp -Force
    Write-Host "   -> notebook 05 re-uploaded com URL correta"
} else {
    Write-Host "   -> URL do app nao disponivel ainda; notebook 05 usa widget api_base (padrao: localhost:8000)"
}

# ---------------------------------------------------------------------------
# 6. deploy do bundle
# ---------------------------------------------------------------------------
Write-Host "==> Deploy do bundle (setup_load_gold + job)..."
$TfBin = (Get-Command terraform -ErrorAction Stop).Source
$TfVer = (terraform version -json | python -c "import sys,json; print(json.load(sys.stdin)['terraform_version'])").Trim()

Push-Location $PSScriptRoot
try {
    $env:DATABRICKS_TF_EXEC_PATH = $TfBin
    $env:DATABRICKS_TF_VERSION   = $TfVer
    Invoke-Expression "$Dbx bundle validate -t dev"
    Invoke-Expression "$Dbx bundle deploy -t dev"
} finally {
    Remove-Item Env:DATABRICKS_TF_EXEC_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:DATABRICKS_TF_VERSION   -ErrorAction SilentlyContinue
    Pop-Location
}

# ---------------------------------------------------------------------------
# 7. roda a carga da gold
# ---------------------------------------------------------------------------
Write-Host "==> Carregando a camada GOLD canonica..."
$BundleRunArgs = "-t dev"
if ($CatalogLocation) {
    $BundleRunArgs += " --var=catalog_location=$CatalogLocation"
}

Push-Location $PSScriptRoot
try {
    Invoke-Expression "$Dbx bundle run setup_gold $BundleRunArgs"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "==> Concluido. Ambiente pronto em '$Catalog'."
Write-Host "    gold: $Catalog.gold.*  |  raw volume: $VolumePath"
Write-Host "    notebooks: $WsNotebooks/"
Write-Host "    market API: $(if ($AppUrl) { $AppUrl } else { "databricks apps get $AppName (verifique a URL na UI)" })"
