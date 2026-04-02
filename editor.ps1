param([string]$msgPath)
$m = Get-Content -Raw -Encoding UTF8 $msgPath
$m = $m -replace '(?i)lovable','Secure Gig Guardian'
Set-Content -Encoding UTF8 -Value $m -Path $msgPath
