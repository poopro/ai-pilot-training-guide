$taskRoot = 'E:\ai_pilot\autopilot\combat_fix'
$taskActivePath = Join-Path $taskRoot 'active_run.json'
if (-not (Test-Path -LiteralPath $taskActivePath)) { Write-Host '目前沒有登錄的修正版訓練。'; exit }
$taskActive = Get-Content -LiteralPath $taskActivePath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskRunPath = [IO.Path]::GetFullPath([string]$taskActive.run_dir)
$taskAllowed = [IO.Path]::GetFullPath((Join-Path $taskRoot 'training')) + '\'
if (-not $taskRunPath.StartsWith($taskAllowed, [StringComparison]::OrdinalIgnoreCase)) { throw '作業路徑不符，未寫停止檔。' }
if (-not (Test-Path -LiteralPath $taskRunPath)) { throw '作業目錄不存在。' }
if (Test-Path -LiteralPath (Join-Path $taskRunPath 'result.json')) { Write-Host '這個作業已結束。'; exit }
Set-Content -LiteralPath (Join-Path $taskRunPath 'STOP') -Value 'User requested safe save and stop' -Encoding UTF8
Write-Host '已要求停止並保存。請等訓練視窗顯示已完整儲存，不要直接關掉Python。'
