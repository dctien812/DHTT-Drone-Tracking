<#
.SYNOPSIS
  Bien laptop Windows 10/11 x64 sach thanh tram mat dat (GCS) chay Mission Planner.
  Chay tren LAPTOP GCS, can quyen Administrator (script tu kiem, KHONG tu nang quyen).
  Chay khong can Internet neu gcs\packages\ da du (xem Get-GcsPackages.ps1).
  C:\GCS duoc tao nguyen tu kem chu so huu + ACL (Administrators/SYSTEM toan quyen, Users chi doc; khong thu muc nao cho Users ghi).
  Neu C:\GCS da co nhung khong dat kiem tin cay: script DUNG, khong tu doi ten/reset; nguoi dung tu doi ten/xoa bang admin roi chay lai.
  Chi chay .msi/.exe khi SHA256 khop checksums.json VA chu ky Authenticode hop le, khop ban ghi luc tai.
.PARAMETER WhatIf
  Chi in viec se lam, khong doi gi (khong can admin o che do nay).
.PARAMETER UseZip
  Dung MissionPlanner-latest.zip, giai nen vao C:\GCS\MissionPlanner thay vi cai MSI.
.PARAMETER Include
  Goi tuy chon: MAVProxy, QGC, Tailscale, Zadig, ZeroTier.
.PARAMETER SilentTimeoutMinutes
  Thoi gian toi da cho cai MSI im lang truoc khi ket thuc tien trinh msiexec client do script tao,
  cho Windows Installer roi, roi chuyen sang cai co giao dien (/passive). Mac dinh 20.
.PARAMETER InteractiveTimeoutMinutes
  Han cho cai co giao dien (msiexec /passive, bo cai .exe tuong tac). Mac dinh 60. Het han: script KHONG ket thuc
  tien trinh cai dang chay, chi bao ro va ghi vao "con phai lam tay".
.PARAMETER Force
  Cai lai Mission Planner du da co.
.PARAMETER AllowUnsigned
  CHAP NHAN RUI RO, THEO TUNG GOI: danh sach id goi (vd -AllowUnsigned missionplanner-msi,mavproxy) duoc phep chay du
  thieu checksum / chu ky so khong hop le / khong khop ban ghi luc tai, va duoc bo qua cau hoi xac nhan khi
  expectedPublisher rong. (SHA256 sai hoac nguoi ky khong khop expectedPublisher van luon bi dung.) In canh bao lon va ghi log.
.PARAMETER AllowUnverified
  Cho phep cai goi danh dau verified=false trong manifest.json (Zadig, ZeroTier...).
.PARAMETER InstallDrivers
  Cai cac driver .inf trong gcs\drivers\. Chi cai driver co .cat voi chu ky hop le; mac dinh chi liet ke.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\Install-Gcs.ps1 -WhatIf
  powershell -ExecutionPolicy Bypass -File .\Install-Gcs.ps1 -Include MAVProxy,QGC
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$UseZip,
    [string[]]$Include = @(),   # MAVProxy, QGC, Tailscale, Zadig, ZeroTier (cho phep "MAVProxy,QGC" khi goi bang -File)
    [ValidateRange(1, 240)][int]$SilentTimeoutMinutes = 20,
    [ValidateRange(1, 720)][int]$InteractiveTimeoutMinutes = 60,
    [switch]$Force,
    [string[]]$AllowUnsigned = @(),   # id goi, vd missionplanner-msi,mavproxy (cho phep "a,b" khi goi bang -File)
    [switch]$AllowUnverified,
    [switch]$InstallDrivers,
    [string]$PackageDir = '',
    [string]$GcsRoot = 'C:\GCS'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir 'GcsLogic.ps1')
$rootProblems = @(Test-GcsRootPathValid $GcsRoot)
if ($rootProblems.Count -gt 0) { Write-Host ("LOI: -GcsRoot '{0}' khong hop le: {1}" -f $GcsRoot, ($rootProblems -join '; ')) -ForegroundColor Red; exit 2 }
$GcsRoot = ConvertTo-GcsFullPath $GcsRoot
if (-not $PackageDir) { $PackageDir = Join-Path $ScriptDir 'packages' }
$Include = @($Include | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$AllowUnsigned = @($AllowUnsigned | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
foreach ($i in $Include) {
    if (@('MAVProxy', 'QGC', 'Tailscale', 'Zadig', 'ZeroTier') -notcontains $i) { throw "-Include khong hop le: '$i'. Chon trong: MAVProxy, QGC, Tailscale, Zadig, ZeroTier" }
}
$script:Cmdlet = $PSCmdlet
# Nap truoc cac module chi doc de che do -WhatIf khong in "Set Alias" cua chinh viec nap module
$wiSaved = $WhatIfPreference; $WhatIfPreference = $false
foreach ($mod in @('CimCmdlets', 'NetSecurity', 'NetConnection', 'Microsoft.PowerShell.Archive')) { Import-Module $mod -ErrorAction SilentlyContinue }
$WhatIfPreference = $wiSaved
$script:Dry = [bool]$WhatIfPreference
$script:Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$script:LogFile = Join-Path $GcsRoot ("logs\install-{0}.log" -f $script:Stamp)
$script:BackupDir = Join-Path $GcsRoot ("backup\{0}" -f $script:Stamp)
$script:Summary = New-Object System.Collections.ArrayList
$script:Manual = New-Object System.Collections.ArrayList
$script:State = $null
$script:StateFile = Join-Path $script:BackupDir 'state.json'
$script:PendingErrors = 0
$script:Pkg = @{}
$script:Manifest = $null
$script:MpExe = $null
$script:RootReady = $false
$script:Staged = @{}        # id goi -> duong dan ban chep da kiem trong <GcsRoot>\packages
$script:Confirmed = @{}     # id goi -> nguoi dung da xac nhan (de lan kiem lai ngay truoc khi chay khong hoi lai)
$script:MarkerFile = Join-Path $GcsRoot '.installed-by-gcs.json'   # dau hieu Mission Planner do bo cai nay cai (ben vung qua Uninstall)

# ---------------------------------------------------------------- tien ich
function Write-Log([string]$Msg, [string]$Level = 'INFO') {
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Msg
    $color = switch ($Level) { 'ERROR' { 'Red' } 'WARN' { 'Yellow' } 'DRY' { 'Cyan' } default { 'Gray' } }
    Write-Host $line -ForegroundColor $color
    if (-not $script:Dry) {
        Initialize-GcsRoot
        $dir = Split-Path -Parent $script:LogFile
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $newLog = -not (Test-Path -LiteralPath $script:LogFile)
        Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8
        if ($newLog) { Set-TrustedOwner $script:LogFile }
    }
}
function Add-Summary([string]$Step, [string]$Status, [string]$Detail) {
    [void]$script:Summary.Add([pscustomobject]@{ Step = $Step; Status = $Status; Detail = $Detail })
}
function Add-Manual([string]$Text) { if (@($script:Manual) -notcontains $Text) { [void]$script:Manual.Add($Text) } }
function Test-Do([string]$Target, [string]$Action) { return $script:Cmdlet.ShouldProcess($Target, $Action) }
function Get-Prop($obj, [string]$name, $default = $null) {
    if ($null -eq $obj) { return $default }
    if ($obj -is [System.Collections.IDictionary]) { if ($obj.Contains($name)) { return $obj[$name] } else { return $default } }
    $p = $obj.PSObject.Properties[$name]
    if ($null -eq $p) { return $default }
    return $p.Value
}
function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Invoke-Icacls([string[]]$IcaclsArgs, [bool]$Required = $true) {
    $out = (& (Get-GcsSysExe 'icacls.exe') @IcaclsArgs | Out-String)
    if ($LASTEXITCODE -ne 0 -and $Required) { throw ("icacls {0} loi {1}: {2}" -f ($IcaclsArgs -join ' '), $LASTEXITCODE, $out.Trim()) }
}
# Chinh sach cho thu muc goc (khong co nhanh "nhan lai"/reset; script khong doi ten, khong reset ACL, khong doc gi tu mot goc khong dat):
#  - Chua co: tao NGUYEN TU kem chu so huu + ACL (DirectorySecurity, Administrators/SYSTEM toan quyen, Users chi doc, bo thua ke),
#    roi kiem lai (chu so huu, ACL, reparse, con rong) vi CreateDirectory khong bao loi neu co ai tao truoc.
#  - Da co: chi tiep tuc khi dat kiem tin cay day du (Get-GcsRootDecision: chu so huu, ACL tung muc, khong reparse o dau) - tuc la do chinh
#    bo cai nay tao lan truoc. Khong dat: DUNG kem huong dan doi ten/xoa bang tay.
# Ngay truoc moi lan chay thu gi bang quyen admin lay tu trong goc (msiexec, bo cai .exe, Expand-Archive, Test-Gcs.ps1) goi Assert-RootTrusted.
function Assert-RootTrusted([string]$Why) {
    $pr = @(Test-GcsRootTrusted $GcsRoot)
    if ($pr.Count -gt 0) { throw ("Cay $GcsRoot khong con dang tin truoc khi ${Why} - DUNG: " + ($pr -join ' | ')) }
}
function Initialize-GcsRoot {
    if ($script:RootReady) { return }
    $script:RootReady = $true
    $exists = Test-GcsAnyExists $GcsRoot
    if ($script:Dry) {
        if ($exists) {
            $dec = Get-GcsRootDecision $GcsRoot @(Test-GcsRootTrusted $GcsRoot)
            if ($dec.Action -eq 'Stop') { Write-Log ('WhatIf: chay that se DUNG. ' + $dec.Message) 'DRY' }
        }
        return
    }
    $msgs = @()
    if ($exists) {
        $dec = Get-GcsRootDecision $GcsRoot @(Test-GcsRootTrusted $GcsRoot)
        if ($dec.Action -eq 'Stop') { throw $dec.Message }
        $msgs += , @('INFO', "$GcsRoot da co va dat kiem tin cay day du (do bo cai nay tao lan truoc): tiep tuc.")
    } else {
        $parent = Split-Path -Parent $GcsRoot
        if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw "Thu muc cha $parent chua co; script khong tu tao thu muc cha (se mang ACL mac dinh). Dung -GcsRoot truc tiep duoi goc o dia." }
        [void](New-GcsRootDirectory $GcsRoot (New-GcsRootSecurity))
        $rootProblems = @(Test-GcsRootTrusted $GcsRoot)
        if ($rootProblems.Count -gt 0) { throw ("Vua tao $GcsRoot nhung chu so huu/ACL sai (co the co tien trinh khac da tao truoc): " + ($rootProblems -join ' | ')) }
        if (@(Get-ChildItem -LiteralPath $GcsRoot -Force).Count -gt 0) { throw "$GcsRoot vua tao da co muc ben trong (co tien trinh khac ghi vao): dung." }
        $msgs += , @('INFO', "Da tao nguyen tu ${GcsRoot} kem chu so huu + ACL: Administrators/SYSTEM toan quyen, Users chi doc/chay; da kiem lai chu so huu, ACL va thu muc con rong.")
    }
    foreach ($sub in @('tools', 'backup', 'logs', 'packages')) {
        $sp = Join-Path $GcsRoot $sub
        if (-not (Test-Path -LiteralPath $sp)) { New-Item -ItemType Directory -Path $sp | Out-Null; Set-TrustedOwner $sp }
    }
    $left = @(Test-GcsTreeAcl $GcsRoot)
    if ($left.Count -gt 0) { throw ("Khong khoa duoc ACL ${GcsRoot}: " + ($left -join ' | ')) }
    foreach ($m in $msgs) { Write-Log $m[1] $m[0] }
}
function Set-TrustedOwner([string]$Path) {
    $acl = Get-Acl -LiteralPath $Path
    $own = $null
    try { $own = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]) } catch { $own = $null }
    $ok = ($null -ne $own) -and (@((Get-GcsSidString 'Admins'), (Get-GcsSidString 'System')) -contains $own.Value)
    if (-not $ok) { Invoke-Icacls @($Path, '/setowner', ('*' + (Get-GcsSidString 'Admins'))) }
}
function Save-State {
    if ($script:Dry) { return }
    Initialize-GcsRoot
    if (-not (Test-Path -LiteralPath $script:BackupDir)) { New-Item -ItemType Directory -Path $script:BackupDir -Force | Out-Null }
    ($script:State | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $script:StateFile -Encoding UTF8
    # Uninstall chi tin state.json do Administrators/SYSTEM so huu
    Set-TrustedOwner $script:BackupDir
    Set-TrustedOwner $script:StateFile
}
function Invoke-Step([string]$Name, [bool]$Required, [scriptblock]$Body) {
    Write-Log ("--- Buoc: {0}" -f $Name)
    try { & $Body }
    catch {
        $msg = $_.Exception.Message
        Write-Log ("{0} that bai: {1}" -f $Name, $msg) 'ERROR'
        Add-Summary $Name 'LOI' $msg
        if ($Required) {
            if ($script:Dry) { Write-Log 'WhatIf: buoc bat buoc se LOI khi chay that (xem tren); van chay tiep de in du ke hoach.' 'DRY'; $script:PendingErrors++ }
            else { Show-Summary; Write-Log ('DUNG vi buoc bat buoc that bai. Xem log: ' + $script:LogFile) 'ERROR'; exit 1 }
        }
    }
}
function Get-InstalledSoftware {
    $paths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $items = @(Get-ItemProperty -Path $paths -ErrorAction SilentlyContinue | Where-Object { $_.PSObject.Properties['DisplayName'] -and $_.DisplayName })
    return @($items | ForEach-Object {
        [pscustomobject]@{
            name    = $_.DisplayName
            version = (Get-Prop $_ 'DisplayVersion' '')
            key     = $_.PSChildName
        }
    })
}
function Test-AppInstalled([string]$Short) {
    $r = @(Get-InstalledSoftware | Where-Object { $_.name -like "*$($Short)*" -or ($Short -eq 'QGC' -and $_.name -like '*QGroundControl*') })
    return ($r.Count -gt 0)
}
function Get-ActiveSchemeGuid {
    $act = (& (Get-GcsSysExe 'powercfg.exe') /getactivescheme | Out-String)
    $m = [regex]::Match($act, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    if ($m.Success) { return $m.Value }
    return $null
}
function Get-PowerValues([string]$Guid) {
    $res = [ordered]@{}
    $items = @(
        @('SUB_SLEEP', 'STANDBYIDLE'), @('SUB_SLEEP', 'HIBERNATEIDLE'),
        @('SUB_VIDEO', 'VIDEOIDLE'), @('SUB_BUTTONS', 'LIDACTION')
    )
    foreach ($it in $items) {
        $out = (& (Get-GcsSysExe 'powercfg.exe') /query $Guid $it[0] $it[1] | Out-String)
        if ($LASTEXITCODE -ne 0) { $res[$it[1]] = $null; continue }
        # Khong phu thuoc ngon ngu: hai dong hex cuoi la AC roi DC
        $hex = @([regex]::Matches($out, ':\s*0x([0-9a-fA-F]{8})\s*(\r|\n|$)') | ForEach-Object { [Convert]::ToInt64($_.Groups[1].Value, 16) })
        if ($hex.Count -lt 2) { $res[$it[1]] = $null; continue }
        $res[$it[1]] = [ordered]@{ sub = $it[0]; ac = $hex[$hex.Count - 2]; dc = $hex[$hex.Count - 1] }
    }
    return $res
}
function Get-MsiProperty([string]$Path, [string]$Prop) {
    try {
        $inst = New-Object -ComObject WindowsInstaller.Installer
        $db = $inst.GetType().InvokeMember('OpenDatabase', 'InvokeMethod', $null, $inst, @($Path, 0))
        $view = $db.GetType().InvokeMember('OpenView', 'InvokeMethod', $null, $db, @("SELECT Value FROM Property WHERE Property = '$Prop'"))
        $view.GetType().InvokeMember('Execute', 'InvokeMethod', $null, $view, $null) | Out-Null
        $rec = $view.GetType().InvokeMember('Fetch', 'InvokeMethod', $null, $view, $null)
        if ($null -eq $rec) { return $null }
        return $rec.GetType().InvokeMember('StringData', 'GetProperty', $null, $rec, 1)
    } catch { return $null }
}
function Find-MissionPlannerExe {
    $c = @(
        'C:\Program Files (x86)\Mission Planner\MissionPlanner.exe',
        'C:\Program Files\Mission Planner\MissionPlanner.exe',
        (Join-Path $GcsRoot 'MissionPlanner\MissionPlanner.exe')
    )
    if ($UseZip) { $c = @($c[2], $c[0], $c[1]) }   # -UseZip: uu tien ban ZIP do chinh script giai nen
    return ($c | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)
}
function Find-QgcExe {
    $c = @('C:\Program Files\QGroundControl\QGroundControl.exe', 'C:\Program Files (x86)\QGroundControl\QGroundControl.exe')
    return ($c | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)
}
function Get-Checksums {
    $f = Join-Path $PackageDir 'checksums.json'
    $map = @{}
    if (Test-Path -LiteralPath $f) {
        try { $j = Get-Content -LiteralPath $f -Raw | ConvertFrom-Json }
        catch { throw "packages\checksums.json hong, khong doc duoc: $($_.Exception.Message)" }
        foreach ($e in @($j.packages)) { $map[$e.file] = $e }
    }
    return $map
}
# Tin cay goi: quyet dinh do Get-GcsPackageVerdict (GcsLogic.ps1). SHA256 sai hoac nguoi ky khong khop expectedPublisher = luon dung.
# Thieu checksum/chu ky khong hop le = dung, tru khi id goi nam trong -AllowUnsigned. .zip hoac chu ky hop le nhung expectedPublisher rong = hoi xac nhan.
# Khong nho ket qua: moi lan goi deu bam lai file (Get-GcsFileSha256, .NET - khong tra $null duoi -WhatIf). $Recheck = kiem lai
# ngay truoc khi chay (khong in lai, khong hoi lai; goi can xac nhan phai da duoc xac nhan o lan dau).
function Assert-PackageTrust($Pk, [string]$File, [bool]$Recheck = $false) {
    $name = [string]$Pk.file
    $id = [string]$Pk.id
    $sums = Get-Checksums
    $rec = $null
    if ($sums.ContainsKey($name)) { $rec = $sums[$name] }
    $h = ''
    if ($null -ne $rec) {
        $h = Get-GcsFileSha256 $File
        if (-not $Recheck -and [string]::Equals($h, [string]$rec.sha256, [StringComparison]::OrdinalIgnoreCase)) { Write-Log ("SHA256 khop: {0}" -f $name) }
    }
    $ext = [IO.Path]::GetExtension($File).ToLowerInvariant()
    $sig = $null
    if ($ext -eq '.msi' -or $ext -eq '.exe') {
        $sig = Get-GcsFileSignature $File
        if (-not $Recheck) { Write-Log ("Nguoi ky {0}: {1} | subject={2} | thumbprint={3}" -f $name, $sig.status, $sig.subject, $sig.thumbprint) }
    }
    $v = Get-GcsPackageVerdict $Pk $rec $h $sig $AllowUnsigned
    if ($v.Action -eq 'Stop') {
        $hint = ''
        if ($v.Message -notmatch 'KHONG the bo qua') { $hint = " Neu ban chap nhan rui ro cua RIENG goi nay, chay lai voi -AllowUnsigned $id" }
        throw ("Goi {0} khong dat kiem tin cay: {1}. DUNG goi nay.{2}" -f $name, $v.Message, $hint)
    }
    if ($Recheck) {
        if ($v.Action -eq 'Confirm' -and -not $script:Confirmed.ContainsKey($id)) { throw "Goi $name chua duoc xac nhan truoc khi chay: DUNG." }
        return
    }
    if ($v.Action -eq 'Confirm') {
        if ($script:Dry) { Write-Log ("WhatIf: se hoi xac nhan goi {0}: {1}" -f $name, $v.Message) 'DRY'; return }
        $who = 'khong co chu ky'
        if ($null -ne $sig) { $who = "{0} (thumbprint {1})" -f $sig.subject, $sig.thumbprint }
        $q = "Goi $id ($name): $($v.Message).`nNguoi ky: $who`nDoi chieu nguoi ky nay voi thong tin ban da xem luc tai goi. Chay goi nay?"
        $yes = $false
        try { $yes = $script:Cmdlet.ShouldContinue($q, "Xac nhan goi $id") } catch { $yes = $false }
        if (-not $yes) { throw "Goi $name khong duoc xac nhan (hoac khong the hoi vi chay khong tuong tac). Dien expectedPublisher trong manifest.json, hoac dung -AllowUnsigned $id sau khi tu kiem nguoi ky." }
        $script:Confirmed[$id] = $true
        Add-Manual "$id da duoc xac nhan tay (nguoi ky: $who). Dien expectedPublisher trong manifest.json de lan sau khong phai hoi."
    }
    if ($v.Action -eq 'Allow' -and $v.Allowed) {
        Write-Log '########################################################################' 'WARN'
        Write-Log ("CANH BAO: chay {0} theo -AllowUnsigned {1}. {2}" -f $name, $id, $v.Message) 'WARN'
        Write-Log '########################################################################' 'WARN'
        Add-Manual "$name chay voi -AllowUnsigned $id ($($v.Message)). Kiem tra nguon goi bang cach khac."
    }
}
# Ngay truoc MOI lan chay thu gi bang quyen admin lay tu trong goc: kiem lai ca cay (chu so huu goc, ACL, reparse), file phai nam trong
# <GcsRoot>\packages (khong bao gio chay ban tren USB), va bam lai SHA256 + chu ky cua chinh file do. Khong dat -> throw (dung).
function Assert-RunnableFromRoot($Pk, [string]$File, [string]$What) {
    if (-not (Test-GcsPathUnder $File (Join-Path $GcsRoot 'packages'))) { throw "$What : file $File khong nam trong $GcsRoot\packages - khong chay ban ngoai goc da khoa." }
    Assert-RootTrusted "chay $What"
    Assert-PackageTrust $Pk $File $true
}
# Chep goi tu USB vao <GcsRoot>\packages (chi admin ghi), kiem SHA256 + chu ky tren BAN CHEP, tra ve duong dan ban chep.
# Moi buoc chay sau do (msiexec, thu lai 1618, Expand-Archive, bo cai .exe) dung ban chep va goi Assert-RunnableFromRoot.
# WhatIf: chi kiem file nguon (doc), khong chep. Nguoi dung tra loi No cho buoc chep: DUNG (throw), khong bao gio quay lai chay ban tren USB.
function Get-StagedPackage($Pk, [string]$Src) {
    $id = [string]$Pk.id
    if ($script:Staged.ContainsKey($id)) { return $script:Staged[$id] }
    $dest = Join-Path (Join-Path $GcsRoot 'packages') ([string]$Pk.file)
    if (-not (Test-Do $dest "Chep goi $($Pk.file) vao thu muc chi admin ghi, kiem SHA256 + chu ky tren ban chep")) {
        if (-not $script:Dry) { throw "Ban khong dong y chep goi $($Pk.file) vao $GcsRoot\packages; script khong chay ban tren USB nen DUNG." }
        Assert-PackageTrust $Pk $Src
        return $Src
    }
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Force }
    Copy-Item -LiteralPath $Src -Destination $dest -Force
    Set-TrustedOwner $dest
    try { Assert-PackageTrust $Pk $dest }
    catch { Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue; throw }
    $script:Staged[$id] = $dest
    return $dest
}
function Install-Exe([string]$Path, [string]$Label, $Pk) {
    if (Test-Do $Path "Chay bo cai (tuong tac): $Label") {
        $run = Get-StagedPackage $Pk $Path
        Assert-RunnableFromRoot $Pk $run "bo cai $Label"
        Write-Log "Mo bo cai $Label - hay lam theo cua so cai dat, script cho toi da $InteractiveTimeoutMinutes phut."
        $p = Start-Process -FilePath $run -PassThru
        $null = $p.Handle
        if (-not $p.WaitForExit($InteractiveTimeoutMinutes * 60 * 1000)) {
            Write-Log ("{0}: het han {1} phut, bo cai (PID {2}) van dang chay - KHONG ket thuc no." -f $Label, $InteractiveTimeoutMinutes, $p.Id) 'WARN'
            Add-Manual ("${Label}: bo cai (PID $($p.Id)) chua xong sau $InteractiveTimeoutMinutes phut va van dang chay. Hoan tat/dong no bang tay roi chay lai Install-Gcs.ps1.")
            return [pscustomobject]@{ Ran = $true; ExitCode = $null; TimedOut = $true }
        }
        Write-Log ("{0} ket thuc, ma thoat {1}" -f $Label, $p.ExitCode)
        return [pscustomobject]@{ Ran = $true; ExitCode = $p.ExitCode; TimedOut = $false }
    }
    return [pscustomobject]@{ Ran = $false; ExitCode = $null; TimedOut = $false }
}
# Mot lan msiexec /i. Cho Windows Installer roi truoc; 1618 (dang co luot cai khac) thi cho va thu lai toi da 4 lan.
# Qua han: -KillOnTimeout (mac dinh, dung cho /qn) chi ket thuc tien trinh msiexec client do script tao (KHONG dung dich vu msiserver);
# khong co -KillOnTimeout (/passive) thi KHONG ket thuc gi, chi bao TimedOut/StillRunning.
function Invoke-MsiOnce($Pk, [string]$Msi, [string]$Mode, [string]$LogPath, [int]$TimeoutMinutes, [bool]$KillOnTimeout = $true) {
    for ($try = 1; $try -le 4; $try++) {
        if (-not (Wait-GcsMsiIdle 300)) { throw 'Windows Installer van dang ban sau 5 phut (co luot cai khac dang chay, vd Windows Update). Doi no xong hoac khoi dong lai roi chay lai.' }
        Assert-RunnableFromRoot $Pk $Msi 'msiexec'   # ngay truoc moi lan chay (ke ca thu lai 1618, /passive)
        $a = '/i "{0}" {1} /norestart /l*v "{2}"' -f $Msi, $Mode, $LogPath
        Write-Log ("msiexec " + $a)
        $p = Start-Process -FilePath (Get-GcsSysExe 'msiexec.exe') -ArgumentList $a -PassThru
        $null = $p.Handle
        if ($TimeoutMinutes -gt 0) {
            if (-not $p.WaitForExit($TimeoutMinutes * 60 * 1000)) {
                if ($KillOnTimeout) {
                    Write-Log "Qua han $TimeoutMinutes phut (co the treo vi hop thoai cai driver) - ket thuc tien trinh msiexec client do script tao (PID $($p.Id))." 'WARN'
                    & (Get-GcsSysExe 'taskkill.exe') /PID $p.Id /T /F | Out-Null
                    [void]$p.WaitForExit(30000)
                    return [pscustomobject]@{ ExitCode = $null; TimedOut = $true; StillRunning = $false; Pid = $p.Id }
                }
                Write-Log "Qua han $TimeoutMinutes phut - msiexec (PID $($p.Id)) van dang chay, KHONG ket thuc no." 'WARN'
                return [pscustomobject]@{ ExitCode = $null; TimedOut = $true; StillRunning = $true; Pid = $p.Id }
            }
        } else { $p.WaitForExit() }
        Write-Log ("msiexec {0} ma thoat {1}" -f $Mode, $p.ExitCode)
        if ($p.ExitCode -eq 1618) { Write-Log "msiexec 1618: Windows Installer dang ban, cho 30 giay roi thu lai (lan $try/4)." 'WARN'; Start-Sleep -Seconds 30; continue }
        return [pscustomobject]@{ ExitCode = $p.ExitCode; TimedOut = $false; StillRunning = $false; Pid = $p.Id }
    }
    return [pscustomobject]@{ ExitCode = 1618; TimedOut = $false; StillRunning = $false; Pid = 0 }
}
function Get-FwSnapshot([string]$Name) {
    $r = @(Get-NetFirewallRule -Name $Name -ErrorAction SilentlyContinue) | Select-Object -First 1
    if ($null -eq $r) { return $null }
    $app = Get-NetFirewallApplicationFilter -AssociatedNetFirewallRule $r
    $adr = Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $r
    $pf = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $r
    return [ordered]@{ name = $r.Name; profile = [string]$r.Profile; enabled = [string]$r.Enabled; program = [string]$app.Program; remoteAddress = @($adr.RemoteAddress | ForEach-Object { [string]$_ })
        protocol = [string]$pf.Protocol; localPort = @($pf.LocalPort | ForEach-Object { [string]$_ }); direction = [string]$r.Direction; action = [string]$r.Action }
}
# Quy tac inbound UDP 14550-14551 theo chuong trinh, chi Private, chi mang cuc bo. Co san thi luu cau hinh cu vao state de Uninstall khoi phuc.
function Set-GcsFwRule([string]$Rn, [string]$Program, [string]$Desc, [string]$Label) {
    $ex = Get-FwSnapshot $Rn
    if ($null -ne $ex) {
        $mine = (@($script:State.created.firewallRules) -contains $Rn)
        $saved = (@($script:State.created.firewallModified | Where-Object { (Get-Prop $_ 'name' '') -eq $Rn }).Count -gt 0)
        if (-not $mine -and -not $saved) {
            if (Test-Do $Rn 'Luu cau hinh cu cua quy tac vao state') { $script:State.created.firewallModified += @([pscustomobject]$ex); Save-State }
        }
        # Ep ve dung: Inbound, Allow, UDP 14550-14551 (quy tac cung ten co the da bi doi giao thuc/cong/huong/hanh dong)
        if (Test-Do $Rn "Set-NetFirewallRule Inbound Allow UDP 14550-14551 Profile=Private Program=$Program RemoteAddress=LocalSubnet") {
            Set-NetFirewallRule -Name $Rn -Direction Inbound -Action Allow -Protocol UDP -LocalPort '14550-14551' -Profile Private -Program $Program -RemoteAddress LocalSubnet -Enabled True
            Add-Summary $Label 'DA LAM' "Quy tac da co - da ep Inbound/Allow/UDP 14550-14551, Profile=Private, Program=$Program, RemoteAddress=LocalSubnet (cau hinh cu luu trong state)"
        } else { Add-Summary $Label 'SE LAM (WhatIf)' "Quy tac da co: ep Inbound/Allow/UDP 14550-14551, Profile=Private, Program=$Program, RemoteAddress=LocalSubnet" }
        return
    }
    if (Test-Do $Rn "New-NetFirewallRule Inbound UDP 14550-14551 Profile=Private Program=$Program RemoteAddress=LocalSubnet") {
        New-NetFirewallRule -Name $Rn -DisplayName $Rn -Direction Inbound -Protocol UDP -LocalPort '14550-14551' -Action Allow -Profile Private -Program $Program -RemoteAddress LocalSubnet -Enabled True -Description $Desc | Out-Null
        if (@($script:State.created.firewallRules) -notcontains $Rn) { $script:State.created.firewallRules += @($Rn) }
        Save-State
        Add-Summary $Label 'DA LAM' "$Rn (Program=$Program, LocalSubnet, Private)"
    } else { Add-Summary $Label 'SE LAM (WhatIf)' "$Rn (Inbound UDP 14550-14551, Program=$Program, LocalSubnet, CHI Private)" }
}

function Add-Done([string]$Step, [string]$Detail) {
    $st = 'DA LAM'
    if ($script:Dry) { $st = 'SE LAM (WhatIf)' }
    Add-Summary $Step $st $Detail
}
function Show-Summary {
    Write-Host ''
    Write-Host '================ TONG KET ================'
    $script:Summary | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
    $fixed = @(
        'Nap firmware lan dau qua DFU + STM32CubeProgrammer (README muc 3.1)',
        'Flash/bind ELRS va bat Backpack Telemetry = WiFi; DOI mat khau WiFi Backpack khoi mac dinh (README muc 3.2, 3.6)',
        'Prefetch ban do ngoai tuyen trong Mission Planner, can Internet (README muc 3.3)',
        'Sau khi chinh MP lan dau: luu config.xml mau vao gcs\config\MissionPlanner\ (README muc 3.4)',
        'Dat Active Hours cho Windows Update bang tay: Settings > Windows Update > Advanced options > Active hours',
        'Dat mang WiFi "ExpressLRS TX Backpack" thanh Private (quy tac tuong lua chi ap cho Private)',
        'Truoc buoi bay: bat MAVLink signing qua USB, xac nhan ARMING_SKIPCHK = 0 (checklist-truoc-bay.md)'
    )
    Write-Host '--- Con phai lam tay ---'
    foreach ($m in (@($script:Manual) + $fixed)) { Write-Host ("  [ ] " + $m) }
    if (-not $script:Dry) { Write-Host ("Log: " + $script:LogFile); Write-Host ("Trang thai hoan tac: " + $script:StateFile) }
}

# ---------------------------------------------------------------- tien kiem
$isAdmin = Test-Admin
if (-not $isAdmin) {
    if ($script:Dry) { Write-Host 'WhatIf: khong phai admin - khong sao o che do -WhatIf. Khi chay that phai mo PowerShell bang "Run as administrator".' -ForegroundColor Cyan }
    else {
        Write-Host 'LOI: can quyen Administrator. Mo PowerShell bang "Run as administrator" roi chay lai. (Script khong tu nang quyen.)' -ForegroundColor Red
        exit 2
    }
}
if ($PSVersionTable.PSVersion.Major -lt 5) { Write-Host 'Can Windows PowerShell 5.1 tro len.' -ForegroundColor Red; exit 2 }
# Khoa ACL C:\GCS truoc khi ghi bat cu thu gi (ke ca log); sai thi dung ngay
try { Initialize-GcsRoot } catch { Write-Host ("LOI: khong khoa duoc ACL {0}: {1}" -f $GcsRoot, $_.Exception.Message) -ForegroundColor Red; exit 1 }
if ($script:Dry) { Write-Log 'CHE DO -WhatIf: chi in viec se lam, khong ghi file, khong doi he thong, khong ghi log ra dia.' 'DRY' }
Write-Log ("Bat dau Install-Gcs, script {0}, user {1}, admin={2}" -f $ScriptDir, $env:USERNAME, $isAdmin)
if ($AllowUnsigned.Count -gt 0) { Write-Log ('Da bat -AllowUnsigned cho goi: ' + ($AllowUnsigned -join ', ') + ' - cac goi nay VAN SE DUOC CHAY du thieu checksum/chu ky hop le (rui ro cao).') 'WARN' }
if ($AllowUnverified) { Write-Log 'Da bat -AllowUnverified: goi verified=false trong manifest co the duoc cai.' 'WARN' }

# ---------------------------------------------------------------- a. kiem tra
$script:MsiPath = $null
$script:ZipPath = $null
Invoke-Step 'a. Kiem tra he thong va goi' $true {
    $cv = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $build = [int](Get-Prop $cv 'CurrentBuildNumber' 0)
    # Registry ProductName van ghi "Windows 10" tren Windows 11; build >= 22000 la Windows 11
    Write-Log ("OS: {0} build {1} (>= 22000 la Windows 11), kien truc OS 64-bit={2}, PROCESSOR_ARCHITECTURE={3}" -f (Get-Prop $cv 'ProductName' '?'), $build, [Environment]::Is64BitOperatingSystem, $env:PROCESSOR_ARCHITECTURE)
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Can Windows 64-bit.' }
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { throw 'May ARM64 chua duoc ho tro/khong kiem chung; can x64.' }
    if ($build -lt 10240) { throw "Build $build qua cu; can Windows 10 tro len." }
    if ($build -lt 19041) { Write-Log "Build $build la Windows 10 ban cu, nen cap nhat." 'WARN' }

    $k = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue
    $rel = Get-Prop $k 'Release' 0
    Write-Log (".NET Framework Release = {0} (can >= 461808)" -f $rel)
    if ([int]$rel -lt 461808) { throw '.NET Framework < 4.7.2. Cap nhat Windows (Windows Update) hoac cai .NET Framework 4.8 truoc.' }

    $drive = (Split-Path -Qualifier $GcsRoot)
    $free = (Get-PSDrive -Name $drive.TrimEnd(':')).Free
    Write-Log ("Trong tren {0}: {1} GB" -f $drive, [math]::Round($free / 1GB, 1))
    if ($free -lt 3GB) { throw "Chi con $([math]::Round($free/1GB,1)) GB tren $drive, can >= 3 GB." }

    # Danh sach goi can
    $script:Manifest = Get-Content -LiteralPath (Join-Path $ScriptDir 'manifest.json') -Raw | ConvertFrom-Json
    $map = @{ MAVProxy = 'mavproxy'; QGC = 'qgroundcontrol-daily' }
    $mpId = 'missionplanner-msi'
    if ($UseZip) { $mpId = 'missionplanner-zip' }
    $needIds = @($mpId)
    foreach ($i in $Include) { if ($map.ContainsKey($i)) { $needIds += $map[$i] } }
    foreach ($au in $AllowUnsigned) {
        if (@($script:Manifest.packages | Where-Object { $_.id -eq $au }).Count -eq 0) { throw "-AllowUnsigned: khong co goi id '$au' trong manifest.json" }
    }
    $sums = Get-Checksums
    if ($sums.Count -eq 0) { Write-Log 'Khong co packages\checksums.json - goi .msi/.exe se bi tu choi tru khi dung -AllowUnsigned.' 'WARN' }
    foreach ($id in $needIds) {
        $pk = @($script:Manifest.packages | Where-Object { $_.id -eq $id }) | Select-Object -First 1
        if ($null -eq $pk) { throw "Manifest khong co goi $id" }
        $f = Join-Path $PackageDir $pk.file
        if (-not (Test-Path -LiteralPath $f)) {
            if ($pk.required) { throw "Thieu goi bat buoc: $f (chay Get-GcsPackages.ps1 tren may co Internet)" }
            Write-Log "Thieu goi tuy chon $($pk.file) - se bo qua." 'WARN'; continue
        }
        # Goi bat buoc: chep vao <GcsRoot>\packages va kiem tren BAN CHEP ngay (de dung som); cac buoc sau chi dung ban chep.
        if ($pk.required) { $f = Get-StagedPackage $pk $f }
        if ($id -eq 'missionplanner-msi') { $script:MsiPath = $f }
        if ($id -eq 'missionplanner-zip') { $script:ZipPath = $f }
        $script:Pkg = $script:Pkg + @{ $id = $f }
    }
    Add-Summary 'a. Kiem tra he thong va goi' 'DA LAM' ("build {0}, .NET {1}, trong {2} GB" -f $build, $rel, [math]::Round($free / 1GB, 1))
}

# ---------------------------------------------------------------- b. luu hien trang
Invoke-Step 'b. Luu hien trang de hoan tac' $true {
    $earlier = @()
    $bdir = Join-Path $GcsRoot 'backup'
    if (Test-Path -LiteralPath $bdir) {
        $earlier = @(Get-ChildItem -LiteralPath $bdir -Directory | Sort-Object Name | ForEach-Object { Join-Path $_.FullName 'state.json' } | Where-Object { Test-Path -LiteralPath $_ })
    }
    $created = [ordered]@{ firewallRules = @(); firewallModified = @(); powerActiveBefore = $null; shortcuts = @(); mp = $null; apps = @(); drivers = @(); configBackups = @(); tools = @() }
    $original = $null
    $latest = $null
    if ($earlier.Count -gt 0) {
        $latest = $earlier[$earlier.Count - 1]
        $tp = @(Test-GcsStateTrusted $latest $GcsRoot)
        if ($tp.Count -gt 0) {
            Write-Log "Bo qua state cu $latest vi khong dang tin (se chup lai hien trang):" 'WARN'
            foreach ($t in $tp) { Write-Log "  - $t" 'WARN' }
            $latest = $null
        }
    }
    $prev = $null
    $san = $null
    if ($null -ne $latest) {
        # Moi gia tri doc tu state di vao lenh (powercfg, tuong lua) deu qua Get-GcsSanitizedState: GUID dung mau, ten thiet lap nam trong
        # danh sach script tu quan, so nguyen khong am, truong tuong lua dung dinh dang. Co gia tri khong hop le -> bo ca state cu (chup lai).
        $prev = Get-Content -LiteralPath $latest -Raw | ConvertFrom-Json
        $san = Get-GcsSanitizedState $prev $GcsRoot @([Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('Desktop') | Where-Object { $_ })
        if ($san.Rejected.Count -gt 0 -or -not $san.PowerGuid) {
            Write-Log "Bo qua state cu $latest vi co gia tri khong hop le hoac thieu power scheme (se chup lai hien trang):" 'WARN'
            foreach ($rj in $san.Rejected) { Write-Log "  - $rj" 'WARN' }
            $latest = $null
        }
    }
    if ($null -ne $latest) {
        # Chay lai: giu nguyen hien trang GOC tu lan chay dau, khong chup lai trang thai da bi doi (chi dung phan da loc)
        $pwr = [ordered]@{}
        foreach ($p in $san.Power) { $pwr[$p.Name] = [ordered]@{ sub = $p.Sub; ac = $p.Ac; dc = $p.Dc } }
        $po = Get-Prop $prev 'original' $null
        $original = [ordered]@{ capturedAt = [string](Get-Prop $po 'capturedAt' ''); powerScheme = $san.PowerGuid; power = $pwr
            firewallRulesBefore = @(Get-Prop $po 'firewallRulesBefore' @()); software = @(Get-Prop $po 'software' @()) }
        $original = ($original | ConvertTo-Json -Depth 8 | ConvertFrom-Json)
        $pc = Get-Prop $prev 'created' $null
        foreach ($k in @('drivers', 'configBackups', 'tools')) { $created[$k] = @(Get-Prop $pc $k @()) }
        $created['firewallRules'] = @($san.FirewallRules)
        $created['firewallModified'] = @($san.FirewallModified | ForEach-Object { [ordered]@{ name = $_.Name; profile = $_.Profile; enabled = $_.Enabled; program = $_.Program
            remoteAddress = @($_.RemoteAddress); protocol = $_.Protocol; localPort = @($_.LocalPort); direction = $_.Direction; action = $_.Action } })
        $created['shortcuts'] = @($san.Shortcuts)
        $created['apps'] = @($san.Apps)
        $created['mp'] = Get-Prop $pc 'mp' $null
        $created['powerActiveBefore'] = $san.ActiveBefore
        Write-Log ("Da co state truoc: {0} - dung lai hien trang goc (da loc)." -f $latest)
    } else {
        $cur = Get-ActiveSchemeGuid
        if (-not $cur) { throw 'Khong doc duoc power scheme dang dung (powercfg /getactivescheme).' }
        $fw = @(Get-NetFirewallRule -DisplayName 'GCS-DroneTracking*' -ErrorAction SilentlyContinue | ForEach-Object { [ordered]@{ name = $_.Name; profile = [string]$_.Profile; enabled = [string]$_.Enabled } })
        $original = [ordered]@{
            capturedAt = (Get-Date).ToString('s')
            powerScheme = $cur
            power = (Get-PowerValues $cur)
            firewallRulesBefore = $fw
            software = (Get-InstalledSoftware)
        }
        # Qua JSON de cung kieu doi tuong voi truong hop doc lai tu state.json
        $original = ($original | ConvertTo-Json -Depth 8 | ConvertFrom-Json)
    }
    $script:State = [ordered]@{ version = 2; runAt = (Get-Date).ToString('s'); gcsRoot = $GcsRoot; original = $original; created = $created }
    $pw = Get-Prop $original 'power' $null
    Write-Log ("Power scheme goc: {0}" -f (Get-Prop $original 'powerScheme' '?'))
    if ($pw) { Write-Log ("Gia tri nguon goc: " + (($pw | ConvertTo-Json -Compress -Depth 4))) }
    if (Test-Do $script:StateFile 'Ghi state.json (hien trang truoc khi doi)') { Save-State; Add-Done 'b. Luu hien trang de hoan tac' $script:StateFile }
    else { Add-Done 'b. Luu hien trang de hoan tac' 'powercfg, quy tac tuong lua, danh sach phan mem -> state.json' }
}

# ---------------------------------------------------------------- c. Mission Planner
Invoke-Step 'c. Mission Planner' $true {
    $sw = @(Get-InstalledSoftware | Where-Object { $_.name -like 'Mission Planner*' })
    $swBefore = @(Get-Prop $script:State.original 'software' @() | Where-Object { $_.name -like 'Mission Planner*' })
    # "Cua minh" neu truoc khi chay khong co MP, HOAC file danh dau trong C:\GCS (do admin ghi, da kiem ACL) khop ban MP dang cai
    # (de sau Uninstall roi Install lai, MP do bo cai nay cai truoc do van duoc nhan la cua minh).
    $marker = $null
    if (-not $script:Dry -and (Test-Path -LiteralPath $script:MarkerFile) -and @(Test-GcsFileTrusted $script:MarkerFile).Count -eq 0) {
        try { $marker = Get-Content -LiteralPath $script:MarkerFile -Raw | ConvertFrom-Json } catch { $marker = $null }
    }
    $byUs = ($swBefore.Count -eq 0) -or (Test-GcsMpMarkerMatches $marker $sw $false)
    if ($swBefore.Count -gt 0 -and $byUs) { Write-Log 'MP da co truoc lan chay nay nhung khop file danh dau cua bo cai: coi la do bo cai nay cai.' }
    function Write-MpMarker($Mp) {
        $obj = [ordered]@{ schema = 1; writtenAt = (Get-Date).ToString('s'); method = (Get-Prop $Mp 'method' ''); productCode = (Get-Prop $Mp 'productCode' $null); uninstallKey = (Get-Prop $Mp 'uninstallKey' $null); version = (Get-Prop $Mp 'version' '') }
        ($obj | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $script:MarkerFile -Encoding UTF8
        Set-TrustedOwner $script:MarkerFile
    }
    $exe = Find-MissionPlannerExe
    if ($UseZip) {
        if (-not $script:ZipPath) { throw 'Thieu MissionPlanner-latest.zip trong packages\.' }
        $pkZip = @($script:Manifest.packages | Where-Object { $_.id -eq 'missionplanner-zip' }) | Select-Object -First 1
        $dest = Join-Path $GcsRoot 'MissionPlanner'
        if ((Test-Path -LiteralPath (Join-Path $dest 'MissionPlanner.exe')) -and -not $Force) {
            Write-Log "Da co $dest\MissionPlanner.exe - bo qua (dung -Force de giai nen lai)."
            Add-Summary 'c. Mission Planner' 'BO QUA' 'ZIP da giai nen'
        } elseif (Test-Do $dest "Giai nen $($script:ZipPath)") {
            $zipRun = Get-StagedPackage $pkZip $script:ZipPath
            if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
            # Ghi state TRUOC khi giai nen (danh dau dang cai) de Uninstall don duoc neu hong giua chung
            $script:State.created.mp = [ordered]@{ method = 'zip'; path = $dest; byUs = $true; status = 'installing' }
            Save-State
            Assert-RunnableFromRoot $pkZip $zipRun 'Expand-Archive'
            Expand-Archive -LiteralPath $zipRun -DestinationPath $dest -Force
            if (-not (Test-Path -LiteralPath (Join-Path $dest 'MissionPlanner.exe'))) {
                # ZIP co the boc trong mot thu muc con: dua noi dung len $dest
                $subs = @(Get-ChildItem -LiteralPath $dest -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'MissionPlanner.exe') })
                if ($subs.Count -eq 1) {
                    Write-Log "ZIP co thu muc con '$($subs[0].Name)' - dua noi dung len $dest" 'WARN'
                    Get-ChildItem -LiteralPath $subs[0].FullName -Force | Move-Item -Destination $dest -Force
                    Remove-Item -LiteralPath $subs[0].FullName -Force -ErrorAction SilentlyContinue
                }
            }
            if (-not (Test-Path -LiteralPath (Join-Path $dest 'MissionPlanner.exe'))) { throw "Giai nen xong nhung khong thay MissionPlanner.exe trong $dest." }
            $script:State.created.mp['status'] = 'installed'
            Save-State
            Write-MpMarker $script:State.created.mp
            $es = Get-GcsFileSignature (Join-Path $dest 'MissionPlanner.exe')
            Write-Log ("MissionPlanner.exe (ZIP) Authenticode: {0} {1}" -f $es.status, $es.subject) 'WARN'
            $left = @(Test-GcsTreeAcl $GcsRoot)
            if ($left.Count -gt 0) { throw ("ACL sau giai nen khong an toan: " + ($left -join ' | ')) }
            Add-Done 'c. Mission Planner' "ZIP -> $dest"
        } else { Add-Done 'c. Mission Planner' "giai nen ZIP -> $dest" }
    } else {
        if (-not $script:MsiPath) { throw 'Thieu MissionPlanner-latest.msi trong packages\.' }
        $pkMsi = @($script:Manifest.packages | Where-Object { $_.id -eq 'missionplanner-msi' }) | Select-Object -First 1
        $msiVer = Get-MsiProperty $script:MsiPath 'ProductVersion'
        Write-Log ("MSI ProductVersion = {0}; da cai: {1}" -f $msiVer, (($sw | ForEach-Object { $_.name + ' ' + $_.version }) -join '; '))
        $skip = $false
        if ($sw.Count -gt 0 -and -not $Force) {
            if ($msiVer -and ($sw | Where-Object { $_.version -eq $msiVer })) { $skip = $true; Add-Summary 'c. Mission Planner' 'BO QUA' "Da cai dung ban $msiVer" }
            elseif (-not $msiVer) { $skip = $true; Add-Summary 'c. Mission Planner' 'BO QUA' 'Da cai; khong doc duoc ban trong MSI de so (dung -Force de cai de)' }
        }
        if ($skip -and $byUs -and $null -eq (Get-Prop $script:State.created 'mp' $null) -and (Test-Do $script:StateFile 'Ghi MP (do bo cai nay cai) vao state')) {
            # Bo qua cai vi da co, nhung do chinh bo cai nay cai truoc do: ghi vao state de Uninstall -RemoveApps nhan ra
            $cur = $sw | Select-Object -First 1
            $script:State.created.mp = [ordered]@{ method = 'msi'; msi = $script:MsiPath; productCode = (Get-Prop $marker 'productCode' $null); uninstallKey = (Get-Prop $cur 'key' $null); byUs = $true; version = (Get-Prop $cur 'version' ''); status = 'installed' }
            Save-State
        }
        if (-not $skip) {
            $log = Join-Path $GcsRoot ("logs\mp-msi-{0}.log" -f $script:Stamp)
            $ok = $false
            if (Test-Do $script:MsiPath "msiexec /i /qn /norestart, toi da $SilentTimeoutMinutes phut") {
                Assert-RunnableFromRoot $pkMsi $script:MsiPath 'msiexec (truoc khi ghi state)'
                if (-not (Test-Path -LiteralPath (Split-Path -Parent $log))) { New-Item -ItemType Directory -Path (Split-Path -Parent $log) -Force | Out-Null }
                # Ghi state TRUOC khi cai (danh dau dang cai + ProductCode doc tu MSI) de Uninstall don duoc neu hong giua chung
                $pcode = Get-MsiProperty $script:MsiPath 'ProductCode'
                $script:State.created.mp = [ordered]@{ method = 'msi'; msi = $script:MsiPath; productCode = $pcode; uninstallKey = $null; byUs = $byUs; status = 'installing' }
                Save-State
                $r1 = Invoke-MsiOnce $pkMsi $script:MsiPath '/qn' $log $SilentTimeoutMinutes
                if (-not $r1.TimedOut -and (@(0, 3010, 1641) -contains $r1.ExitCode)) { $ok = $true; if ($r1.ExitCode -ne 0) { Add-Manual 'Khoi dong lai Windows (msiexec tra 3010/1641).' } }
                if (-not $ok) {
                    Write-Log 'Chuyen sang cai co giao dien (/passive) sau khi Windows Installer roi. Neu co hop thoai driver, bam Install/Allow.' 'WARN'
                    $log2 = Join-Path $GcsRoot ("logs\mp-msi-passive-{0}.log" -f $script:Stamp)
                    $r2 = Invoke-MsiOnce $pkMsi $script:MsiPath '/passive' $log2 $InteractiveTimeoutMinutes $false
                    if ($r2.TimedOut) {
                        Add-Manual ("Cai MSI /passive (msiexec PID {0}) chua xong sau {1} phut va VAN DANG CHAY (script khong ket thuc no). Hoan tat/dong hop thoai cai dat, doi no xong roi chay lai Install-Gcs.ps1. Log: {2}" -f $r2.Pid, $InteractiveTimeoutMinutes, $log2)
                        throw "Cai MSI /passive qua han $InteractiveTimeoutMinutes phut; tien trinh cai dat van chay (PID $($r2.Pid)), KHONG bi ket thuc. Xem muc 'Con phai lam tay'."
                    }
                    if (@(0, 3010, 1641) -contains $r2.ExitCode) { $ok = $true; if ($r2.ExitCode -ne 0) { Add-Manual 'Khoi dong lai Windows (msiexec tra 3010/1641).' } }
                }
                if (-not $ok) { throw "Cai MSI that bai ca /qn lan /passive. Xem log trong $GcsRoot\logs\ . Thu cai tay bang MSI, hoac chay lai voi -UseZip." }
                $after = @(Get-InstalledSoftware | Where-Object { $_.name -like 'Mission Planner*' }) | Select-Object -First 1
                $key = Get-Prop $after 'key' $null
                $script:State.created.mp = [ordered]@{ method = 'msi'; msi = $script:MsiPath; productCode = $pcode; uninstallKey = $key; byUs = $byUs; version = (Get-Prop $after 'version' ''); status = 'installed' }
                Save-State
                if ($byUs) { Write-MpMarker $script:State.created.mp }
                Add-Done 'c. Mission Planner' ("MSI da cai, ban " + (Get-Prop $after 'version' '?'))
            } else { Add-Done 'c. Mission Planner' "msiexec /i /qn (toi da $SilentTimeoutMinutes phut), neu loi thi /passive" }
        }
    }
    $script:MpExe = Find-MissionPlannerExe
}

# ---------------------------------------------------------------- d. goi tuy chon
Invoke-Step 'd. Goi tuy chon' $false {
    if ($Include.Count -eq 0) { Add-Summary 'd. Goi tuy chon' 'BO QUA' 'Khong co -Include'; return }
    $manifest = $script:Manifest
    if ($null -eq $manifest) { $manifest = Get-Content -LiteralPath (Join-Path $ScriptDir 'manifest.json') -Raw | ConvertFrom-Json }
    $map = @{ MAVProxy = 'mavproxy'; QGC = 'qgroundcontrol-daily'; Tailscale = 'tailscale'; Zadig = 'zadig'; ZeroTier = 'zerotier' }
    foreach ($i in $Include) {
        $name = "d. $i"
        try {
            $pk = @($manifest.packages | Where-Object { $_.id -eq $map[$i] }) | Select-Object -First 1
            if (-not [bool](Get-Prop $pk 'verified' $false) -and -not $AllowUnverified) {
                Add-Summary $name 'BO QUA' 'Goi verified=false trong manifest: chi cai khi co -AllowUnverified'
                Add-Manual "$i chua duoc cai (verified=false); them -AllowUnverified neu ban chap nhan."
                continue
            }
            if ([bool](Get-Prop $pk 'daily' $false)) {
                Write-Log "$i la ban DAILY, KHONG DUNG DE BAY (chi du phong/tap)." 'WARN'
                Add-Manual "$i la ban DAILY, khong dung de bay."
            }
            if ($pk.install -eq 'exe-interactive') {
                $f = Join-Path $PackageDir $pk.file
                if (-not (Test-Path -LiteralPath $f)) { Add-Summary $name 'BO QUA' "Thieu $($pk.file) trong packages\"; continue }
                if (Test-AppInstalled $i) { Add-Summary $name 'BO QUA' 'Da co trong danh sach phan mem'; continue }
                $r = Install-Exe $f $pk.name $pk
                if (-not $r.Ran) { Add-Summary $name 'SE LAM (WhatIf)' 'Chay bo cai tuong tac'; continue }
                if ($r.TimedOut) { Add-Summary $name 'LAM TAY' "Het han $InteractiveTimeoutMinutes phut, bo cai van dang chay (khong bi ket thuc); hoan tat tay roi chay lai"; continue }
                # Chi ghi created.apps khi bo cai tra 0 VA phan mem da xuat hien trong danh sach
                $nowInstalled = Test-AppInstalled $i
                if ($r.ExitCode -eq 0 -and $nowInstalled) { $script:State.created.apps += @($i); Save-State; Add-Summary $name 'DA LAM' 'Bo cai tra 0 va phan mem da co trong danh sach' }
                else { Write-Log ("{0}: bo cai ma thoat {1}, co trong danh sach phan mem={2} - khong ghi vao state." -f $i, $r.ExitCode, $nowInstalled) 'WARN'; Add-Summary $name 'LOI' ("Bo cai ma thoat {0}; co trong danh sach phan mem: {1}. Kiem tra tay." -f $r.ExitCode, $nowInstalled) }
            } elseif ($pk.install -eq 'winget') {
                $wg = Get-Command winget.exe -ErrorAction SilentlyContinue
                if ($null -eq $wg) { Add-Summary $name 'BO QUA' 'Khong co winget'; Add-Manual "Cai $i bang tay (khong co winget)."; continue }
                if (-not $script:Dry) {
                    & winget.exe list --id $pk.winget -e --accept-source-agreements | Out-Null
                    if ($LASTEXITCODE -eq 0) { Add-Summary $name 'BO QUA' 'winget bao da cai'; continue }
                }
                if (Test-Do $pk.winget 'winget install (can Internet)') {
                    & winget.exe install --id $pk.winget -e --accept-package-agreements --accept-source-agreements
                    if ($LASTEXITCODE -ne 0) { throw "winget install that bai, ma $LASTEXITCODE (co the khong co Internet hoac ID sai - verified=$($pk.verified))" }
                    & winget.exe list --id $pk.winget -e --accept-source-agreements | Out-Null
                    if ($LASTEXITCODE -ne 0) { Write-Log "$i : winget install tra 0 nhung winget list khong thay goi - khong ghi vao state." 'WARN'; Add-Summary $name 'LOI' 'winget install tra 0 nhung khong thay trong winget list; kiem tra tay'; continue }
                    $script:State.created.apps += @($i); Save-State
                    Add-Summary $name 'DA LAM' "winget $($pk.winget)"
                } else { Add-Summary $name 'SE LAM (WhatIf)' "winget install $($pk.winget)" }
            }
        } catch { Write-Log ("{0} loi: {1}" -f $name, $_.Exception.Message) 'ERROR'; Add-Summary $name 'LOI' $_.Exception.Message }
    }
}

# ---------------------------------------------------------------- e. driver
Invoke-Step 'e. Driver .inf' $false {
    $dd = Join-Path $ScriptDir 'drivers'
    $infs = @()
    if (Test-Path -LiteralPath $dd) { $infs = @(Get-ChildItem -LiteralPath $dd -Filter *.inf -Recurse -File) }
    if ($infs.Count -eq 0) { Add-Summary 'e. Driver .inf' 'BO QUA' 'Khong co .inf trong gcs\drivers\ (FC STM32H7 la USB CDC, Windows tu nhan)'; return }
    foreach ($f in $infs) {
        $catName = Get-GcsInfCatalogName ([string](Get-Content -LiteralPath $f.FullName -Raw -ErrorAction SilentlyContinue))
        $catPath = $null
        if ($catName) { $cp = Join-Path $f.DirectoryName $catName; if (Test-Path -LiteralPath $cp) { $catPath = $cp } }
        $sig = $null
        $valid = $false
        if ($catPath) { $sig = Get-GcsFileSignature $catPath; $valid = ($sig.status -eq 'Valid') }
        $who = 'khong co .cat'
        if ($null -ne $sig) { $who = "{0} | {1} | {2}" -f $sig.status, $sig.subject, $sig.thumbprint }
        Write-Log ("Driver {0}: catalog={1}, chu ky .cat: {2}" -f $f.FullName, $catName, $who)
        if (-not $InstallDrivers) { Add-Summary "e. $($f.Name)" 'BO QUA' "Chua cai (can -InstallDrivers). Chu ky .cat: $who"; continue }
        if (-not $valid) { Write-Log "Bo qua driver $($f.Name): .cat khong co chu ky hop le ($who)." 'WARN'; Add-Summary "e. $($f.Name)" 'BO QUA' "Khong cai: .cat thieu/khong hop le ($who)"; continue }
        if (Test-Do $f.FullName 'pnputil /add-driver /install') {
            $out = (& (Get-GcsSysExe 'pnputil.exe') /add-driver $f.FullName /install | Out-String)
            Write-Log ($out.Trim())
            if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 3010) { Add-Summary "e. $($f.Name)" 'LOI' "pnputil ma $LASTEXITCODE"; continue }
            $pub = [regex]::Match($out, 'oem\d+\.inf').Value
            $script:State.created.drivers += @([ordered]@{ inf = $f.FullName; published = $pub; signerSubject = $sig.subject; signerThumbprint = $sig.thumbprint })
            Save-State
            Write-Log ("Da cai driver {0} (published {1}), nguoi ky {2} {3}" -f $f.Name, $pub, $sig.subject, $sig.thumbprint)
            Add-Summary "e. $($f.Name)" 'DA LAM' ("published " + $pub + "; nguoi ky " + $sig.subject)
        } else { Add-Summary "e. $($f.Name)" 'SE LAM (WhatIf)' "pnputil /add-driver /install (nguoi ky: $who)" }
    }
}

# ---------------------------------------------------------------- f. config
Invoke-Step 'f. Chep config va cong cu' $false {
    $src = Join-Path $ScriptDir 'config'
    $dst = Join-Path $GcsRoot 'config'
    $toolsDst = Join-Path $GcsRoot 'tools'
    $old = Join-Path $script:BackupDir 'overwritten'
    function Copy-WithBackup([string]$From, [string]$To) {
        $res = 'copied'
        if (Test-Path -LiteralPath $To) {
            if ((Get-GcsFileSha256 $From) -eq (Get-GcsFileSha256 $To)) { $res = 'same' }
            else {
                $bk = Join-Path $old (($To -replace '[:\\]', '_'))
                New-Item -ItemType Directory -Path (Split-Path -Parent $bk) -Force | Out-Null
                Copy-Item -LiteralPath $To -Destination $bk -Force
                $script:State.created.configBackups += @([ordered]@{ original = $To; backup = $bk })
            }
            # Xoa file dich truoc khi chep (ke ca khi noi dung giong): Copy-Item -Force de len file co san se GIU DACL/chu so huu cu
            Remove-Item -LiteralPath $To -Force
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $To) -Force | Out-Null
        Copy-Item -LiteralPath $From -Destination $To -Force
        return $res
    }
    # cong cu (GcsLogic.ps1 can cho Uninstall-Gcs.ps1 va Test-Gcs.ps1)
    foreach ($t in @('Test-Gcs.ps1', 'Uninstall-Gcs.ps1', 'GcsLogic.ps1')) {
        $s = Join-Path $ScriptDir $t
        if (-not (Test-Path -LiteralPath $s)) { Write-Log "Thieu $s" 'WARN'; continue }
        if (Test-Do (Join-Path $toolsDst $t) "Chep $t") {
            [void](Copy-WithBackup $s (Join-Path $toolsDst $t))
            $script:State.created.tools += @($t)
            # Kiem chu so huu + ACL cua TUNG file vua chep (va thu muc chua no)
            $fp = @(Test-GcsFileTrusted (Join-Path $toolsDst $t))
            if ($fp.Count -gt 0) { throw ("File cong cu khong dang tin sau khi chep: " + ($fp -join ' | ')) }
        }
    }
    # config chung (tru MissionPlanner\ va gmapcache\); so sanh duong dan khong wildcard
    $n = 0
    if (Test-Path -LiteralPath $src) {
        $files = @(Get-ChildItem -LiteralPath $src -File -Recurse | Where-Object { -not (Test-GcsPathUnder $_.FullName (Join-Path $src 'MissionPlanner')) -and -not (Test-GcsPathUnder $_.FullName (Join-Path $src 'gmapcache')) })
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($src.Length).TrimStart('\')
            $n++
            if (Test-Do (Join-Path $dst $rel) 'Chep file config') { [void](Copy-WithBackup $f.FullName (Join-Path $dst $rel)) }
        }
    }
    # config.xml cua Mission Planner (chi khi nguoi dung dat file mau). LUU Y: Documents cua tai khoan chay script nay (admin),
    # khong phai tai khoan thuong se dung de bay - xem README.
    $cx = Join-Path $src 'MissionPlanner\config.xml'
    $docs = [Environment]::GetFolderPath('MyDocuments')
    if (Test-Path -LiteralPath $cx) {
        $target = Join-Path $docs 'Mission Planner\config.xml'
        if (@(Get-Process -Name MissionPlanner -ErrorAction SilentlyContinue).Count -gt 0) { Write-Log 'Mission Planner dang chay - khong ghi de config.xml.' 'WARN'; Add-Manual 'Dong Mission Planner roi chep lai config.xml mau.' }
        elseif (Test-Do $target 'Ghi config.xml mau (sao luu ban cu truoc)') { Write-Log ("config.xml: " + (Copy-WithBackup $cx $target)) }
        Add-Manual "config.xml mau da chep vao Documents cua tai khoan '$env:USERNAME' (tai khoan admin chay bo cai). Neu bay bang tai khoan khac, chep config.xml vao Documents\Mission Planner\ cua tai khoan do."
    } else { Add-Manual 'Chua co config\MissionPlanner\config.xml mau (tao sau khi chinh MP lan dau).' }
    # gmapcache
    $gm = Join-Path $src 'gmapcache'
    if ((Test-Path -LiteralPath $gm) -and @(Get-ChildItem -LiteralPath $gm -Recurse -File -ErrorAction SilentlyContinue).Count -gt 0) {
        $gt = 'C:\ProgramData\Mission Planner\gmapcache'
        if (Test-Do $gt 'robocopy gmapcache (khong xoa file co san)') {
            & (Get-GcsSysExe 'robocopy.exe') $gm $gt /E /XO /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
            if ($LASTEXITCODE -ge 8) { throw "robocopy gmapcache loi, ma $LASTEXITCODE" }
            Write-Log 'Da chep gmapcache.'
        }
    } else { Add-Manual 'Chua co ban do ngoai tuyen (config\gmapcache\) - prefetch trong MP khi co Internet.' }
    Save-State
    if (-not $script:Dry) {
        $left = @(Test-GcsTreeAcl $GcsRoot)   # gom ca file trong tools\ va config\
        if ($left.Count -gt 0) { throw ("Cay $GcsRoot khong an toan sau khi chep: " + ($left -join ' | ')) }
    }
    Add-Done 'f. Chep config va cong cu' ("{0} file config, cong cu vao {1}" -f $n, $toolsDst)
}

# ---------------------------------------------------------------- g. thiet lap may ra san
Invoke-Step 'g1. Nguon (powercfg)' $true {
    $guid = Get-Prop $script:State.original 'powerScheme' $null
    if (-not $guid) { throw 'Khong co power scheme trong state.' }
    if ([string]$guid -notmatch '^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$') { throw 'Power scheme khong dung dinh dang GUID.' }
    $pw = Get-Prop $script:State.original 'power' $null
    $changed = @()
    foreach ($p in $pw.PSObject.Properties) {
        if ($null -eq $p.Value) { Write-Log ("Bo qua {0}: may khong co thiet lap." -f $p.Name) 'WARN'; continue }
        $sub = $p.Value.sub
        if (Test-Do ("{0} {1}" -f $guid, $p.Name) 'powercfg set AC=0 DC=0') {
            & (Get-GcsSysExe 'powercfg.exe') /setacvalueindex $guid $sub $p.Name 0
            if ($LASTEXITCODE -ne 0) { throw "powercfg /setacvalueindex $($p.Name) loi $LASTEXITCODE" }
            & (Get-GcsSysExe 'powercfg.exe') /setdcvalueindex $guid $sub $p.Name 0
            if ($LASTEXITCODE -ne 0) { throw "powercfg /setdcvalueindex $($p.Name) loi $LASTEXITCODE" }
            $changed += $p.Name
        }
    }
    if ($changed.Count -gt 0) {
        $cur = Get-ActiveSchemeGuid
        $note = ''
        # Luon luu scheme dang dung truoc do roi LUON /setactive: gia tri vua sua co the chua ap dung neu scheme do dang active
        # (vo hai khi scheme da active).
        if ($cur -and -not (Get-Prop $script:State.created 'powerActiveBefore' $null)) { $script:State.created['powerActiveBefore'] = $cur; Save-State }
        if (Test-Do $guid 'powercfg /setactive (ap dung gia tri vua sua)') {
            & (Get-GcsSysExe 'powercfg.exe') /setactive $guid
            if ($LASTEXITCODE -ne 0) { throw "powercfg /setactive loi $LASTEXITCODE" }
            $note = "; da /setactive $guid (truoc do dang dung $cur, luu trong state)"
        }
        Add-Done 'g1. Nguon (powercfg)' ("AC=0 DC=0: " + ($changed -join ', ') + $note)
    } else {
        $names = @($pw.PSObject.Properties | Where-Object { $null -ne $_.Value } | ForEach-Object { $_.Name })
        Add-Done 'g1. Nguon (powercfg)' (($names -join ', ') + ' = 0 cho ca AC va DC, roi powercfg /setactive ' + $guid + ' (may khong co thiet lap nao khac thi bo qua)')
    }
    Add-Manual 'May dung Modern Standby (S0): kiem tra them Settings > System > Power; nen thu tren ban (CHUA kiem chung).'
}
Invoke-Step 'g2. Tuong lua UDP 14550-14551 (Private, theo chuong trinh)' $true {
    $mp = $script:MpExe
    if (-not $mp) {
        if ($script:Dry) { $mp = 'C:\Program Files (x86)\Mission Planner\MissionPlanner.exe'; if ($UseZip) { $mp = Join-Path $GcsRoot 'MissionPlanner\MissionPlanner.exe' }; Write-Log "WhatIf: chua co MissionPlanner.exe, dung duong dan mac dinh $mp" 'DRY' }
        else { throw 'Khong thay MissionPlanner.exe de gan quy tac tuong lua theo chuong trinh (khong mo cong cho moi chuong trinh).' }
    }
    Set-GcsFwRule 'GCS-DroneTracking-MAVLink-UDP-14550-14551' $mp 'MAVLink UDP cho Mission Planner (Drone-Tracking GCS). Chi mang Private, chi mang cuc bo, chi MissionPlanner.exe.' 'g2. Tuong lua Mission Planner'
    if ($Include -contains 'QGC') {
        $q = Find-QgcExe
        if (-not $q -and $script:Dry) { $q = 'C:\Program Files\QGroundControl\QGroundControl.exe' }
        if ($q) { Set-GcsFwRule 'GCS-DroneTracking-QGC-UDP-14550-14551' $q 'MAVLink UDP cho QGroundControl (Drone-Tracking GCS). Chi mang Private, chi mang cuc bo, chi QGroundControl.exe.' 'g2. Tuong lua QGC' }
        else { Add-Manual 'QGC chua co quy tac tuong lua: khong thay QGroundControl.exe (cai xong roi chay lai Install-Gcs.ps1 -Include QGC).' }
    }
}
Add-Summary 'g3. Active Hours Windows Update' 'LAM TAY' 'Khong tu dat de tranh doan khoa registry khong tai lieu'
Write-Log 'Active Hours: Settings > Windows Update > Advanced options > Active hours, chon khung gio bay (toi da 18 gio). Hoac Pause updates trong ngay bay.' 'WARN'

# ---------------------------------------------------------------- h. shortcut
Invoke-Step 'h. Shortcut Desktop' $false {
    # Public Desktop de tai khoan thuong (dung de bay) cung thay; Uninstall chi xoa .lnk trong Public/User Desktop
    $desk = [Environment]::GetFolderPath('CommonDesktopDirectory')
    try {
        $dp = @(Test-GcsAclSafe (Get-Acl -LiteralPath $desk) $false)
        if ($dp.Count -gt 0) { Add-Manual ("Public Desktop ($desk) cho tai khoan ngoai Administrators/SYSTEM quyen ghi: " + ($dp -join '; ') + ' -> shortcut co the bi doi tro sang file khac. Script KHONG tu doi ACL Desktop; kiem tra shortcut truoc khi bay.') }
    } catch { Write-Log ("Khong doc duoc ACL Public Desktop: " + $_.Exception.Message) 'WARN' }
    $mp = $script:MpExe
    $list = @()
    if ($mp) { $list += @([ordered]@{ name = 'GCS - Mission Planner.lnk'; target = $mp; args = ''; wd = (Split-Path -Parent $mp) }) }
    else { Write-Log 'Chua co MissionPlanner.exe - bo shortcut MP.' 'WARN' }
    $list += @([ordered]@{ name = 'GCS - Thu muc C-GCS.lnk'; target = $GcsRoot; args = ''; wd = $GcsRoot })
    $rootArg = ''
    if (-not (Test-GcsPathEqual $GcsRoot 'C:\GCS')) { $rootArg = ' -GcsRoot "{0}"' -f $GcsRoot }   # goc khac mac dinh: Test-Gcs phai biet
    $list += @([ordered]@{ name = 'GCS - Test-Gcs.lnk'; target = (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'); args = ('-NoProfile -ExecutionPolicy Bypass -NoExit -File "{0}" -ListenSeconds 10{1}' -f (Join-Path $GcsRoot 'tools\Test-Gcs.ps1'), $rootArg); wd = $GcsRoot })
    $made = 0
    foreach ($s in $list) {
        $lnk = Join-Path $desk $s.name
        if (Test-Do $lnk 'Tao shortcut') {
            $ws = New-Object -ComObject WScript.Shell
            $sc = $ws.CreateShortcut($lnk)
            $sc.TargetPath = $s.target; $sc.Arguments = $s.args; $sc.WorkingDirectory = $s.wd
            $sc.Save()
            if ($script:State.created.shortcuts -notcontains $lnk) { $script:State.created.shortcuts += @($lnk) }
            $made++
        }
    }
    Save-State
    Add-Done 'h. Shortcut Desktop' ("{0} shortcut tren {1}" -f $list.Count, $desk)
}

# ---------------------------------------------------------------- i. kiem tra sau cai
Invoke-Step 'i. Test-Gcs.ps1' $false {
    # Chay bang quyen admin ban trong <GcsRoot>\tools: ngay truoc khi chay kiem lai ca cay + tung file; khong dat thi DUNG (khong chay ban nao khac).
    $t = Join-Path $GcsRoot 'tools\Test-Gcs.ps1'
    if (-not $script:Dry) {
        Assert-RootTrusted 'chay Test-Gcs.ps1'
        $tp = @(Test-GcsFileTrusted $t) + @(Test-GcsFileTrusted (Join-Path $GcsRoot 'tools\GcsLogic.ps1'))
        if ($tp.Count -gt 0) { throw ('Test-Gcs.ps1/GcsLogic.ps1 trong tools khong dang tin, khong chay: ' + ($tp -join ' | ')) }
    }
    if (Test-Do $t 'Chay Test-Gcs.ps1') {
        $out = (& (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -NoProfile -ExecutionPolicy Bypass -File $t -GcsRoot $GcsRoot | Out-String)
        $code = $LASTEXITCODE
        Write-Log $out
        if ($code -eq 0) { Add-Summary 'i. Test-Gcs.ps1' 'DA LAM' 'Khong co FAIL' }
        else { Add-Summary 'i. Test-Gcs.ps1' 'LOI' 'Test-Gcs co FAIL (xem log phia tren)' }
    } else { Add-Summary 'i. Test-Gcs.ps1' 'SE LAM (WhatIf)' $t }
}

Show-Summary
$errs = @($script:Summary | Where-Object { $_.Status -eq 'LOI' }).Count
if ($script:Dry) { Write-Log ("WhatIf xong. Khong co gi bi thay doi. So muc se LOI neu chay that: {0}" -f $errs) 'DRY'; exit 0 }
if ($errs -gt 0) { exit 1 }
exit 0
