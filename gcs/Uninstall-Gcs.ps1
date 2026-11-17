<#
.SYNOPSIS
  Hoan tac phan thiet lap may (nguon, tuong lua, shortcut) tu state.json do Install-Gcs.ps1 ghi.
  Go Mission Planner CHI KHI co -RemoveApps (va chi neu chinh Install-Gcs da cai no).
  Khong xoa C:\GCS (log, backup, config), khong xoa du lieu Mission Planner trong Documents / ProgramData.
  Chi tin state.json nam trong C:\GCS\backup\ va do Administrators/SYSTEM so huu (Users khong ghi duoc);
  moi gia tri doc tu state (duong dan, ten quy tac, GUID...) deu bi kiem pham vi truoc khi dung.
  Khoi phuc xong khong loi: state.json doi ten thanh state.restored.json de lan Install sau chup lai hien trang moi.
.PARAMETER StatePath
  state.json cu the (phai nam trong <GcsRoot>\backup\). Mac dinh: ban moi nhat trong C:\GCS\backup\*\.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$StatePath = '',
    [switch]$RemoveApps,
    [string]$GcsRoot = 'C:\GCS'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:Cmdlet = $PSCmdlet
$script:Dry = [bool]$WhatIfPreference
$script:Rows = New-Object System.Collections.ArrayList

# Chay bang quyen admin tu <GcsRoot>\tools: GcsLogic.ps1 (se duoc nap) va thu muc chua no phai do Administrators/SYSTEM so huu va
# khong ai ngoai Administrators/SYSTEM/TrustedInstaller ghi duoc; khong thi DUNG (chay ban goc tu USB thay vi ban trong C:\GCS\tools).
# (Ban sao nho cua Test-GcsFileTrusted vi chua nap duoc GcsLogic.ps1 de dung no.)
function Test-BootstrapTrusted([string]$Path) {
    $okSids = @('S-1-5-32-544', 'S-1-5-18')
    $mayWrite = $okSids + @('S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')
    $mask = [int64](0x2 -bor 0x4 -bor 0x10 -bor 0x40 -bor 0x100 -bor 0x10000 -bor 0x40000 -bor 0x80000 -bor 0x10000000 -bor 0x40000000)
    $bad = @()
    foreach ($t in @($Path, (Split-Path -Parent $Path))) {
        $it = Get-Item -LiteralPath $t -Force
        if (($it.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { $bad += "${t}: la reparse point"; continue }
        $acl = Get-Acl -LiteralPath $t
        $own = $null
        try { $own = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]) } catch { $own = $null }
        if ($null -eq $own -or $okSids -notcontains $own.Value) { $bad += "${t}: chu so huu khong phai Administrators/SYSTEM" }
        foreach ($r in $acl.Access) {
            if ([string]$r.AccessControlType -ne 'Allow') { continue }
            if (([int64]$r.FileSystemRights -band $mask) -eq 0) { continue }
            $sid = $null
            try { $sid = $r.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { $sid = $null }
            if ($null -eq $sid -or $mayWrite -notcontains $sid) { $bad += ("${t}: {0} co quyen ghi" -f $r.IdentityReference.Value) }
        }
    }
    return $bad
}
$bootAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$bootRoot = $GcsRoot.TrimEnd('\')
if ($bootAdmin -and $PSScriptRoot.StartsWith($bootRoot + '\', [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'GcsLogic.ps1'))) {
    $bootBad = @(Test-BootstrapTrusted (Join-Path $PSScriptRoot 'GcsLogic.ps1'))
    if ($bootBad.Count -gt 0) {
        Write-Host 'TU CHOI nap GcsLogic.ps1 voi quyen admin vi file/thu muc khong dang tin:' -ForegroundColor Red
        foreach ($b in $bootBad) { Write-Host "  - $b" -ForegroundColor Red }
        Write-Host 'Chay ban goc tu USB (gcs\<script>.ps1) hoac chay lai Install-Gcs.ps1; dung chay file trong C:\GCS\tools.' -ForegroundColor Yellow
        exit 1
    }
}
$logicPath = Join-Path $PSScriptRoot 'GcsLogic.ps1'
if (-not (Test-Path -LiteralPath $logicPath)) { Write-Host "LOI: thieu $logicPath (Install-Gcs.ps1 chep file nay cung Uninstall-Gcs.ps1)." -ForegroundColor Red; exit 1 }
. $logicPath
$rootProblems = @(Test-GcsRootPathValid $GcsRoot)
if ($rootProblems.Count -gt 0) { Write-Host ("LOI: -GcsRoot '{0}' khong hop le: {1}" -f $GcsRoot, ($rootProblems -join '; ')) -ForegroundColor Red; exit 2 }
$GcsRoot = ConvertTo-GcsFullPath $GcsRoot
function Add-Row([string]$Step, [string]$Status, [string]$Detail) { [void]$script:Rows.Add([pscustomobject]@{ Step = $Step; Status = $Status; Detail = $Detail }) }
function Test-Do([string]$Target, [string]$Action) { return $script:Cmdlet.ShouldProcess($Target, $Action) }
function Write-Log([string]$m) { Write-Host ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }
function Get-ActiveSchemeGuid {
    $act = (& (Get-GcsSysExe 'powercfg.exe') /getactivescheme | Out-String)
    $m = [regex]::Match($act, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    if ($m.Success) { return $m.Value }
    return $null
}

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $script:Dry) {
    Write-Host 'LOI: can quyen Administrator (mo PowerShell bang Run as administrator). Script khong tu nang quyen.' -ForegroundColor Red
    exit 2
}

$desktops = @([Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('Desktop') | Where-Object { $_ })

if (-not $StatePath) {
    $cands = @()
    $bd = Join-Path $GcsRoot 'backup'
    if (Test-Path -LiteralPath $bd) {
        $cands = @(Get-ChildItem -LiteralPath $bd -Directory | Sort-Object Name | ForEach-Object { Join-Path $_.FullName 'state.json' } | Where-Object { Test-Path -LiteralPath $_ })
    }
    if ($cands.Count -eq 0) { Write-Host "Khong tim thay state.json trong $bd - khong co gi de hoan tac." -ForegroundColor Red; exit 1 }
    $StatePath = $cands[$cands.Count - 1]
}
if (-not (Test-Path -LiteralPath $StatePath)) { Write-Host "Khong co file $StatePath" -ForegroundColor Red; exit 1 }
Write-Log "Dung state: $StatePath"

# state.json la dau vao cua script chay quyen admin: chi tin khi chu so huu/ACL dung
$trust = @(Test-GcsStateTrusted $StatePath $GcsRoot)
if ($trust.Count -gt 0) {
    Write-Host 'TU CHOI dung state.json vi khong dang tin:' -ForegroundColor Red
    foreach ($t in $trust) { Write-Host "  - $t" -ForegroundColor Red }
    Write-Host 'Neu ban chac chan file la cua minh: chay lai Install-Gcs.ps1 (sua ACL C:\GCS), hoac kiem tra thu cong roi dat chu so huu = Administrators.' -ForegroundColor Yellow
    exit 1
}
try { $st = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json }
catch { Write-Host ("LOI: state.json khong doc duoc: " + $_.Exception.Message) -ForegroundColor Red; exit 1 }
$plan = Get-GcsSanitizedState $st $GcsRoot $desktops
# state.restored*.json: nguon/tuong lua DA duoc khoi phuc o lan truoc; khoi phuc lan hai se ghi de thay doi sau do cua nguoi dung. Chi dung de -RemoveApps.
$alreadyRestored = ((Split-Path -Leaf $StatePath) -like 'state.restored*')
if ($alreadyRestored) { Write-Log 'State nay da duoc khoi phuc truoc do (state.restored*.json): bo qua khoi phuc nguon/tuong lua, chi xu ly go ung dung neu co -RemoveApps.' }
$failed = 0
foreach ($rj in $plan.Rejected) { Add-Row 'TU CHOI muc trong state' 'LOI' $rj; $failed++ }

# 1. Nguon
try {
    $guid = $plan.PowerGuid
    if ($alreadyRestored) { Add-Row 'Nguon' 'BO QUA' 'state da khoi phuc roi (state.restored)' }
    elseif ($guid -and $plan.Power.Count -gt 0) {
        $n = 0
        foreach ($p in $plan.Power) {
            if (Test-Do ("{0} {1}" -f $guid, $p.Name) ("powercfg khoi phuc AC={0} DC={1}" -f $p.Ac, $p.Dc)) {
                & (Get-GcsSysExe 'powercfg.exe') /setacvalueindex $guid $p.Sub $p.Name ([string]$p.Ac)
                if ($LASTEXITCODE -ne 0) { throw "setacvalueindex $($p.Name) loi $LASTEXITCODE" }
                & (Get-GcsSysExe 'powercfg.exe') /setdcvalueindex $guid $p.Sub $p.Name ([string]$p.Dc)
                if ($LASTEXITCODE -ne 0) { throw "setdcvalueindex $($p.Name) loi $LASTEXITCODE" }
                $n++
            }
        }
        if ($n -gt 0) {
            $detail = "Khoi phuc $n thiet lap tren scheme $guid"
            # Chi /setactive khi Install da doi scheme dang dung (state ghi scheme truoc do) va hien tai khac scheme do
            if ($plan.ActiveBefore) {
                $cur = Get-ActiveSchemeGuid
                if ($cur -and $cur -eq $plan.ActiveBefore) {
                    # scheme dang active la scheme da sua: /setactive lai de gia tri vua khoi phuc co hieu luc ngay
                    & (Get-GcsSysExe 'powercfg.exe') /setactive $plan.ActiveBefore
                    if ($LASTEXITCODE -ne 0) { throw "powercfg /setactive $($plan.ActiveBefore) loi $LASTEXITCODE" }
                    $detail += '; /setactive lai de ap dung'
                }
                if ($cur -and $cur -ne $plan.ActiveBefore) {
                    & (Get-GcsSysExe 'powercfg.exe') /setactive $plan.ActiveBefore
                    if ($LASTEXITCODE -ne 0) { throw "powercfg /setactive $($plan.ActiveBefore) loi $LASTEXITCODE" }
                    $detail += "; bat lai scheme truoc do $($plan.ActiveBefore)"
                }
            }
            Add-Row 'Nguon' 'DA LAM' $detail
        }
        else { Add-Row 'Nguon' 'SE LAM (WhatIf)' 'Khoi phuc cac gia tri powercfg goc' }
    } else { Add-Row 'Nguon' 'BO QUA' 'state.json khong co du lieu nguon hop le' }
} catch { Add-Row 'Nguon' 'LOI' $_.Exception.Message; $failed++ }

# 2. Tuong lua (chi quy tac do Install-Gcs tao; ten da kiem dung dinh dang, khong wildcard)
try {
    if ($alreadyRestored) { Add-Row 'Tuong lua' 'BO QUA' 'state da khoi phuc roi (state.restored)' }
    elseif ($plan.FirewallRules.Count -eq 0 -and $plan.FirewallModified.Count -eq 0) { Add-Row 'Tuong lua' 'BO QUA' 'Install-Gcs khong tao/sua quy tac nao' }
    foreach ($r in @(if (-not $alreadyRestored) { $plan.FirewallRules })) {
        if (Test-Do $r 'Remove-NetFirewallRule') {
            if (Get-NetFirewallRule -Name $r -ErrorAction SilentlyContinue) { Remove-NetFirewallRule -Name $r; Add-Row "Tuong lua $r" 'DA LAM' 'Da xoa' }
            else { Add-Row "Tuong lua $r" 'BO QUA' 'Khong con quy tac' }
        } else { Add-Row "Tuong lua $r" 'SE LAM (WhatIf)' 'Remove-NetFirewallRule' }
    }
    foreach ($b in @(if (-not $alreadyRestored) { $plan.FirewallModified })) {
        # Quy tac da co san truoc Install: khoi phuc cau hinh cu thay vi xoa
        if (Test-Do $b.Name ("Set-NetFirewallRule khoi phuc Profile={0} Enabled={1} Program={2} RemoteAddress={3}" -f $b.Profile, $b.Enabled, $b.Program, ($b.RemoteAddress -join ','))) {
            if (Get-NetFirewallRule -Name $b.Name -ErrorAction SilentlyContinue) {
                $profiles = @($b.Profile -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
                # giao thuc/cong/huong/hanh dong cu (Install ep ve UDP 14550-14551 Inbound Allow); state ban cu khong co thi bo qua
                $extra = @{}
                if ($b.Protocol) { $extra['Protocol'] = $b.Protocol }
                if ($b.LocalPort.Count -gt 0) { $extra['LocalPort'] = @($b.LocalPort) }
                if ($b.Direction) { $extra['Direction'] = $b.Direction }
                if ($b.Action) { $extra['Action'] = $b.Action }
                Set-NetFirewallRule -Name $b.Name -Profile $profiles -Enabled $b.Enabled -Program $b.Program -RemoteAddress $b.RemoteAddress @extra
                Add-Row "Tuong lua $($b.Name)" 'DA LAM' 'Da khoi phuc cau hinh cu'
            } else { Add-Row "Tuong lua $($b.Name)" 'BO QUA' 'Khong con quy tac' }
        } else { Add-Row "Tuong lua $($b.Name)" 'SE LAM (WhatIf)' 'Khoi phuc cau hinh cu' }
    }
} catch { Add-Row 'Tuong lua' 'LOI' $_.Exception.Message; $failed++ }

# 3. Shortcut (chi .lnk truc tiep trong Desktop cua nguoi dung hoac Public; da loc trong Get-GcsSanitizedState)
try {
    foreach ($s in $plan.Shortcuts) {
        if (Test-Path -LiteralPath $s -PathType Leaf) {
            if (Test-Do $s 'Xoa shortcut') { Remove-Item -LiteralPath $s -Force; Add-Row 'Shortcut' 'DA LAM' $s } else { Add-Row 'Shortcut' 'SE LAM (WhatIf)' $s }
        } else { Add-Row 'Shortcut' 'BO QUA' "Khong con: $s" }
    }
} catch { Add-Row 'Shortcut' 'LOI' $_.Exception.Message; $failed++ }

# 4. Go ung dung (chi voi -RemoveApps)
try {
    if (-not $RemoveApps) {
        Add-Row 'Go Mission Planner' 'BO QUA' 'Khong co -RemoveApps'
    } else {
        $mp = $plan.Mp
        if ($null -eq $mp) { Add-Row 'Go Mission Planner' 'BO QUA' 'state khong ghi Install-Gcs da cai MP (hoac muc bi tu choi)' }
        elseif (-not $mp.ByUs) { Add-Row 'Go Mission Planner' 'BO QUA' 'MP da co truoc khi chay Install-Gcs - khong go' }
        elseif ($mp.Method -eq 'msi') {
            $key = $mp.Key
            if (-not $key) { Add-Row 'Go Mission Planner' 'LOI' 'Khong co ProductCode hop le trong state. Go tay trong Settings > Apps.'; $failed++ }
            else {
                $dn = $null
                foreach ($rp in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\')) {
                    $k = Get-ItemProperty -LiteralPath ($rp + $key) -ErrorAction SilentlyContinue
                    if ($null -ne $k) { $dn = [string](Get-GcsProp $k 'DisplayName' ''); break }
                }
                if ($null -eq $dn) { Add-Row 'Go Mission Planner' 'BO QUA' "Khong thay $key trong danh sach phan mem (chua cai xong hoac da go)" }
                elseif ($dn -notlike 'Mission Planner*') { Add-Row 'Go Mission Planner' 'LOI' "Ma $key la '$dn', khong phai Mission Planner - khong go"; $failed++ }
                elseif (Test-Do $key 'msiexec /x /qn') {
                    $p = Start-Process (Get-GcsSysExe 'msiexec.exe') -ArgumentList ('/x {0} /qn /norestart' -f $key) -PassThru -Wait
                    if (@(0, 3010, 1605) -contains $p.ExitCode) { Add-Row 'Go Mission Planner' 'DA LAM' ("msiexec /x ma thoat {0}" -f $p.ExitCode) }
                    else { Add-Row 'Go Mission Planner' 'LOI' ("msiexec /x ma thoat {0}" -f $p.ExitCode); $failed++ }
                } else { Add-Row 'Go Mission Planner' 'SE LAM (WhatIf)' "msiexec /x $key /qn" }
            }
        }
        elseif ($mp.Method -eq 'zip') {
            $full = $mp.Path   # da kiem bang chinh <GcsRoot>\MissionPlanner
            if (Test-Do $full 'Xoa thu muc MP (ZIP)') { if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }; Add-Row 'Go Mission Planner' 'DA LAM' $full }
            else { Add-Row 'Go Mission Planner' 'SE LAM (WhatIf)' "Xoa $full" }
        }
        if ($plan.Apps.Count -gt 0) { Add-Row 'Go ung dung tuy chon' 'LAM TAY' ("Go bang Settings > Apps: " + ($plan.Apps -join ', ')) }
    }
} catch { Add-Row 'Go ung dung' 'LOI' $_.Exception.Message; $failed++ }

# 5. Thong tin con lai (khong tu lam)
foreach ($d in $plan.Drivers) {
    Add-Row 'Driver' 'LAM TAY' "pnputil /delete-driver $($d.Published) /uninstall  (goc: $($d.Inf))"
}
foreach ($b in @(Get-GcsProp (Get-GcsProp $st 'created' $null) 'configBackups' @())) {
    Add-Row 'Config da ghi de' 'LAM TAY' ("Ban cu nam o {0} -> chep lai ve {1} neu muon" -f ([string](Get-GcsProp $b 'backup' '') -replace '[\r\n]', ' '), ([string](Get-GcsProp $b 'original' '') -replace '[\r\n]', ' '))
}
Add-Row 'Active Hours / Windows Update' 'BO QUA' 'Install-Gcs khong thay doi, khong can hoan tac'
Add-Row 'C:\GCS, du lieu MP' 'BO QUA' 'Giu nguyen (log, backup, config, Documents\Mission Planner, ProgramData\Mission Planner)'

# 6. Danh dau state da dung de lan Install sau chup lai hien trang moi lam "original"
if ($failed -eq 0) {
    $newName = 'state.restored.json'
    $dir = Split-Path -Parent $StatePath
    if (Test-Path -LiteralPath (Join-Path $dir $newName)) { $newName = 'state.restored-{0}.json' -f (Get-Date -Format 'yyyyMMdd-HHmmss') }
    if (Test-Do $StatePath "Doi ten thanh $newName") {
        Rename-Item -LiteralPath $StatePath -NewName $newName
        Add-Row 'state.json' 'DA LAM' "Doi ten thanh $newName (go MP sau do: -StatePath <...>\$newName -RemoveApps)"
    } else { Add-Row 'state.json' 'SE LAM (WhatIf)' "Doi ten thanh $newName" }
} else { Add-Row 'state.json' 'BO QUA' 'Co loi - giu nguyen state.json de chay lai' }

$script:Rows | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
if ($script:Dry) { Write-Host 'WhatIf xong - khong co gi bi thay doi.'; exit 0 }
if ($failed -gt 0) { exit 1 }
exit 0
