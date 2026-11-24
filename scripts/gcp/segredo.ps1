param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("anthropic-api-key", "voyage-api-key", "smtp-url", "google-client-id", "google-client-secret")]
  [string]$Nome,
  [string]$Projeto = "projetos-pessoais-vini",
  [string]$Configuracao = "nota-a-nota"
)

. "$PSScriptRoot\comum.ps1" -Projeto $Projeto -Configuracao $Configuracao

$seguro = Read-Host -AsSecureString "Cole o valor de $Nome (nao aparece na tela)"
$ponteiro = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
try {
  $valor = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ponteiro).Trim()
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ponteiro)
}
if (-not $valor) { throw "Valor vazio; nada foi gravado." }

Set-Segredo $Nome $valor
Remove-Variable valor
Write-Host "Gravado em $Nome. Rode scripts\gcp\publicar.ps1 para os servicos passarem a usar."
