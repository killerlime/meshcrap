# Run on your Windows relay host in Administrator PowerShell.
# This installer never changes radio settings or restarts Tailscale.
#Requires -Version 5.1
#Requires -RunAsAdministrator
param(
    [Parameter(Mandatory=$true)][System.Net.IPAddress]$ListenAddress,
    [Parameter(Mandatory=$true)][System.Net.IPAddress]$TargetAddress,
    [ValidateRange(1,65535)][int]$Port = 4403
)
$ErrorActionPreference = 'Stop'
if ($ListenAddress.AddressFamily -ne 'InterNetwork' -or $TargetAddress.AddressFamily -ne 'InterNetwork') { throw 'IPv4 addresses required' }
if ($env:COMPUTERNAME -notmatch '^[A-Za-z0-9-]+$') { throw 'Unsupported computer name' }
$taskName = 'Meshcrap - Relay watchdog'
$installDir = Join-Path $env:ProgramData 'Meshcrap-Relay'
$monitorPath = Join-Path $installDir 'Watch-Relay.ps1'
$markerPath = Join-Path $installDir 'managed-by-meshcrap-relay-installer.txt'
if ((Test-Path -LiteralPath $installDir) -and -not (Test-Path -LiteralPath $markerPath)) {
    throw "Existing unmanaged directory: $installDir. No changes made."
}
foreach ($path in @($installDir,$monitorPath,$markerPath)) {
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing redirected installation path: $path"
    }
}
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask -and $existingTask.Description -notlike 'Meshcrap relay watchdog*') {
    throw 'A different task already uses this name. No changes made.'
}
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
# SYSTEM executes this script: ordinary users must not be able to modify it.
$acl = New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
foreach ($sid in @('S-1-5-18','S-1-5-32-544')) {
    $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $installDir -AclObject $acl
$monitor = @'
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$listenAddress = '__LISTEN__'
$listenPort = __PORT__
$targetAddress = '__TARGET__'
$targetPort = __PORT__
$logPath = Join-Path $PSScriptRoot 'relay-watchdog.log'
function Write-RelayLog([string]$Message) {
    if ((Test-Path -LiteralPath $logPath) -and (Get-Item -LiteralPath $logPath).Length -gt 1048576) {
        Move-Item -LiteralPath $logPath -Destination ($logPath + '.previous') -Force
    }
    Add-Content -LiteralPath $logPath -Value ('{0:o} {1}' -f (Get-Date), $Message) -Encoding UTF8
}
try {
    if ($env:COMPUTERNAME -ine '__HOST__') { throw 'Wrong computer; refusing to modify forwarding.' }
    # A missing Tailscale address is not a broken relay. Wait for the next run.
    $address = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -eq $listenAddress }
    if (-not $address) { exit 0 }
    $registryPath = 'HKLM:\SYSTEM\CurrentControlSet\Services\PortProxy\v4tov4\tcp'
    $ruleName = "$listenAddress/$listenPort"
    $expected = "$targetAddress/$targetPort"
    $saved = $null
    if (Test-Path -LiteralPath $registryPath) {
        $saved = (Get-Item -LiteralPath $registryPath).GetValue($ruleName, $null)
    }
    if ($null -ne $saved -and $saved -ne $expected) {
        throw "Forwarding target was changed to $saved. Preserving it; update watchdog configuration intentionally."
    }
    $listener = Get-NetTCPConnection -LocalAddress $listenAddress -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        if ($saved -ne $expected) { throw 'Port is owned by another listener; no forwarding rule was changed.' }
        exit 0
    }
    Start-Service -Name iphlpsvc
    $netsh = Join-Path $env:SystemRoot 'System32\netsh.exe'
    if ($null -ne $saved) {
        $output = & $netsh interface portproxy delete v4tov4 "listenaddress=$listenAddress" "listenport=$listenPort" 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Could not remove the stale rule: $output" }
    }
    $output = & $netsh interface portproxy add v4tov4 "listenaddress=$listenAddress" "listenport=$listenPort" "connectaddress=$targetAddress" "connectport=$targetPort" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Could not restore forwarding: $output" }
    # Inspect Windows' listener table, not the radio's single-client TCP socket.
    $listener = $null
    for ($attempt = 0; $attempt -lt 5; $attempt++) {
        Start-Sleep -Seconds 1
        $listener = Get-NetTCPConnection -LocalAddress $listenAddress -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue
        if ($listener) { break }
    }
    if (-not $listener) { throw 'Rule restored, but the relay listener is still missing. Tailscale was not restarted.' }
    Write-RelayLog "Repaired $listenAddress`:$listenPort -> $targetAddress`:$targetPort"
    exit 0
} catch {
    Write-RelayLog ('ERROR: ' + $_.Exception.Message)
    exit 1
}
'@
$monitor = $monitor.Replace('__HOST__',$env:COMPUTERNAME).Replace('__LISTEN__',$ListenAddress.ToString()).Replace('__TARGET__',$TargetAddress.ToString()).Replace('__PORT__',$Port.ToString())
$monitor | Set-Content -LiteralPath $monitorPath -Encoding UTF8
'Meshcrap relay watchdog installer v1' | Set-Content -LiteralPath $markerPath -Encoding ASCII
foreach ($path in @($monitorPath,$markerPath)) {
    $fileAcl = New-Object System.Security.AccessControl.FileSecurity
    $fileAcl.SetAccessRuleProtection($true,$false)
    foreach ($sid in @('S-1-5-18','S-1-5-32-544')) {
        $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
        $fileAcl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')))
    }
    Set-Acl -LiteralPath $path -AclObject $fileAcl
}
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $monitorPath)
$startup = New-ScheduledTaskTrigger -AtStartup
# Omitted repetition duration means indefinite repetition, not a one-day expiry.
$periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 3)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($startup,$periodic) -Principal $principal -Settings $settings -Description 'Meshcrap relay watchdog v1: repair only the configured Tailscale portproxy listener; no radio probes or Tailscale restarts.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "Installed on $env:COMPUTERNAME. Runs at startup and every 3 minutes, including while logged out."
Write-Host "Logs: $installDir\relay-watchdog.log (repairs/errors only)."
Start-Sleep -Seconds 8
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object LastRunTime,LastTaskResult,NextRunTime
Get-NetTCPConnection -LocalAddress $ListenAddress.ToString() -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State
