<#
.SYNOPSIS
  Устанавливает MCP-сервер 1С через COM в указанный проект Cursor.

.DESCRIPTION
  - Готовит portable Python (если нет) и зависимости mcp/pywin32
  - При необходимости регистрирует V83.COMConnector (comcntr.dll)
  - Копирует код сервера в <Project>\tools\mcp-1c-com (или использует -SharedServerDir)
  - Пишет/дополняет <Project>\.cursor\mcp.json
  - Опционально проверяет соединение (smoke_test)

.EXAMPLE
  .\Install-Mcp1cCom.ps1 -ProjectPath D:\MyProject -ServerName ka-com `
    -Srvr localhost -Ref KA -User User -Password '***'

.EXAMPLE
  .\Install-Mcp1cCom.ps1 -ProjectPath D:\MyProject -Interactive
#>

[CmdletBinding(DefaultParameterSetName = "Params")]
param(
  [Parameter(Mandatory = $true)]
  [string] $ProjectPath,

  [string] $ServerName = "",

  [Parameter(ParameterSetName = "Params")]
  [string] $Srvr = "",

  [Parameter(ParameterSetName = "Params")]
  [string] $Ref = "",

  [Parameter(ParameterSetName = "Params")]
  [string] $File = "",

  [string] $User = "",

  [string] $Password = "",

  [string] $PythonDir = "",

  [string] $SharedServerDir = "",

  [string] $OneCPlatformDir = "",

  [switch] $Interactive,

  [switch] $SkipComRegister,

  [switch] $SkipSmokeTest,

  [switch] $CopyIntoProject
)

$ErrorActionPreference = "Stop"

function Write-Step([string] $Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Read-Default([string] $Prompt, [string] $Default = "") {
  if ($Default) {
    $v = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($v)) { return $Default }
    return $v
  }
  return Read-Host $Prompt
}

function Find-ComCntrDll {
  param([string] $Hint)
  if ($Hint) {
    $p = Join-Path $Hint "bin\comcntr.dll"
    if (Test-Path $p) { return $p }
    $p = Join-Path $Hint "comcntr.dll"
    if (Test-Path $p) { return $p }
  }
  $roots = @()
  if ($env:ProgramFiles) { $roots += (Join-Path $env:ProgramFiles "1cv8") }
  $pf86 = ${env:ProgramFiles(x86)}
  if ($pf86) { $roots += (Join-Path $pf86 "1cv8") }

  $found = @()
  foreach ($root in $roots) {
    if (-not (Test-Path $root)) { continue }
    $found += Get-ChildItem -Path $root -Filter "comcntr.dll" -Recurse -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -match '\\bin\\comcntr\.dll$' }
  }
  if (-not $found -or $found.Count -eq 0) { return $null }
  return ($found | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}

function Ensure-PortablePython {
  param([string] $TargetDir)

  $pythonExe = Join-Path $TargetDir "python.exe"
  if (Test-Path $pythonExe) {
    Write-Host "Python already present: $pythonExe"
    return $pythonExe
  }

  Write-Step "Downloading portable Python 3.12.8 (embeddable)"
  New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
  $setupDir = Join-Path (Split-Path $TargetDir -Parent) "_setup"
  New-Item -ItemType Directory -Force -Path $setupDir | Out-Null
  $zip = Join-Path $setupDir "python-3.12.8-embed-amd64.zip"
  $url = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
  if (-not (Test-Path $zip)) {
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
  }
  Expand-Archive -Path $zip -DestinationPath $TargetDir -Force

  $pth = Join-Path $TargetDir "python312._pth"
  @(
    "python312.zip",
    ".",
    "Lib\site-packages",
    "import site"
  ) | Set-Content -Path $pth -Encoding ASCII
  New-Item -ItemType Directory -Force -Path (Join-Path $TargetDir "Lib\site-packages") | Out-Null

  Write-Step "Installing pip"
  $getPip = Join-Path $setupDir "get-pip.py"
  if (-not (Test-Path $getPip)) {
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
  }
  & $pythonExe $getPip --no-warn-script-location
  return $pythonExe
}

function Ensure-PythonPackages {
  param([string] $PythonExe, [string] $RequirementsFile)
  Write-Step "Installing MCP dependencies"
  & $PythonExe -m pip install --no-warn-script-location -r $RequirementsFile
  $post = Join-Path (Split-Path $PythonExe) "Lib\site-packages\win32\scripts\pywin32_postinstall.py"
  if (Test-Path $post) {
    & $PythonExe $post -install 2>$null | Out-Null
  }
}

function Ensure-ComConnector {
  param([string] $DllPath)
  Write-Step "Registering COM: $DllPath"
  try {
    $p = Start-Process -FilePath "regsvr32.exe" -ArgumentList @("/s", "`"$DllPath`"") -Verb RunAs -Wait -PassThru
    if ($p.ExitCode -ne 0) {
      Write-Warning "regsvr32 exit $($p.ExitCode). Register comcntr.dll manually as Administrator if Connect fails."
    } else {
      Write-Host "COM registered."
    }
  } catch {
    Write-Warning "Could not elevate regsvr32: $($_.Exception.Message)"
  }
}

function Merge-McpJson {
  param(
    [string] $McpJsonPath,
    [string] $Name,
    [hashtable] $ServerEntry
  )
  $dir = Split-Path $McpJsonPath -Parent
  New-Item -ItemType Directory -Force -Path $dir | Out-Null

  $servers = @{}
  if (Test-Path $McpJsonPath) {
    $raw = Get-Content -LiteralPath $McpJsonPath -Raw -Encoding UTF8
    if ($raw -and $raw.Trim()) {
      $parsed = $raw | ConvertFrom-Json
      if ($parsed.mcpServers) {
        foreach ($p in $parsed.mcpServers.PSObject.Properties) {
          $servers[$p.Name] = $p.Value
        }
      }
    }
  }
  $servers[$Name] = $ServerEntry
  $root = @{ mcpServers = $servers }
  $json = $root | ConvertTo-Json -Depth 8
  [System.IO.File]::WriteAllText($McpJsonPath, $json, [System.Text.UTF8Encoding]::new($false))
  Write-Host "Wrote: $McpJsonPath (server '$Name')"
}

$ProjectPath = [System.IO.Path]::GetFullPath($ProjectPath)
if (-not (Test-Path $ProjectPath)) {
  throw "Project folder not found: $ProjectPath"
}

$SourceServerDir = $PSScriptRoot
if (-not (Test-Path (Join-Path $SourceServerDir "server.py"))) {
  throw "server.py not found next to installer: $SourceServerDir"
}

if ($Interactive) {
  Write-Host "Install MCP 1C COM into: $ProjectPath"
  $Srvr = Read-Default "1C server (Srvr), empty for file IB" $Srvr
  if ($Srvr) {
    $Ref = Read-Default "Infobase name (Ref)" $Ref
  } else {
    $File = Read-Default "File IB path (ONEC_FILE)" $File
  }
  $User = Read-Default "1C user" $(if ($User) { $User } else { "Administrator" })
  $secure = Read-Host "Password" -AsSecureString
  $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
  $defaultName = if ($Ref) { "$Ref-com".ToLower() } elseif ($File) { "1c-file-com" } else { "1c-com" }
  if (-not $ServerName) { $ServerName = $defaultName }
  $ServerName = Read-Default "MCP server name in Cursor" $ServerName
  $ans = Read-Default "Copy server code into project? (y/N)" "N"
  if ($ans -match '^(y|Y|д|Д)') { $CopyIntoProject = $true }
}

if (-not $ServerName) {
  if ($Ref) { $ServerName = "$($Ref.ToLower())-com" }
  elseif ($File) { $ServerName = "1c-file-com" }
  else { $ServerName = "1c-com" }
}

if (-not $File -and (-not $Srvr -or -not $Ref)) {
  throw "Provide -File, or -Srvr and -Ref (or -Interactive)."
}
if (-not $User) {
  throw "Provide -User (or -Interactive)."
}

$BundleRoot = Split-Path $SourceServerDir -Parent
if (-not $PythonDir) {
  $PythonDir = Join-Path $SourceServerDir "_python"
}
$PythonDir = [System.IO.Path]::GetFullPath($PythonDir)
$PythonExe = Ensure-PortablePython -TargetDir $PythonDir
Ensure-PythonPackages -PythonExe $PythonExe -RequirementsFile (Join-Path $SourceServerDir "requirements.txt")

if (-not $SkipComRegister) {
  $dll = Find-ComCntrDll -Hint $OneCPlatformDir
  if ($dll) {
    Ensure-ComConnector -DllPath $dll
  } else {
    Write-Warning "comcntr.dll not found. Pass -OneCPlatformDir 'C:\Program Files\1cv8\8.3.xx.xxxx'"
  }
}

if ($SharedServerDir) {
  $RuntimeServerDir = [System.IO.Path]::GetFullPath($SharedServerDir)
  if (-not (Test-Path (Join-Path $RuntimeServerDir "server.py"))) {
    throw "SharedServerDir has no server.py: $RuntimeServerDir"
  }
} elseif ($CopyIntoProject) {
  Write-Step "Copying server into project"
  $RuntimeServerDir = Join-Path $ProjectPath "tools\mcp-1c-com"
  New-Item -ItemType Directory -Force -Path $RuntimeServerDir | Out-Null
  foreach ($f in @("server.py", "onec_com.py", "config.py", "smoke_test.py", "requirements.txt", ".env.example", "README.md", "Install-Mcp1cCom.ps1", "LICENSE")) {
    $src = Join-Path $SourceServerDir $f
    if (Test-Path $src) {
      Copy-Item -LiteralPath $src -Destination (Join-Path $RuntimeServerDir $f) -Force
    }
  }
} else {
  $RuntimeServerDir = $SourceServerDir
}

$ServerPy = Join-Path $RuntimeServerDir "server.py"
if (-not (Test-Path $ServerPy)) {
  throw "server.py not found: $ServerPy"
}

Write-Step "Writing .cursor/mcp.json"
$envMap = @{
  ONEC_MCP_NAME = $ServerName
  ONEC_USR      = $User
  ONEC_PWD      = $Password
}
if ($File) {
  $envMap["ONEC_FILE"] = $File
} else {
  $envMap["ONEC_SRVR"] = $Srvr
  $envMap["ONEC_REF"] = $Ref
}

$entry = @{
  command = ($PythonExe -replace '/', '\')
  args    = @(($ServerPy -replace '/', '\'))
  env     = $envMap
}

$mcpJson = Join-Path $ProjectPath ".cursor\mcp.json"
Merge-McpJson -McpJsonPath $mcpJson -Name $ServerName -ServerEntry $entry

$example = Join-Path $ProjectPath ".cursor\mcp.json.example"
$exampleEnv = @{}
foreach ($k in $envMap.Keys) {
  if ($k -eq "ONEC_PWD") { $exampleEnv[$k] = "" }
  else { $exampleEnv[$k] = $envMap[$k] }
}
$exampleEntry = @{
  command = $entry.command
  args    = $entry.args
  env     = $exampleEnv
}
Merge-McpJson -McpJsonPath $example -Name $ServerName -ServerEntry $exampleEntry

$gi = Join-Path $ProjectPath ".gitignore"
$giLines = @(".cursor/mcp.json", "tools/_python/", "tools/_setup/", "_python/", "_setup/")
if (Test-Path $gi) {
  $existing = Get-Content $gi -ErrorAction SilentlyContinue
  foreach ($line in $giLines) {
    if ($existing -notcontains $line) {
      Add-Content -Path $gi -Value $line
    }
  }
}

if (-not $SkipSmokeTest) {
  Write-Step "Connection smoke test"
  $env:ONEC_MCP_NAME = $ServerName
  $env:ONEC_USR = $User
  $env:ONEC_PWD = $Password
  if ($File) {
    $env:ONEC_FILE = $File
    Remove-Item Env:\ONEC_SRVR -ErrorAction SilentlyContinue
    Remove-Item Env:\ONEC_REF -ErrorAction SilentlyContinue
  } else {
    $env:ONEC_SRVR = $Srvr
    $env:ONEC_REF = $Ref
    Remove-Item Env:\ONEC_FILE -ErrorAction SilentlyContinue
  }
  & $PythonExe (Join-Path $RuntimeServerDir "smoke_test.py")
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Project:    $ProjectPath"
Write-Host "  MCP server: $ServerName"
Write-Host "  Runtime:    $RuntimeServerDir"
Write-Host "  Python:     $PythonExe"
Write-Host ""
Write-Host "In Cursor: Settings -> MCP -> Refresh (or restart Cursor)."
