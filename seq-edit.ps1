param([string]$todoPath)
$shas = @(
  '6b047d0fc4254d36b1157001b597ff5d3e1b1acd',
  '30ecd31c37b983f62300448e92ac5ad7d541406e',
  '471cc72684d9d190d30807513da963d498ee295c'
)
$text = Get-Content -Raw -Encoding UTF8 $todoPath
foreach ($s in $shas) {
  $text = $text -replace "(?m)^pick\s+$s","reword $s"
}
Set-Content -Encoding UTF8 -Value $text -Path $todoPath
