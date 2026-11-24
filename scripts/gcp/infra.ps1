param(
  [string]$Projeto = "projetos-pessoais-vini",
  [string]$Regiao = "southamerica-east1",
  [string]$Configuracao = "nota-a-nota",
  [string]$RepositorioGitHub
)

. "$PSScriptRoot\comum.ps1" -Projeto $Projeto -Regiao $Regiao -Configuracao $Configuracao

Write-Host "APIs do projeto"
Invoke-Gcloud services enable run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com

Write-Host "Repositorio de imagens"
if (-not (Test-Gcloud artifacts repositories describe $Repositorio --location=$Regiao)) {
  Invoke-Gcloud artifacts repositories create $Repositorio --repository-format=docker --location=$Regiao --description="Imagens do Capi"
}

Write-Host "Conta de servico dos containers"
if (-not (Test-Gcloud iam service-accounts describe $ContaDeServico)) {
  Invoke-Gcloud iam service-accounts create capi-run --display-name="Capi no Cloud Run"
}
foreach ($papel in "roles/cloudsql.client", "roles/secretmanager.secretAccessor") {
  Invoke-GcloudComRepeticao projects add-iam-policy-binding $Projeto --member="serviceAccount:$ContaDeServico" --role=$papel --condition=None --quiet
}

Write-Host "Cloud SQL (leva uns 10 minutos na primeira vez)"
if (-not (Test-Gcloud sql instances describe $Instancia)) {
  $senha = New-Aleatorio 24 -Hex
  Invoke-Gcloud sql instances create $Instancia `
    --database-version=POSTGRES_17 `
    --edition=ENTERPRISE `
    --tier=db-f1-micro `
    --region=$Regiao `
    --availability-type=ZONAL `
    --storage-type=SSD `
    --storage-size=10 `
    --storage-auto-increase `
    --backup-start-time=06:00 `
    --retained-backups-count=7 `
    --deletion-protection `
    --root-password=$senha
  Invoke-Gcloud sql databases create $Banco --instance=$Instancia
  $conexao = Get-Gcloud sql instances describe $Instancia --format="value(connectionName)"
  Set-Segredo "database-url" "postgresql://postgres:$senha@/$($Banco)?host=/cloudsql/$conexao"
} elseif (-not (Test-Segredo "database-url")) {
  throw "A instancia $Instancia existe, mas o segredo database-url nao. Redefina a senha do usuario postgres e grave o segredo."
}

Write-Host "Segredo do Better Auth"
if (-not (Test-Segredo "better-auth-secret")) {
  Set-Segredo "better-auth-secret" (New-Aleatorio 48)
}

if ($RepositorioGitHub) {
  Write-Host "Deploy pelo GitHub Actions sem chave ($RepositorioGitHub, so a branch main)"
  $idDoRepositorio = (& gh api "repos/$RepositorioGitHub" --jq .id).Trim()
  if (-not $idDoRepositorio) { throw "Nao achei o repositorio $RepositorioGitHub no GitHub." }
  $numero = Get-Gcloud projects describe $Projeto --format="value(projectNumber)"

  if (-not (Test-Gcloud iam workload-identity-pools describe github --location=global)) {
    Invoke-Gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
  }
  $condicao = "assertion.repository_id=='$idDoRepositorio' && assertion.ref=='refs/heads/main'"
  $mapeamento = "google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref"
  if (Test-Gcloud iam workload-identity-pools providers describe github --location=global --workload-identity-pool=github) {
    Invoke-Gcloud iam workload-identity-pools providers update-oidc github --location=global --workload-identity-pool=github --attribute-mapping=$mapeamento --attribute-condition=$condicao
  } else {
    Invoke-Gcloud iam workload-identity-pools providers create-oidc github --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping=$mapeamento --attribute-condition=$condicao
  }

  if (-not (Test-Gcloud iam service-accounts describe $ContaDeDeploy)) {
    Invoke-Gcloud iam service-accounts create capi-deploy --display-name="Deploy do Capi pelo GitHub"
  }
  $principal = "principalSet://iam.googleapis.com/projects/$numero/locations/global/workloadIdentityPools/github/attribute.repository_id/$idDoRepositorio"
  Invoke-GcloudComRepeticao iam service-accounts add-iam-policy-binding $ContaDeDeploy --member=$principal --role=roles/iam.workloadIdentityUser
  foreach ($papel in "roles/run.admin", "roles/secretmanager.viewer") {
    Invoke-GcloudComRepeticao projects add-iam-policy-binding $Projeto --member="serviceAccount:$ContaDeDeploy" --role=$papel --condition=None --quiet
  }
  Invoke-GcloudComRepeticao iam service-accounts add-iam-policy-binding $ContaDeServico --member="serviceAccount:$ContaDeDeploy" --role=roles/iam.serviceAccountUser
  Invoke-GcloudComRepeticao artifacts repositories add-iam-policy-binding $Repositorio --location=$Regiao --member="serviceAccount:$ContaDeDeploy" --role=roles/artifactregistry.writer

  Write-Host ""
  Write-Host "Variaveis do repositorio no GitHub:"
  Write-Host "  GCP_PROJECT=$Projeto"
  Write-Host "  GCP_PROJECT_NUMBER=$numero"
  Write-Host "  GCP_REGION=$Regiao"
  Write-Host "  GCP_DEPLOY_SA=$ContaDeDeploy"
  Write-Host "  GCP_WIF_PROVIDER=projects/$numero/locations/global/workloadIdentityPools/github/providers/github"
}

Write-Host "Pronto. Proximo passo: scripts\gcp\publicar.ps1"
