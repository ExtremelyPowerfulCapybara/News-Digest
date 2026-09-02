# run_telegram.ps1 — Telegram editorial callback handler
# Scheduled: every 5 minutes via Task Scheduler (\MustardHQ\Telegram Handler)

$repo = "C:\Projects\News-Digest"
$date = Get-Date -Format "yyyy-MM-dd"
$log  = "C:\Projects\logs\telegram_$date.log"

New-Item -ItemType Directory -Force -Path "C:\Projects\logs" | Out-Null
Set-Location $repo

docker compose run --rm app python telegram_handler.py 2>&1 | Add-Content $log

# Push any image selections (hero image copied to docs/ after Telegram callback)
git -C $repo add docs/ digests/
git -C $repo diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git -C $repo commit -m "Image selection: $date"
    git -C $repo push origin main
}
