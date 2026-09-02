# run_newsletter.ps1 — Main newsletter pipeline + git push
# Scheduled: Mon-Fri 07:30 CDMX via Task Scheduler (\MustardHQ\Newsletter Pipeline)

$repo = "C:\Projects\News-Digest"
$date = Get-Date -Format "yyyy-MM-dd"
$log  = "C:\Projects\logs\newsletter_$date.log"

New-Item -ItemType Directory -Force -Path "C:\Projects\logs" | Out-Null
Set-Location $repo

"=== Newsletter run $date $(Get-Date -Format 'HH:mm:ss') ===" | Add-Content $log

# Run the pipeline
docker compose run --rm app python main.py 2>&1 | Tee-Object -FilePath $log -Append

# Commit and push docs/ + digests/ back to main for GitHub Pages
git -C $repo add docs/ digests/
git -C $repo diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git -C $repo commit -m "Issue: $date"
    git -C $repo push origin main
    "$(Get-Date -Format 'HH:mm:ss') Committed and pushed issue $date" | Add-Content $log
} else {
    "$(Get-Date -Format 'HH:mm:ss') Nothing new to commit." | Add-Content $log
}
