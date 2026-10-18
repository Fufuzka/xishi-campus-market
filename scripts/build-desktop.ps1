param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$VersionSource = Get-Content desktop/version-info.txt -Raw -Encoding utf8
$VersionMatch = [regex]::Match($VersionSource, "StringStruct\('ProductVersion', '([^']+)'\)")
if (!$VersionMatch.Success) { throw '无法读取桌面版本号。' }
$BuildVersion = $VersionMatch.Groups[1].Value
$OutputDirectory = Join-Path 'dist' $BuildVersion
$WorkDirectory = Join-Path 'build' $BuildVersion
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --distpath $OutputDirectory --workpath $WorkDirectory --name '夕拾' --icon desktop/app.ico --version-file desktop/version-info.txt --add-data 'frontend;frontend' --add-data 'backend/schema.sql;backend' --add-data 'desktop/settings.html;desktop' --collect-all webview --hidden-import uvicorn.logging --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.protocols.http.h11_impl --hidden-import uvicorn.lifespan.on run_desktop.py
if ($LASTEXITCODE -ne 0) { throw '桌面打包失败，请查看构建日志。' }
Write-Output "已生成 $OutputDirectory/夕拾.exe"
