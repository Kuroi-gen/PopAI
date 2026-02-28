$ErrorActionPreference = "Stop"

$src = "D:\002_MyDocuments\000_Study\002_Programing\013_Antigravity\PopAI"
$tmp = Join-Path $env:TEMP "PopAI_GitFix"

if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $tmp | Out-Null

Copy-Item "$src\*" -Destination $tmp -Recurse -Force -Exclude ".git", "__pycache__"

Push-Location $tmp
git init --template='"' --initial-branch=main
git config core.autocrlf false
git config core.filemode false
git add .
git commit -m "feat: initial commit"
Pop-Location

if (Test-Path "$src\.git") { Remove-Item "$src\.git" -Recurse -Force -ErrorAction SilentlyContinue }
Move-Item "$tmp\.git" -Destination "$src\.git" -Force
