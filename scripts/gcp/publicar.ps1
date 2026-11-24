param(
  [string]$Projeto = "projetos-pessoais-vini",
  [string]$Regiao = "southamerica-east1",
  [string]$Configuracao = "nota-a-nota",
  [string]$NumeroDoProjeto,
  [ValidateSet("api", "web")]
  [string[]]$Servicos = @("api", "web"),
  [ValidateSet("cloudbuild", "docker")]
  [string]$Construtor = "cloudbuild",
  [string]$Versao = (Get-Date -Format "yyyyMMdd-HHmmss"),
  [string]$Remetente,
  [ValidateSet("anthropic", "desligada")]
  [string]$PesquisaWeb = "anthropic"
)

. (Join-Path $PSScriptRoot "comum.ps1") -Projeto $Projeto -Regiao $Regiao -Configuracao $Configuracao

$raiz = (Resolve-Path (Join-Path $PSScriptRoot (Join-Path ".." ".."))).Path
if (-not $NumeroDoProjeto) { $NumeroDoProjeto = Get-Gcloud projects describe $Projeto --format="value(projectNumber)" }
$urlWeb = "https://capi-web-$NumeroDoProjeto.$Regiao.run.app"
$urlApi = "https://capi-api-$NumeroDoProjeto.$Regiao.run.app"
$registro = "$Regiao-docker.pkg.dev/$Projeto/$Repositorio"

function Get-Segredos([hashtable]$Mapa) {
  $presentes = foreach ($variavel in $Mapa.Keys) {
    if (Test-Segredo $Mapa[$variavel]) { "$variavel=$($Mapa[$variavel]):latest" }
  }
  $presentes -join ","
}

function Publish-Imagem([string]$Pasta, [string]$Imagem) {
  $caminho = Join-Path $raiz $Pasta
  Write-Host "Build de $Imagem"
  if ($Construtor -eq "docker") {
    $ErrorActionPreference = "Continue"
    & docker build --platform=linux/amd64 --tag=$Imagem $caminho
    if ($LASTEXITCODE -ne 0) { throw "docker build falhou" }
    & docker push $Imagem
    if ($LASTEXITCODE -ne 0) { throw "docker push falhou" }
  } else {
    Invoke-Gcloud builds submit $caminho --tag=$Imagem --region=$Regiao
  }
}

if ($Servicos -contains "api") {
  $imagem = "$registro/api:$Versao"
  Publish-Imagem "backend" $imagem

  Write-Host "Migrations"
  Invoke-Gcloud run jobs deploy capi-migrar `
    --image=$imagem `
    --region=$Regiao `
    --service-account=$ContaDeServico `
    --set-cloudsql-instances=$Conexao `
    --set-secrets="DATABASE_URL=database-url:latest" `
    --command=alembic `
    "--args=upgrade,head" `
    --max-retries=0 `
    --task-timeout=10m `
    --execute-now `
    --wait

  Write-Host "Deploy da API"
  $segredos = Get-Segredos @{
    DATABASE_URL      = "database-url"
    ANTHROPIC_API_KEY = "anthropic-api-key"
    VOYAGE_API_KEY    = "voyage-api-key"
  }
  Invoke-Gcloud run deploy capi-api `
    --image=$imagem `
    --region=$Regiao `
    --service-account=$ContaDeServico `
    --add-cloudsql-instances=$Conexao `
    --update-secrets=$segredos `
    --update-env-vars="AUTH_JWKS_URL=$urlWeb/api/auth/jwks,AUTH_ISSUER=$urlWeb,AUTH_AUDIENCE=$Audiencia,PESQUISA_WEB=$PesquisaWeb" `
    --allow-unauthenticated `
    --cpu=1 `
    --memory=512Mi `
    --min-instances=0 `
    --max-instances=2 `
    --concurrency=40
}

if ($Servicos -contains "web") {
  $imagem = "$registro/web:$Versao"
  Publish-Imagem "frontend" $imagem

  Write-Host "Deploy do front"
  $mapa = @{
    BETTER_AUTH_SECRET = "better-auth-secret"
    DATABASE_URL       = "database-url"
    SMTP_URL           = "smtp-url"
  }
  if ((Test-Segredo "google-client-id") -and (Test-Segredo "google-client-secret")) {
    $mapa.GOOGLE_CLIENT_ID = "google-client-id"
    $mapa.GOOGLE_CLIENT_SECRET = "google-client-secret"
  }
  $segredos = Get-Segredos $mapa
  $variaveis = "BETTER_AUTH_URL=$urlWeb,NOTA_API_URL=$urlApi,AUTH_AUDIENCE=$Audiencia,AUTH_TRUSTED_PROXIES=169.254.0.0/16"
  if ($Remetente) { $variaveis = "^|^$($variaveis.Replace(',', '|'))|EMAIL_REMETENTE=$Remetente" }
  Invoke-Gcloud run deploy capi-web `
    --image=$imagem `
    --region=$Regiao `
    --service-account=$ContaDeServico `
    --add-cloudsql-instances=$Conexao `
    --update-secrets=$segredos `
    --update-env-vars=$variaveis `
    --allow-unauthenticated `
    --cpu=1 `
    --memory=512Mi `
    --min-instances=0 `
    --max-instances=2 `
    --concurrency=40
}

if ($env:GITHUB_OUTPUT) { Add-Content -Path $env:GITHUB_OUTPUT -Value "url=$urlWeb" }
Write-Host ""
Write-Host "Front: $urlWeb"
Write-Host "API e MCP: $urlApi"
