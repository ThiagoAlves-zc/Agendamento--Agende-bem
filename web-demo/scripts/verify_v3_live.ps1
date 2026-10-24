# Smoke test manual do go-live V3. Usa somente credenciais locais e dados sintéticos.
# Não imprime chaves, tokens, senhas ou strings de conexão.
$ErrorActionPreference = 'Stop'
$ref = 'fvrjxoycosmuujxvhnpm'
$vault = Get-Content -LiteralPath 'C:\Users\caio.cacalho\.agende-bem\secrets.json' -Raw | ConvertFrom-Json
$keys = supabase projects api-keys --project-ref $ref --output json 2>$null | ConvertFrom-Json
$service = ($keys | Where-Object { $_.name -eq 'service_role' }).api_key
$publishable = ($keys | Where-Object { $_.name -eq 'anon' }).api_key
if (-not $service -or -not $publishable) { throw 'Chaves server-side ou publicável indisponíveis.' }
$appPass = [uri]::EscapeDataString([string]$vault.app_role_password)
$env:DATABASE_URL = "postgresql://agende_bem_app.${ref}:$appPass@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
$env:SUPABASE_URL = "https://$ref.supabase.co"
$env:SUPABASE_SECRET_KEY = $service
$env:SUPABASE_PUBLISHABLE_KEY = $publishable
try {
    & "$PSScriptRoot\..\.venv\Scripts\python.exe" "$PSScriptRoot\verify_v3_live.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Remove-Item Env:DATABASE_URL,Env:SUPABASE_URL,Env:SUPABASE_SECRET_KEY,Env:SUPABASE_PUBLISHABLE_KEY -ErrorAction SilentlyContinue
}
