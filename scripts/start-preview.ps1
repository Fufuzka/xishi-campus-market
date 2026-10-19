param([int]$Port = 8007)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot
$PythonPath = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $PythonPath)) {
    $PythonPath = Join-Path (Split-Path $ProjectRoot -Parent) '.venv/Scripts/python.exe'
}
if (!(Test-Path -LiteralPath $PythonPath)) {
    throw '请先按 README 安装 Python 环境并运行 start.ps1 -Demo。'
}
if ($Port -lt 1024 -or $Port -gt 65535) { throw '端口应在 1024 到 65535 之间。' }
$env:MARKET_DATA_DIR = Join-Path $ProjectRoot 'test-data/campus-preview'
$env:PYTHONUTF8 = '1'
$PreviewUrl = "http://127.0.0.1:$Port"
try {
    $Health = Invoke-RestMethod "$PreviewUrl/api/health" -TimeoutSec 2
} catch { $Health = $null }
if ($Health -and $Health.status -eq 'ok' -and $Health.version -eq '0.2.0-beta.1') {
    Write-Host "测试服务已在运行，请在浏览器打开 $PreviewUrl"
    exit 0
}
& $PythonPath -m backend.seed
if ($LASTEXITCODE -ne 0) { throw '初始化测试数据失败。' }
Write-Host "请在浏览器打开 $PreviewUrl"
Write-Host '测试期间请保留这个窗口。关闭窗口或按 Ctrl+C 会停止测试服务。'
& $PythonPath -m uvicorn backend.main:app --host 127.0.0.1 --port $Port --reload --reload-dir backend
exit $LASTEXITCODE
