# Operação manual de go-live: usa somente o cofre local e não imprime segredos.
$ErrorActionPreference = 'Stop'
$ref = 'fvrjxoycosmuujxvhnpm'
$vault = Get-Content -LiteralPath 'C:\Users\caio.cacalho\.agende-bem\secrets.json' -Raw | ConvertFrom-Json
$keys = supabase projects api-keys --project-ref $ref --output json 2>$null | ConvertFrom-Json
$service = ($keys | Where-Object { $_.name -eq 'service_role' }).api_key
if (-not $service) { throw 'Chave server-side indisponível.' }
$appPass = [uri]::EscapeDataString([string]$vault.app_role_password)
$env:DATABASE_URL = "postgresql://agende_bem_app.${ref}:$appPass@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
$env:SUPABASE_URL = "https://$ref.supabase.co"
$env:SUPABASE_SECRET_KEY = $service
try {
    & "$PSScriptRoot\..\.venv\Scripts\python.exe" -c "from database import connect; from authorization import Actor,Role; from file_library import SupabaseStorage; from template_catalog import register_defaults; c=connect(); a=Actor('00000000-0000-0000-0000-000000000001','v3.admin@agendebem.test',Role.ADMIN); print('templates_created='+str(register_defaults(c,SupabaseStorage(),a))); print('templates_total='+str(c.execute('SELECT count(*) AS n FROM file_templates').fetchone()['n']))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Remove-Item Env:DATABASE_URL,Env:SUPABASE_URL,Env:SUPABASE_SECRET_KEY -ErrorAction SilentlyContinue
}
