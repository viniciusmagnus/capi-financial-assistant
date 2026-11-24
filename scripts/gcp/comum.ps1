param(
  [string]$Projeto = "projetos-pessoais-vini",
  [string]$Regiao = "southamerica-east1",
  [string]$Configuracao = "nota-a-nota"
)

$ErrorActionPreference = "Stop"
if ($Configuracao) { $env:CLOUDSDK_ACTIVE_CONFIG_NAME = $Configuracao }
$env:CLOUDSDK_CORE_PROJECT = $Projeto
$env:CLOUDSDK_CORE_DISABLE_PROMPTS = "1"

$Instancia = "capi-db"
$Banco = "nota_a_nota"
$Repositorio = "capi"
$ContaDeServico = "capi-run@$Projeto.iam.gserviceaccount.com"
$ContaDeDeploy = "capi-deploy@$Projeto.iam.gserviceaccount.com"
$Audiencia = "nota-a-nota-api"
$Conexao = "$($Projeto):$($Regiao):$Instancia"

function Invoke-Gcloud {
  $ErrorActionPreference = "Continue"
  & gcloud @args
  if ($LASTEXITCODE -ne 0) { throw "Falhou: gcloud $($args -join ' ')" }
}

function Invoke-GcloudComRepeticao {
  for ($tentativa = 1; $tentativa -le 6; $tentativa++) {
    $ErrorActionPreference = "Continue"
    & gcloud @args *> $null
    if ($LASTEXITCODE -eq 0) { return }
    Start-Sleep -Seconds 10
  }
  throw "Falhou depois de 6 tentativas: gcloud $($args -join ' ')"
}

function Get-Gcloud {
  $ErrorActionPreference = "Continue"
  $saida = & gcloud @args 2>$null
  if ($LASTEXITCODE -ne 0) { throw "Falhou: gcloud $($args -join ' ')" }
  ($saida | Out-String).Trim()
}

function Test-Gcloud {
  $ErrorActionPreference = "Continue"
  & gcloud @args *> $null
  $LASTEXITCODE -eq 0
}

function Test-Segredo([string]$Nome) {
  Test-Gcloud secrets versions describe latest --secret=$Nome --format="value(name)"
}

function Set-Segredo([string]$Nome, [string]$Valor) {
  $arquivo = [IO.Path]::GetTempFileName()
  try {
    [IO.File]::WriteAllText($arquivo, $Valor, (New-Object Text.UTF8Encoding $false))
    if (Test-Gcloud secrets describe $Nome) {
      Invoke-Gcloud secrets versions add $Nome --data-file=$arquivo --quiet *> $null
    } else {
      Invoke-Gcloud secrets create $Nome --replication-policy=automatic --data-file=$arquivo --quiet *> $null
    }
  } finally {
    Remove-Item $arquivo -Force
  }
}

function New-Aleatorio([int]$Bytes, [switch]$Hex) {
  $dados = New-Object byte[] $Bytes
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($dados)
  if ($Hex) { return -join ($dados | ForEach-Object { $_.ToString("x2") }) }
  [Convert]::ToBase64String($dados)
}
