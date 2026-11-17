<#
.SYNOPSIS
  Kiem tra sau cai dat tram mat dat (GCS). Khong can admin. Chi doc, khong doi gi.
  Moi dong: PASS / FAIL / WARN. Exit code 1 neu co FAIL.
.PARAMETER ListenSeconds
  Neu > 0: nghe UDP tren -Port trong so giay nay va dem goi MAVLink nhan duoc.
.PARAMETER Port
  Cong UDP MAVLink (mac dinh 14550).
.PARAMETER GcsRoot
  Thu muc cai (mac dinh C:\GCS); kiem ACL o day.
#>
[CmdletBinding()]
param(
    [int]$ListenSeconds = 0,
    [int]$Port = 14550,
    [string]$GcsRoot = 'C:\GCS'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
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
if (-not (Test-Path -LiteralPath $logicPath)) { Write-Host "LOI: thieu $logicPath" -ForegroundColor Red; exit 1 }
. $logicPath
$rootProblems = @(Test-GcsRootPathValid $GcsRoot)
if ($rootProblems.Count -gt 0) { Write-Host ("LOI: -GcsRoot '{0}' khong hop le: {1}" -f $GcsRoot, ($rootProblems -join '; ')) -ForegroundColor Red; exit 2 }
$GcsRoot = ConvertTo-GcsFullPath $GcsRoot

$script:Results = New-Object System.Collections.ArrayList
function Add-Result([string]$Level, [string]$Name, [string]$Detail) {
    [void]$script:Results.Add([pscustomobject]@{ Level = $Level; Check = $Name; Detail = $Detail })
    $color = switch ($Level) { 'PASS' { 'Green' } 'FAIL' { 'Red' } default { 'Yellow' } }
    Write-Host ("[{0}] {1}: {2}" -f $Level, $Name, $Detail) -ForegroundColor $color
}
function Try-Check([string]$Name, [scriptblock]$Body) {
    try { & $Body } catch { Add-Result 'FAIL' $Name ("Loi khi kiem: " + $_.Exception.Message) }
}

Write-Host "=== Test-Gcs $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# 1. Mission Planner
Try-Check 'Mission Planner' {
    $cands = @(
        'C:\Program Files (x86)\Mission Planner\MissionPlanner.exe',
        'C:\Program Files\Mission Planner\MissionPlanner.exe',
        (Join-Path $GcsRoot 'MissionPlanner\MissionPlanner.exe')
    )
    $found = $cands | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($found) {
        $v = (Get-Item -LiteralPath $found).VersionInfo
        Add-Result 'PASS' 'Mission Planner' ("{0} (file version {1})" -f $found, $v.FileVersion)
    } else {
        Add-Result 'FAIL' 'Mission Planner' 'Khong thay MissionPlanner.exe o cac duong dan thuong gap'
    }
}

# 2. .NET Framework
Try-Check '.NET Framework' {
    $k = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue
    if ($null -eq $k -or -not $k.PSObject.Properties['Release']) { Add-Result 'FAIL' '.NET Framework' 'Khong doc duoc Release trong registry'; return }
    if ([int]$k.Release -ge 461808) { Add-Result 'PASS' '.NET Framework' ("Release {0} (>= 461808, tuong ung 4.7.2)" -f $k.Release) }
    else { Add-Result 'FAIL' '.NET Framework' ("Release {0} < 461808, can .NET Framework 4.7.2 tro len" -f $k.Release) }
}

# 3. Tuong lua
Try-Check 'Tuong lua' {
    $rules = @(Get-NetFirewallRule -DisplayName 'GCS-DroneTracking*' -ErrorAction SilentlyContinue)
    if ($rules.Count -eq 0) { Add-Result 'FAIL' 'Tuong lua' 'Khong co quy tac GCS-DroneTracking*'; return }
    foreach ($r in $rules) {
        $pf = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $r
        $app = Get-NetFirewallApplicationFilter -AssociatedNetFirewallRule $r
        $adr = Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $r
        $prof = [string]$r.Profile
        $ok = ($r.Enabled.ToString() -eq 'True') -and ($r.Direction.ToString() -eq 'Inbound') -and ($prof -eq 'Private')
        $detail = "{0}: Enabled={1} Dir={2} Profile={3} Proto={4} Port={5} Program={6} Remote={7}" -f $r.DisplayName, $r.Enabled, $r.Direction, $prof, $pf.Protocol, $pf.LocalPort, $app.Program, (@($adr.RemoteAddress) -join ',')
        if ($ok) { Add-Result 'PASS' 'Tuong lua' $detail } else { Add-Result 'FAIL' 'Tuong lua' ($detail + ' (phai la Inbound, Private, Enabled)') }
        if ([string]$app.Program -eq 'Any') { Add-Result 'WARN' 'Tuong lua' ("{0}: khong gan theo chuong trinh (Program=Any); chay lai Install-Gcs.ps1" -f $r.DisplayName) }
    }
    # Bat ky quy tac inbound Allow nao cho MissionPlanner.exe bat o profile Public (vd Windows tu tao khi bam Allow) = lo ra mang cong cong
    $exposed = @()
    foreach ($a in @(Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue | Where-Object { [string]$_.Program -like '*\MissionPlanner.exe' })) {
        $rr = @(Get-NetFirewallRule -AssociatedNetFirewallApplicationFilter $a -ErrorAction SilentlyContinue)
        foreach ($x in $rr) {
            if (Test-GcsFirewallRulePublicInbound ([string]$x.Enabled) ([string]$x.Direction) ([string]$x.Action) ([string]$x.Profile)) { $exposed += ("{0} [{1}] Profile={2}" -f $x.DisplayName, $x.Name, $x.Profile) }
        }
    }
    if ($exposed.Count -gt 0) { Add-Result 'FAIL' 'Tuong lua Public' ("Quy tac inbound cho MissionPlanner.exe dang bat o profile Public: " + ($exposed -join ' | ') + ' - tat/xoa hoac bo Public khoi quy tac') }
    else { Add-Result 'PASS' 'Tuong lua Public' 'Khong co quy tac inbound cho MissionPlanner.exe bat o profile Public' }
    # Mang hien tai co phai Private khong
    $np = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue)
    foreach ($n in $np) {
        if ($n.NetworkCategory.ToString() -ne 'Private') {
            Add-Result 'WARN' 'Tuong lua' ("Mang '{0}' dang la {1}; quy tac chi ap dung cho Private. Neu la WiFi Backpack, dat mang do thanh Private." -f $n.Name, $n.NetworkCategory)
        } else {
            Add-Result 'PASS' 'Tuong lua' ("Mang '{0}' la Private" -f $n.Name)
        }
    }
}

# 3b. ACL C:\GCS (Users/Authenticated Users khong duoc ghi vao goc, tools, backup, MissionPlanner; chu so huu Administrators/SYSTEM)
Try-Check 'ACL C:\GCS' {
    if (-not (Test-Path -LiteralPath $GcsRoot)) { Add-Result 'WARN' 'ACL C:\GCS' "Khong co $GcsRoot (chua cai?)"; return }
    $p = @(Test-GcsTreeAcl $GcsRoot)
    if ($p.Count -eq 0) { Add-Result 'PASS' 'ACL C:\GCS' "Chi Administrators/SYSTEM ghi duoc, chu so huu dung, khong co reparse point (ca thu muc lan file) trong $GcsRoot" }
    else { foreach ($x in $p) { Add-Result 'FAIL' 'ACL C:\GCS' ($x + ' - doi ten hoac xoa thu muc C:\GCS bang tai khoan admin roi chay lai Install-Gcs.ps1 (script khong tu doi ten/reset)') } }
}

# 4. Thiet lap nguon
Try-Check 'Nguon' {
    $act = (& (Get-GcsSysExe 'powercfg.exe') /getactivescheme | Out-String)
    $m = [regex]::Match($act, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    if (-not $m.Success) { Add-Result 'WARN' 'Nguon' 'Khong doc duoc scheme dang dung'; return }
    $items = @(
        @('SUB_SLEEP', 'STANDBYIDLE', 'Ngu sau (giay)'),
        @('SUB_SLEEP', 'HIBERNATEIDLE', 'Hibernate sau (giay)'),
        @('SUB_VIDEO', 'VIDEOIDLE', 'Tat man hinh sau (giay)'),
        @('SUB_BUTTONS', 'LIDACTION', 'Dong nap (0 = khong lam gi)')
    )
    foreach ($it in $items) {
        $out = (& (Get-GcsSysExe 'powercfg.exe') /query $m.Value $it[0] $it[1] | Out-String)
        if ($LASTEXITCODE -ne 0) { Add-Result 'WARN' 'Nguon' ("{0}: may khong co thiet lap nay" -f $it[2]); continue }
        $hex = @([regex]::Matches($out, ':\s*0x([0-9a-fA-F]{8})\s*(\r|\n|$)') | ForEach-Object { [Convert]::ToInt64($_.Groups[1].Value, 16) })
        if ($hex.Count -lt 2) { Add-Result 'WARN' 'Nguon' ("{0}: khong doc duoc" -f $it[2]); continue }
        $ac = $hex[$hex.Count - 2]; $dc = $hex[$hex.Count - 1]
        if ($ac -eq 0 -and $dc -eq 0) { Add-Result 'PASS' 'Nguon' ("{0}: AC=0 DC=0" -f $it[2]) }
        else { Add-Result 'FAIL' 'Nguon' ("{0}: AC={1} DC={2} (can 0/0 de ra san)" -f $it[2], $ac, $dc) }
    }
}

# 5. Cong COM
Try-Check 'Cong COM' {
    $devs = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match '\(COM\d+\)' })
    if ($devs.Count -eq 0) { Add-Result 'WARN' 'Cong COM' 'Khong co cong noi tiep nao (binh thuong neu dung WiFi/UDP)'; return }
    foreach ($d in $devs) {
        $vp = [regex]::Match([string]$d.PNPDeviceID, 'VID_([0-9A-F]{4}).PID_([0-9A-F]{4})')
        $ids = 'VID/PID khong co'
        if ($vp.Success) { $ids = "VID_{0} PID_{1}" -f $vp.Groups[1].Value, $vp.Groups[2].Value }
        Add-Result 'PASS' 'Cong COM' ("{0} [{1}]" -f $d.Name, $ids)
    }
}

# 6. Nghe UDP
if ($ListenSeconds -gt 0) {
    # Phep thu nay mo socket bang powershell.exe, KHONG phai MissionPlanner.exe: quy tac tuong lua theo chuong trinh se khong cho goi
    # di qua, nen "khong nhan goi" CO THE chi la tuong lua chan (chi WARN, khong FAIL). Dong Mission Planner truoc khi thu.
    Write-Host 'Luu y: phep nghe UDP can DONG Mission Planner (no giu cong) va co the bi tuong lua chan vi quy tac cho phep gan theo MissionPlanner.exe, khong phai powershell.exe. Ket qua khong nhan goi chi la WARN.' -ForegroundColor Yellow
    Try-Check 'UDP' {
        $udp = $null
        try { $udp = New-Object System.Net.Sockets.UdpClient($Port) }
        catch { Add-Result 'WARN' "UDP $Port" ("Khong bind duoc (co the Mission Planner dang giu cong): " + $_.Exception.Message); return }
        try {
            $deadline = (Get-Date).AddSeconds($ListenSeconds)
            $n = 0; $mav = 0; $src = ''
            Write-Host ("Dang nghe UDP {0} trong {1}s ..." -f $Port, $ListenSeconds)
            while ((Get-Date) -lt $deadline) {
                if ($udp.Available -gt 0) {
                    $ep = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
                    $buf = $udp.Receive([ref]$ep)
                    $n++; $src = $ep.Address.ToString()
                    if ($buf.Length -gt 0 -and ($buf[0] -eq 0xFD -or $buf[0] -eq 0xFE)) { $mav++ }
                } else { Start-Sleep -Milliseconds 50 }
            }
            if ($mav -gt 0) { Add-Result 'PASS' "UDP $Port" ("Nhan {0} goi, {1} giong MAVLink, nguon {2}" -f $n, $mav, $src) }
            elseif ($n -gt 0) { Add-Result 'WARN' "UDP $Port" ("Nhan {0} goi nhung khong giong MAVLink" -f $n) }
            else { Add-Result 'WARN' "UDP $Port" ("Khong nhan goi nao trong {0}s (co the do tuong lua chan powershell.exe, hoac chua co nguon MAVLink; thu trong Mission Planner)" -f $ListenSeconds) }
        } finally { $udp.Close() }
    }
} else {
    Add-Result 'WARN' "UDP $Port" 'Bo qua (dung -ListenSeconds N de nghe)'
}

# 7. gmapcache
Try-Check 'gmapcache' {
    $dir = 'C:\ProgramData\Mission Planner\gmapcache'
    if (-not (Test-Path -LiteralPath $dir)) { Add-Result 'WARN' 'gmapcache' "Chua co $dir (chua prefetch ban do ngoai tuyen)"; return }
    $sum = (Get-ChildItem -LiteralPath $dir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { $sum = 0 }
    $mb = [math]::Round($sum / 1MB, 1)
    if ($mb -lt 1) { Add-Result 'WARN' 'gmapcache' ("{0} MB (gan nhu rong)" -f $mb) } else { Add-Result 'PASS' 'gmapcache' ("{0} MB" -f $mb) }
}

# 8. Dong ho he thong
Try-Check 'Dong ho' {
    $now = Get-Date
    $tz = (Get-TimeZone).Id
    $svc = Get-Service -Name w32time -ErrorAction SilentlyContinue
    $svcs = 'khong co dich vu w32time'
    if ($null -ne $svc) { $svcs = "w32time=" + $svc.Status }
    $detail = "{0} ({1}), UTC {2}, {3}" -f $now.ToString('yyyy-MM-dd HH:mm:ss'), $tz, $now.ToUniversalTime().ToString('HH:mm:ss'), $svcs
    # Khong co moc nam cung: so voi thoi gian ghi cua chinh script nay (khong the som hon ngay script duoc viet/chep)
    $ref = (Get-Item -LiteralPath $PSCommandPath).LastWriteTime
    if ((Get-GcsClockVerdict $now $ref) -eq 'SUSPECT') { Add-Result 'WARN' 'Dong ho' ($detail + (' - dong ho som hon thoi gian file script ({0}), nhieu kha nang pin CMOS/RTC sai; DAT LAI dong ho truoc khi bay' -f $ref.ToString('yyyy-MM-dd HH:mm'))) }
    else { Add-Result 'WARN' 'Dong ho' ($detail + ' - doi chieu bang mat voi dong ho dung truoc khi bay') }
}

$fail = @($script:Results | Where-Object { $_.Level -eq 'FAIL' }).Count
$warn = @($script:Results | Where-Object { $_.Level -eq 'WARN' }).Count
$pass = @($script:Results | Where-Object { $_.Level -eq 'PASS' }).Count
Write-Host ("=== Tong: PASS={0} WARN={1} FAIL={2} ===" -f $pass, $warn, $fail)
if ($fail -gt 0) { exit 1 }
exit 0
