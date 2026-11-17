<#
.SYNOPSIS
  Kiem cac ham thuan logic trong GcsLogic.ps1. Khong can admin, khong doi he thong:
  chi tao/xoa thu muc tam trong $env:TEMP va doi tuong ACL trong bo nho.
  Exit code 1 neu co ca kiem that bai.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'GcsLogic.ps1')

$script:Pass = 0; $script:Fail = 0
function Assert-Eq($Actual, $Expected, [string]$Name) {
    if ($Actual -eq $Expected) { $script:Pass++; Write-Host "[PASS] $Name" -ForegroundColor Green }
    else { $script:Fail++; Write-Host "[FAIL] $Name : mong doi '$Expected', nhan '$Actual'" -ForegroundColor Red }
}
function New-Acl([string]$OwnerSid, $Aces) {
    $a = New-Object System.Security.AccessControl.DirectorySecurity
    if ($OwnerSid) { $a.SetOwner((New-Object System.Security.Principal.SecurityIdentifier($OwnerSid))) }
    foreach ($e in $Aces) {
        $sid = New-Object System.Security.Principal.SecurityIdentifier($e[0])
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, $e[1], 'ContainerInherit,ObjectInherit', 'None', $e[2])
        $a.AddAccessRule($rule)
    }
    return $a
}

$tmp = Join-Path $env:TEMP ('gcs-logic-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $root = 'C:\GCS'
    $desk = @('C:\Users\Public\Desktop', 'C:\Users\Bob\Desktop')

    # --- duong dan / shortcut
    Assert-Eq (ConvertTo-GcsFullPath 'C:\GCS\..\Windows\notepad.exe') 'C:\Windows\notepad.exe' 'chuan hoa ..'
    Assert-Eq ($null -eq (ConvertTo-GcsFullPath 'C:\GCS\*.lnk')) $true 'wildcard bi tu choi'
    Assert-Eq ($null -eq (ConvertTo-GcsFullPath '\\server\share\a.lnk')) $true 'UNC bi tu choi'
    Assert-Eq ($null -eq (ConvertTo-GcsFullPath 'a.lnk')) $true 'duong dan tuong doi bi tu choi'
    Assert-Eq ($null -eq (ConvertTo-GcsFullPath 'C:\a.lnk:stream')) $true 'ADS bi tu choi'
    Assert-Eq (Test-GcsPathUnder 'C:\GCSX\a' $root) $false 'C:\GCSX khong nam trong C:\GCS'
    Assert-Eq (Test-GcsPathUnder 'C:\GCS\backup\..\..\x' $root) $false 'traversal ra ngoai'
    Assert-Eq (Test-GcsPathUnder 'c:\gcs\backup\a\state.json' (Join-Path $root 'backup')) $true 'state trong backup (khong phan biet hoa thuong)'
    Assert-Eq (Test-GcsShortcutPathAllowed 'C:\Users\Public\Desktop\GCS - Mission Planner.lnk' $desk) $true 'shortcut Public Desktop hop le'
    Assert-Eq (Test-GcsShortcutPathAllowed 'C:\Users\Bob\Desktop\x.LNK' $desk) $true 'shortcut Desktop user hop le'
    Assert-Eq (Test-GcsShortcutPathAllowed 'C:\Windows\notepad.exe' $desk) $false 'notepad.exe bi tu choi'
    Assert-Eq (Test-GcsShortcutPathAllowed 'C:\Users\Public\Desktop\a.exe' $desk) $false 'dung Desktop nhung khong .lnk'
    Assert-Eq (Test-GcsShortcutPathAllowed 'C:\Users\Public\Desktop\sub\a.lnk' $desk) $false 'thu muc con cua Desktop'
    Assert-Eq (Test-GcsShortcutPathAllowed 'C:\Users\Public\Desktop\..\..\..\Windows\a.lnk' $desk) $false 'traversal tu Desktop'
    Assert-Eq (Test-GcsShortcutPathAllowed 'C:\Users\Public\Desktop\*.lnk' $desk) $false 'wildcard'

    # --- loc state gia: shortcut notepad, quy tac wildcard, mp.path sai, power sai
    $fake = [pscustomobject]@{
        original = [pscustomobject]@{
            powerScheme = '381b4222-f694-41f0-9685-ff5bb260df2e'
            power = [pscustomobject]@{
                STANDBYIDLE = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = 1800; dc = 900 }
                VIDEOIDLE   = [pscustomobject]@{ sub = 'SUB_VIDEO'; ac = 600; dc = 300 }
                EVIL        = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = 1; dc = 1 }
                LIDACTION   = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = 1; dc = 1 }
            }
        }
        created = [pscustomobject]@{
            shortcuts = @('C:\Windows\notepad.exe', 'C:\Users\Public\Desktop\GCS - Test-Gcs.lnk', 'C:\Users\Public\Desktop\*.lnk')
            firewallRules = @('GCS-DroneTracking-MAVLink-UDP-14550-14551', 'GCS-DroneTracking*', 'Allow-All')
            firewallModified = @([pscustomobject]@{ name = 'GCS-DroneTracking-QGC'; profile = 'Domain, Private'; enabled = 'True'; program = 'Any'; remoteAddress = @('Any') },
                                 [pscustomobject]@{ name = 'GCS-DroneTracking-X'; profile = 'Private'; enabled = 'True'; program = 'C:\a*.exe'; remoteAddress = @('Any') })
            mp = [pscustomobject]@{ method = 'zip'; path = 'C:\GCS\backup'; byUs = $true }
            drivers = @([pscustomobject]@{ inf = 'x.inf'; published = 'oem12.inf' }, [pscustomobject]@{ inf = 'y.inf'; published = 'evil.inf' })
        }
    }
    $pl = Get-GcsSanitizedState $fake $root $desk
    Assert-Eq (@($pl.Shortcuts).Count) 1 'state gia: chi 1 shortcut hop le'
    Assert-Eq ($pl.Shortcuts -contains 'C:\Windows\notepad.exe') $false 'state gia: notepad.exe bi tu choi'
    Assert-Eq (@($pl.Rejected | Where-Object { $_ -like 'shortcut:*notepad*' }).Count) 1 'state gia: notepad.exe nam trong Rejected'
    Assert-Eq (@($pl.FirewallRules).Count) 1 'state gia: GCS-DroneTracking* va Allow-All bi tu choi'
    Assert-Eq (@($pl.FirewallModified).Count) 1 'state gia: firewallModified program wildcard bi tu choi'
    Assert-Eq ($null -eq $pl.Mp) $true 'state gia: mp.path=C:\GCS\backup bi tu choi'
    Assert-Eq (@($pl.Power).Count) 2 'state gia: power chi giu STANDBYIDLE + VIDEOIDLE'
    Assert-Eq (@($pl.Drivers).Count) 1 'state gia: published khong dang oemNN.inf bi tu choi'
    $ok = Get-GcsSanitizedState ([pscustomobject]@{ original = $null; created = [pscustomobject]@{ mp = [pscustomobject]@{ method = 'zip'; path = 'C:\GCS\MissionPlanner'; byUs = $true } } }) $root $desk
    Assert-Eq ($ok.Mp.Path) 'C:\GCS\MissionPlanner' 'mp.path dung duoc chap nhan'
    $msi = Get-GcsSanitizedState ([pscustomobject]@{ original = $null; created = [pscustomobject]@{ mp = [pscustomobject]@{ method = 'msi'; uninstallKey = 'rm -rf'; productCode = '{12345678-1234-1234-1234-123456789ABC}'; byUs = $true } } }) $root $desk
    Assert-Eq ($msi.Mp.Key) '{12345678-1234-1234-1234-123456789ABC}' 'msi: uninstallKey sai thi dung productCode hop le'

    # --- ACL trong bo nho
    $A = 'S-1-5-32-544'; $S = 'S-1-5-18'; $U = 'S-1-5-32-545'; $AU = 'S-1-5-11'; $E = 'S-1-1-0'
    $good = New-Acl $A @(@($A, 'FullControl', 'Allow'), @($S, 'FullControl', 'Allow'), @($U, 'ReadAndExecute', 'Allow'))
    Assert-Eq (@(Test-GcsAclSafe $good $true).Count) 0 'ACL dung (Admin/SYSTEM full, Users RX): an toan'
    $bad1 = New-Acl $A @(@($A, 'FullControl', 'Allow'), @($U, 'Modify', 'Allow'))
    Assert-Eq (@(Test-GcsAclSafe $bad1 $true).Count -gt 0) $true 'Users Modify: khong an toan'
    $bad2 = New-Acl $A @(,@($AU, 'Modify', 'Allow'))
    Assert-Eq (@(Test-GcsAclSafe $bad2 $true).Count -gt 0) $true 'Authenticated Users Modify: khong an toan'
    $bad3 = New-Acl $A @(,@($E, 'FullControl', 'Allow'))
    Assert-Eq (@(Test-GcsAclSafe $bad3 $true).Count -gt 0) $true 'Everyone FullControl: khong an toan'
    $bad4 = New-Acl $U @(,@($A, 'FullControl', 'Allow'))
    Assert-Eq (@(Test-GcsAclSafe $bad4 $true).Count -gt 0) $true 'chu so huu la Users: khong an toan'
    Assert-Eq (@(Test-GcsAclSafe $bad4 $false).Count) 0 'bo kiem chu so huu thi ACL tu no an toan'
    $deny = New-Acl $A @(@($U, 'Write', 'Deny'), @($U, 'ReadAndExecute', 'Allow'))
    Assert-Eq (@(Test-GcsAclSafe $deny $true).Count) 0 'Deny ghi + Users RX: an toan'
    $logsLike = New-Acl $A @(,@($U, 'Write', 'Allow'))
    Assert-Eq (@(Test-GcsAclSafe $logsLike $true).Count -gt 0) $true 'Users Write (kieu logs) bi nhan dien khi kiem thu muc nhay cam'

    # --- state.json that tren thu muc tam
    $troot = Join-Path $tmp 'GCS'
    $sdir = Join-Path $troot 'backup\20260101-000000'
    New-Item -ItemType Directory -Path $sdir -Force | Out-Null
    $sfile = Join-Path $sdir 'state.json'
    Set-Content -LiteralPath $sfile -Value '{}' -Encoding UTF8
    $out = @(Test-GcsStateTrusted (Join-Path $tmp 'ngoai\state.json') $troot)
    Assert-Eq ($out.Count -gt 0 -and $out[0] -like '*ngoai*') $true 'state.json ngoai backup bi tu choi'
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        $tr = @(Test-GcsStateTrusted $sfile $troot)
        Assert-Eq ($tr.Count -gt 0) $true 'state.json do nguoi dung thuong so huu bi tu choi (thu muc tam)'
    } else { Write-Host '[SKIP] state.json do user thuong so huu: dang chay quyen admin (chu so huu mac dinh la Administrators)' -ForegroundColor Yellow }

    # --- chu ky
    $T1 = 'AAAA1111'; $S1 = 'CN=Acme, O=Acme'
    $rec = [pscustomobject]@{ signed = $true; signerThumbprint = $T1; signerSubject = $S1 }
    Assert-Eq (Test-GcsSignatureMatch ([pscustomobject]@{ status = 'Valid'; subject = $S1; thumbprint = 'aaaa1111' }) $rec).Ok $true 'chu ky Valid + khop ban ghi'
    Assert-Eq (Test-GcsSignatureMatch ([pscustomobject]@{ status = 'Valid'; subject = $S1; thumbprint = 'BBBB' }) $rec).Ok $false 'thumbprint khac'
    Assert-Eq (Test-GcsSignatureMatch ([pscustomobject]@{ status = 'Valid'; subject = 'CN=Other'; thumbprint = $T1 }) $rec).Ok $false 'subject khac'
    Assert-Eq (Test-GcsSignatureMatch ([pscustomobject]@{ status = 'HashMismatch'; subject = $S1; thumbprint = $T1 }) $rec).Ok $false 'status HashMismatch'
    Assert-Eq (Test-GcsSignatureMatch ([pscustomobject]@{ status = 'NotSigned'; subject = ''; thumbprint = '' }) ([pscustomobject]@{ signed = $false })).Ok $false 'ban ghi signed=false'
    Assert-Eq (Test-GcsSignatureMatch ([pscustomobject]@{ status = 'Valid'; subject = $S1; thumbprint = $T1 }) ([pscustomobject]@{ sha256 = 'x' })).Ok $false 'ban ghi cu khong co truong chu ky'
    Assert-Eq (Test-GcsSignatureMatch ([pscustomobject]@{ status = 'Valid'; subject = $S1; thumbprint = $T1 }) $null).Ok $false 'khong co ban ghi'
    $fakeExe = Join-Path $tmp 'x.exe'
    Set-Content -LiteralPath $fakeExe -Value 'not a pe' -Encoding ASCII
    Assert-Eq ((Get-GcsFileSignature $fakeExe).status -ne 'Valid') $true 'file .exe gia khong co chu ky hop le'
    Assert-Eq ((Get-GcsFileSignature (Join-Path $tmp 'a.zip')).status) 'NotApplicable' '.zip: NotApplicable'
    $cmd = Join-Path $env:SystemRoot 'System32\cmd.exe'
    $cs = Get-GcsFileSignature $cmd
    Write-Host ("[INFO] cmd.exe: status={0} subject={1}" -f $cs.status, $cs.subject)

    # --- .inf
    Assert-Eq (Get-GcsInfCatalogName "[Version]`r`nSignature=`"`$Windows NT`$`r`nCatalogFile=foo.cat ; ghi chu`r`n") 'foo.cat' 'inf: CatalogFile'
    Assert-Eq (Get-GcsInfCatalogName "CatalogFile = `"foo.cat`"`r`nCatalogFile.NTamd64 = bar.cat") 'bar.cat' 'inf: uu tien NTamd64'
    Assert-Eq ($null -eq (Get-GcsInfCatalogName '; CatalogFile=foo.cat')) $true 'inf: dong chu thich bi bo'
    Assert-Eq ($null -eq (Get-GcsInfCatalogName 'CatalogFile=..\evil.cat')) $true 'inf: duong dan trong ten .cat bi tu choi'
    Assert-Eq ($null -eq (Get-GcsInfCatalogName '[Version]')) $true 'inf: khong co CatalogFile'

    # --- tuong lua, dong ho, mutex
    Assert-Eq (Test-GcsFirewallRulePublicInbound 'True' 'Inbound' 'Allow' 'Public') $true 'FW: Public inbound allow'
    Assert-Eq (Test-GcsFirewallRulePublicInbound 'True' 'Inbound' 'Allow' 'Private, Public') $true 'FW: Private+Public'
    Assert-Eq (Test-GcsFirewallRulePublicInbound 'True' 'Inbound' 'Allow' 'Any') $true 'FW: Any = gom Public'
    Assert-Eq (Test-GcsFirewallRulePublicInbound 'True' 'Inbound' 'Allow' 'Private') $false 'FW: chi Private'
    Assert-Eq (Test-GcsFirewallRulePublicInbound 'False' 'Inbound' 'Allow' 'Public') $false 'FW: tat'
    Assert-Eq (Test-GcsFirewallRulePublicInbound 'True' 'Outbound' 'Allow' 'Public') $false 'FW: outbound'
    Assert-Eq (Test-GcsFirewallRulePublicInbound 'True' 'Inbound' 'Block' 'Public') $false 'FW: Block'
    Assert-Eq (Get-GcsClockVerdict ([datetime]'2020-01-01') ([datetime]'2026-11-16')) 'SUSPECT' 'dong ho 2020 < thoi gian file'
    Assert-Eq (Get-GcsClockVerdict ([datetime]'2026-11-16 10:00') ([datetime]'2026-11-16 12:00')) 'OK' 'dong ho lech duoi 1 ngay'
    Assert-Eq ((Test-GcsMsiBusy) -is [bool]) $true 'Test-GcsMsiBusy tra bool (chi doc)'

    # --- mutex bi giu THAT (giu tu mot luong khac vi Mutex gan voi luong; ten Local\ de khong can admin)
    $mname = 'Local\gcs-test-msi-' + [guid]::NewGuid().ToString('N')
    $ready = New-Object System.Threading.ManualResetEvent($false)
    $rel = New-Object System.Threading.ManualResetEvent($false)
    $ps = [powershell]::Create()
    [void]$ps.AddScript('param($n, $r, $g) $m = New-Object System.Threading.Mutex($true, $n); [void]$r.Set(); [void]$g.WaitOne(); $m.ReleaseMutex(); $m.Dispose()').AddArgument($mname).AddArgument($ready).AddArgument($rel)
    $async = $ps.BeginInvoke()
    try {
        Assert-Eq ($ready.WaitOne(15000)) $true 'mutex: luong phu da tao va giu mutex'
        Assert-Eq (Test-GcsMsiBusy $mname) $true 'mutex bi giu: Test-GcsMsiBusy = true'
        $t0 = Get-Date
        $w = Wait-GcsMsiIdle 2 $mname 1
        $el = ((Get-Date) - $t0).TotalSeconds
        Assert-Eq $w $false 'mutex bi giu: Wait-GcsMsiIdle het han tra false'
        Assert-Eq ($el -ge 1.5 -and $el -lt 10) $true ("mutex bi giu: het han sau ~2s (thuc te {0:N1}s)" -f $el)
    } finally {
        [void]$rel.Set()
        try { $ps.EndInvoke($async) } catch { }
        $ps.Dispose()
    }
    Assert-Eq (Test-GcsMsiBusy $mname) $false 'mutex da tha: Test-GcsMsiBusy = false'
    Assert-Eq (Wait-GcsMsiIdle 2 $mname 1) $true 'mutex da tha: Wait-GcsMsiIdle tra true'
    Assert-Eq (Test-GcsMsiBusy ('Local\gcs-khong-co-' + [guid]::NewGuid().ToString('N'))) $false 'mutex khong ton tai: khong ban'

    # --- ACL: danh sach CHO PHEP
    $TI = 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'
    Assert-Eq (@(Test-GcsAclSafe (New-Acl $A @(@($A, 'FullControl', 'Allow'), @($TI, 'Modify', 'Allow'))) $true).Count) 0 'allowlist: TrustedInstaller duoc ghi'
    Assert-Eq (@(Test-GcsAclSafe (New-Acl $A @(,@('S-1-5-21-111-222-333-1001', 'Modify', 'Allow'))) $true).Count -gt 0) $true 'allowlist: SID tai khoan thuong co quyen ghi bi tu choi (khong chi Users/Everyone)'
    Assert-Eq (@(Test-GcsAclSafe (New-Acl $A @(,@('S-1-5-4', 'Write', 'Allow'))) $true).Count -gt 0) $true 'allowlist: INTERACTIVE ghi bi tu choi'
    Assert-Eq (@(Test-GcsAclSafe (New-Acl $A @(,@('S-1-5-21-111-222-333-1001', 'ReadAndExecute', 'Allow'))) $true).Count) 0 'allowlist: tai khoan thuong chi doc/chay: an toan'

    # --- cay thu muc THAT trong TEMP (file con co ACE ghi cho Users, junction)
    $me = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $tr2 = Join-Path $tmp 'tree'
    New-Item -ItemType Directory -Path (Join-Path $tr2 'tools') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $tr2 'config\sub') -Force | Out-Null
    $fTool = Join-Path $tr2 'tools\GcsLogic.ps1'
    $fCfg = Join-Path $tr2 'config\sub\f.txt'
    Set-Content -LiteralPath $fTool -Value '# x' -Encoding ASCII
    Set-Content -LiteralPath $fCfg -Value 'x' -Encoding ASCII
    Assert-Eq (@(Test-GcsTreeAcl $tr2 $false @($me)).Count) 0 'cay that (tai khoan hien tai coi la tin cay chi trong test): khong co van de'
    if (-not $isAdmin) {
        Assert-Eq (@(Test-GcsTreeAcl $tr2 $true @()).Count -gt 0) $true 'cay that: chu so huu la user thuong bi tu choi'
    }
    $aclF = Get-Acl -LiteralPath $fCfg
    $aclF.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule((New-Object System.Security.Principal.SecurityIdentifier($U)), 'Modify', 'Allow')))
    Set-Acl -LiteralPath $fCfg -AclObject $aclF
    $tp = @(Test-GcsTreeAcl $tr2 $false @($me))
    Assert-Eq ($tp.Count -gt 0 -and (@($tp | Where-Object { $_ -like '*f.txt*Users*' }).Count -gt 0)) $true 'cay that: FILE con trong config co ACE Modify cho Users bi tu choi'
    Assert-Eq (@(Test-GcsFileTrusted $fTool $false @($me)).Count) 0 'Test-GcsFileTrusted: file sach'
    $aclT = Get-Acl -LiteralPath $fTool
    $aclT.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule((New-Object System.Security.Principal.SecurityIdentifier($U)), 'Write', 'Allow')))
    Set-Acl -LiteralPath $fTool -AclObject $aclT
    Assert-Eq (@(Test-GcsFileTrusted $fTool $false @($me)).Count -gt 0) $true 'Test-GcsFileTrusted: file tools co ACE ghi cho Users bi tu choi'
    Assert-Eq (@(Test-GcsFileTrusted (Join-Path $tr2 'tools\khong-co.ps1')).Count -gt 0) $true 'Test-GcsFileTrusted: file khong ton tai bi tu choi'
    # junction: thu muc con la junction -> bi tu choi
    $jTarget = Join-Path $tmp 'jtarget'
    New-Item -ItemType Directory -Path $jTarget -Force | Out-Null
    $jPath = Join-Path $tr2 'logs'
    New-Item -ItemType Junction -Path $jPath -Target $jTarget | Out-Null
    try {
        Assert-Eq (@(Test-GcsTreeReparse $tr2).Count) 1 'junction: Test-GcsTreeReparse thay dung 1'
        Assert-Eq (@(Test-GcsTreeAcl $tr2 $false @($me) | Where-Object { $_ -like '*logs*reparse*' }).Count) 1 'junction: Test-GcsTreeAcl bao reparse point'
    } finally { [IO.Directory]::Delete($jPath, $false) }
    Assert-Eq (Test-Path -LiteralPath $jTarget) $true 'junction: xoa lien ket khong xoa thu muc dich'

    # --- Get-GcsPackageVerdict (logic cua Assert-PackageTrust)
    $H1 = 'ABCD1234'
    $sigOk = [pscustomobject]@{ status = 'Valid'; subject = 'CN=Acme Corp, O=Acme'; thumbprint = $T1 }
    $recOk = [pscustomobject]@{ sha256 = $H1; signed = $true; signerThumbprint = $T1; signerSubject = 'CN=Acme Corp, O=Acme' }
    $pkMsi = [pscustomobject]@{ id = 'p-msi'; file = 'x.msi'; expectedPublisher = @() }
    $pkNoField = [pscustomobject]@{ id = 'p-msi'; file = 'x.msi' }
    $pkPin = [pscustomobject]@{ id = 'p-msi'; file = 'x.msi'; expectedPublisher = @('*O=Acme*') }
    $pkBadPin = [pscustomobject]@{ id = 'p-msi'; file = 'x.msi'; expectedPublisher = @('*O=Evil*') }
    $pkZip = [pscustomobject]@{ id = 'p-zip'; file = 'x.zip'; expectedPublisher = @() }
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk $H1 $sigOk @()).Action 'Confirm' 'verdict: chu ky hop le nhung expectedPublisher rong -> hoi xac nhan'
    Assert-Eq (Get-GcsPackageVerdict $pkNoField $recOk $H1 $sigOk @()).Action 'Confirm' 'verdict: manifest khong co truong expectedPublisher = rong -> hoi'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk $H1 $sigOk @('p-msi')).Action 'Allow' 'verdict: co co theo goi -> bo qua hoi'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk $H1 $sigOk @('goi-khac')).Action 'Confirm' 'verdict: co cua goi KHAC khong ap dung'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk 'EEEE' $sigOk @()).Action 'Stop' 'verdict: SHA256 sai -> dung'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk 'EEEE' $sigOk @('p-msi')).Action 'Stop' 'verdict: SHA256 sai -> dung ke ca khi co co theo goi'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $null '' $sigOk @()).Action 'Stop' 'verdict: thieu muc checksum -> dung'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $null '' $sigOk @('p-msi')).Action 'Allow' 'verdict: thieu muc checksum + co co theo goi -> cho (canh bao)'
    Assert-Eq (Get-GcsPackageVerdict $pkPin $recOk $H1 $sigOk @()).Action 'Allow' 'verdict: nguoi ky khop expectedPublisher -> cho, khong hoi'
    Assert-Eq (Get-GcsPackageVerdict $pkBadPin $recOk $H1 $sigOk @()).Action 'Stop' 'verdict: nguoi ky KHONG khop expectedPublisher -> dung'
    Assert-Eq (Get-GcsPackageVerdict $pkBadPin $recOk $H1 $sigOk @('p-msi')).Action 'Stop' 'verdict: publisher khong khop -> dung ke ca khi co co theo goi'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk $H1 ([pscustomobject]@{ status = 'HashMismatch'; subject = 'CN=Acme Corp, O=Acme'; thumbprint = $T1 }) @()).Action 'Stop' 'verdict: chu ky khong Valid -> dung'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk $H1 ([pscustomobject]@{ status = 'NotSigned'; subject = ''; thumbprint = '' }) @('p-msi')).Action 'Allow' 'verdict: chua ky + co co theo goi -> cho (canh bao)'
    Assert-Eq (Get-GcsPackageVerdict $pkMsi $recOk $H1 ([pscustomobject]@{ status = 'Valid'; subject = 'CN=Acme Corp, O=Acme'; thumbprint = 'BBBB' }) @()).Action 'Stop' 'verdict: thumbprint khac ban ghi luc tai -> dung'
    $recZip = [pscustomobject]@{ sha256 = $H1; signed = $false }
    Assert-Eq (Get-GcsPackageVerdict $pkZip $recZip $H1 $null @()).Action 'Confirm' 'verdict: .zip khong co chu ky -> hoi xac nhan'
    Assert-Eq (Get-GcsPackageVerdict $pkZip $recZip $H1 $null @('p-zip')).Action 'Allow' 'verdict: .zip + co co theo goi -> cho'
    Assert-Eq (Get-GcsPackageVerdict $pkZip $recZip 'EEEE' $null @('p-zip')).Action 'Stop' 'verdict: .zip SHA256 sai -> dung'
    Assert-Eq (Get-GcsPackageVerdict $pkZip $null '' $null @()).Action 'Stop' 'verdict: .zip thieu muc checksum -> dung'
    Assert-Eq (Get-GcsPackageVerdict ([pscustomobject]@{ id = 'p-zip'; file = 'x.zip'; expectedPublisher = @('*Acme*') }) $recZip $H1 $null @()).Action 'Stop' 'verdict: .zip ma manifest ghim publisher -> dung (khong co nguoi ky)'
    Assert-Eq (Test-GcsPublisherMatch 'CN=ACME, O=acme' @('*O=Acme*')) $true 'publisher: khong phan biet hoa thuong'
    Assert-Eq (Test-GcsPublisherMatch 'CN=Acme' @()) $false 'publisher: mang rong khong khop'
    Assert-Eq (Test-GcsPublisherMatch 'CN=Acme' @('', '  ')) $false 'publisher: mau rong bi bo qua'

    # --- -GcsRoot
    Assert-Eq (@(Test-GcsRootPathValid 'C:\GCS').Count) 0 'GcsRoot: C:\GCS hop le'
    Assert-Eq (@(Test-GcsRootPathValid 'C:\Drone\GCS').Count) 0 'GcsRoot: C:\Drone\GCS hop le'
    foreach ($bad in @('C:\', 'C:', 'GCS', '.\GCS', '\\server\share\GCS', 'C:\Windows\GCS', 'C:\Windows', 'C:\Users\Bob\GCS', 'C:\Users', 'C:\Program Files\GCS', 'C:\Program Files (x86)\GCS', 'C:\Program Files Extra\GCS', 'C:\ProgramData\GCS', 'C:\GCS\..\Windows\GCS', 'C:\GCS*', 'C:\GCS:ads', '', 'Q:\GCS')) {
        Assert-Eq (@(Test-GcsRootPathValid $bad).Count -gt 0) $true "GcsRoot khong hop le: '$bad'"
    }
    Assert-Eq ((Get-GcsSysExe 'icacls.exe') -like '*\System32\icacls.exe') $true 'Get-GcsSysExe: duong dan day du'

    # --- dau hieu MP do bo cai cai
    $K1 = '{12345678-1234-1234-1234-123456789ABC}'
    $inst = @([pscustomobject]@{ name = 'Mission Planner'; version = '1.3.83'; key = $K1.ToLower() })
    Assert-Eq (Test-GcsMpMarkerMatches ([pscustomobject]@{ method = 'msi'; uninstallKey = $K1 }) $inst) $true 'marker msi: khop key dang cai (khong phan biet hoa thuong)'
    Assert-Eq (Test-GcsMpMarkerMatches ([pscustomobject]@{ method = 'msi'; uninstallKey = '{AAAAAAAA-1234-1234-1234-123456789ABC}' }) $inst) $false 'marker msi: key khac (MP do nguoi dung tu cai)'
    Assert-Eq (Test-GcsMpMarkerMatches ([pscustomobject]@{ method = 'msi'; uninstallKey = 'rm -rf' }) $inst) $false 'marker msi: key sai dinh dang'
    Assert-Eq (Test-GcsMpMarkerMatches $null $inst) $false 'marker: khong co file'
    Assert-Eq (Test-GcsMpMarkerMatches ([pscustomobject]@{ method = 'zip' }) @() $true) $true 'marker zip: co thu muc MP'
    Assert-Eq (Test-GcsMpMarkerMatches ([pscustomobject]@{ method = 'zip' }) @() $false) $false 'marker zip: khong co thu muc MP'

    # --- state: truong tuong lua cu (protocol/localPort/direction/action)
    $fw = Get-GcsSanitizedState ([pscustomobject]@{ original = $null; created = [pscustomobject]@{ firewallModified = @(
        [pscustomobject]@{ name = 'GCS-DroneTracking-A'; profile = 'Private'; enabled = 'True'; program = 'Any'; remoteAddress = @('Any'); protocol = 'TCP'; localPort = @('80', '443'); direction = 'Inbound'; action = 'Block' },
        [pscustomobject]@{ name = 'GCS-DroneTracking-B'; profile = 'Private'; enabled = 'True'; program = 'Any'; remoteAddress = @('Any'); direction = 'Sideways' },
        [pscustomobject]@{ name = 'GCS-DroneTracking-C'; profile = 'Private'; enabled = 'True'; program = 'Any'; remoteAddress = @('Any') }) } }) $root $desk
    Assert-Eq (@($fw.FirewallModified).Count) 2 'state FW: muc huong sai bi tu choi, muc cu (khong co truong moi) van duoc nhan'
    Assert-Eq ($fw.FirewallModified[0].Protocol) 'TCP' 'state FW: giu protocol cu'
    Assert-Eq (@($fw.FirewallModified[0].LocalPort).Count) 2 'state FW: giu localPort cu'

    # --- D1: thu muc goc tao NGUYEN TU kem DirectorySecurity (SID tham so hoa: o day dung SID chinh nguoi chay thay Administrators)
    $rootN = Join-Path $tmp 'rootN'
    [void](New-GcsRootDirectory $rootN (New-GcsRootSecurity $me @($me) @($U)))
    $aclN = Get-Acl -LiteralPath $rootN
    Assert-Eq $aclN.AreAccessRulesProtected $true 'root nguyen tu: ACL da bo thua ke ngay sau khi tao'
    Assert-Eq ($aclN.GetOwner([System.Security.Principal.SecurityIdentifier]).Value) $me 'root nguyen tu: chu so huu dung ngay sau khi tao'
    Assert-Eq (@($aclN.Access).Count) 2 'root nguyen tu: dung 2 ACE (toan quyen + doc/chay), khong co ACE thua ke'
    $ur = @($aclN.Access | Where-Object { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -eq $U })
    Assert-Eq ($ur.Count -eq 1 -and "$($ur[0].FileSystemRights)" -eq 'ReadAndExecute, Synchronize' -and "$($ur[0].InheritanceFlags)" -eq 'ContainerInherit, ObjectInherit') $true 'root nguyen tu: Users ReadAndExecute, thua ke cho con'
    $subN = Join-Path $rootN 'tools'
    New-Item -ItemType Directory -Path $subN | Out-Null
    Assert-Eq (@(Get-Acl -LiteralPath $subN).Access | Where-Object { $_.IsInherited }).Count 2 'thu muc con tao sau thua ke ACL cua goc'
    Assert-Eq (@(Test-GcsRootTrusted $rootN @($me)).Count) 0 'Test-GcsRootTrusted: goc vua tao dat'
    $secDef = New-GcsRootSecurity
    Assert-Eq (($secDef.GetOwner([System.Security.Principal.SecurityIdentifier])).Value) $A 'security mac dinh: chu so huu Administrators'
    Assert-Eq (@($secDef.Access | ForEach-Object { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } | Sort-Object) -join ',') (@($A, $S, $U | Sort-Object) -join ',') 'security mac dinh: Administrators + SYSTEM + Users'

    # --- D2: quyet dinh khi goc da co: chi 'Continue' khi dat day du, con lai 'Stop' kem huong dan lam tay
    Assert-Eq (Get-GcsRootDecision $rootN @(Test-GcsRootTrusted $rootN @($me))).Action 'Continue' 'goc co san dat (do bo cai tao): Continue'
    $rootBad = Join-Path $tmp 'rootBad'
    $secB = New-GcsRootSecurity $me @($me) @($U)
    $secB.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule((New-Object System.Security.Principal.SecurityIdentifier($AU)), 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
    [void](New-GcsRootDirectory $rootBad $secB)
    $decBad = Get-GcsRootDecision $rootBad @(Test-GcsRootTrusted $rootBad @($me))
    Assert-Eq $decBad.Action 'Stop' 'goc co san ma Authenticated Users ghi duoc: Stop'
    Assert-Eq ($decBad.Message -like '*doi ten hoac xoa*admin*') $true 'goc khong dat: thong bao huong dan doi ten/xoa bang admin'
    Assert-Eq ($decBad.Message -like '*AdoptExistingRoot*') $false 'goc khong dat: khong con goi y -AdoptExistingRoot'
    $rootOwn = Join-Path $tmp 'rootOwn'
    [void](New-GcsRootDirectory $rootOwn (New-GcsRootSecurity $me @($me) @($U)))
    Assert-Eq (Get-GcsRootDecision $rootOwn @(Test-GcsRootTrusted $rootOwn @())).Action ($(if ($isAdmin) { 'Continue' } else { 'Stop' })) 'goc co chu so huu la tai khoan thuong (khong khai bao tin cay): Stop'
    $rootJ = Join-Path $tmp 'rootJ'
    [void](New-GcsRootDirectory $rootJ (New-GcsRootSecurity $me @($me) @($U)))
    $jT3 = Join-Path $tmp 'jt3'
    New-Item -ItemType Directory -Path $jT3 | Out-Null
    New-Item -ItemType Junction -Path (Join-Path $rootJ 'logs') -Target $jT3 | Out-Null
    try { Assert-Eq (Get-GcsRootDecision $rootJ @(Test-GcsRootTrusted $rootJ @($me))).Action 'Stop' 'goc co junction ben trong: Stop (khong co nhanh bo qua)' }
    finally { [IO.Directory]::Delete((Join-Path $rootJ 'logs'), $false) }
    Assert-Eq (Get-GcsRootDecision 'C:\GCS' @()).Action 'Continue' 'quyet dinh thuan: khong van de -> Continue'
    Assert-Eq (Get-GcsRootDecision 'C:\GCS' @('C:\GCS: chu so huu la X')).Action 'Stop' 'quyet dinh thuan: co van de -> Stop'
    Assert-Eq (@(Test-GcsRootTrusted (Join-Path $tmp 'khong-co')).Count -gt 0) $true 'goc khong ton tai: khong dat'

    # --- D4: bo loc state (GUID sai mau, ten thiet lap la, gia tri am/khong phai so, nhom sai)
    $badS = Get-GcsSanitizedState ([pscustomobject]@{ original = [pscustomobject]@{ powerScheme = '381b4222; calc.exe'; power = [pscustomobject]@{ STANDBYIDLE = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = 1; dc = 1 } } }
        created = [pscustomobject]@{ powerActiveBefore = 'khong-phai-guid' } }) $root $desk
    Assert-Eq ($null -eq $badS.PowerGuid) $true 'state: GUID sai mau bi loai'
    Assert-Eq (@($badS.Power).Count) 0 'state: khong co GUID hop le thi khong co thiet lap powercfg nao'
    Assert-Eq ($null -eq $badS.ActiveBefore) $true 'state: powerActiveBefore sai mau bi loai'
    Assert-Eq (@($badS.Rejected).Count) 2 'state: ca hai GUID sai nam trong Rejected'
    $pwS = Get-GcsSanitizedState ([pscustomobject]@{ original = [pscustomobject]@{ powerScheme = '381b4222-f694-41f0-9685-ff5bb260df2e'; power = [pscustomobject]@{
        STANDBYIDLE = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = -1; dc = 5 }
        HIBERNATEIDLE = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = 'abc'; dc = 5 }
        VIDEOIDLE = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = 5; dc = 5 }
        'FOO BAR' = [pscustomobject]@{ sub = 'SUB_SLEEP'; ac = 1; dc = 1 }
        LIDACTION = [pscustomobject]@{ sub = 'SUB_BUTTONS'; ac = 1; dc = 0 } } }; created = [pscustomobject]@{} }) $root $desk
    Assert-Eq (@($pwS.Power).Count) 1 'state: am, khong phai so, nhom sai, ten la deu bi loai; chi giu LIDACTION hop le'
    Assert-Eq (@($pwS.Rejected).Count) 4 'state: 4 muc power khong hop le nam trong Rejected'
    Assert-Eq ($pwS.Power[0].Name) 'LIDACTION' 'state: muc giu lai la LIDACTION'

    # --- D5: Test-GcsRootPathValid: ten 8.3, ten thiet bi, cha la junction
    foreach ($bad in @('C:\PROGRA~1\GCS', 'C:\WINDOW~1\x', 'C:\GCS~1', 'C:\CON', 'C:\GCS\NUL', 'C:\COM1\GCS', 'C:\aux.txt\GCS', 'C:\LPT3')) {
        Assert-Eq (@(Test-GcsRootPathValid $bad).Count -gt 0) $true "GcsRoot ten dai/dac biet bi tu choi: '$bad'"
    }
    Assert-Eq (@(Test-GcsRootPathValid 'C:\GCS.old').Count) 0 'GcsRoot: C:\GCS.old hop le'
    Assert-Eq (@(Test-GcsRootPathValid 'C:\CONSOLE\GCS').Count) 0 'GcsRoot: C:\CONSOLE\GCS khong phai ten thiet bi'
    $jT4 = Join-Path $tmp 'jt4'
    $jL4 = Join-Path $tmp 'jl4'
    New-Item -ItemType Directory -Path $jT4 | Out-Null
    New-Item -ItemType Junction -Path $jL4 -Target $jT4 | Out-Null
    try {
        Assert-Eq (@(Test-GcsRootPathValid (Join-Path $jL4 'GCS') | Where-Object { $_ -like '*reparse*' }).Count) 1 'GcsRoot: thu muc cha la junction bi tu choi'
        Assert-Eq (@(Test-GcsRootTrusted (Join-Path $jL4 'GCS')).Count -gt 0) $true 'Test-GcsRootTrusted: thu muc cha la junction khong dat'
    } finally { [IO.Directory]::Delete($jL4, $false) }
    Assert-Eq (@(Test-GcsParentReparse 'C:\GCS').Count) 0 'cha cua C:\GCS khong phai reparse'

    # --- D5 L3: bam SHA256 bang .NET, khong tra $null duoi -WhatIf
    $hf = Join-Path $tmp 'hash.bin'
    [IO.File]::WriteAllBytes($hf, [byte[]](1..200))
    $hWi = & { $WhatIfPreference = $true; Get-GcsFileSha256 $hf }
    Assert-Eq $hWi (Get-FileHash -LiteralPath $hf -Algorithm SHA256).Hash 'Get-GcsFileSha256 = Get-FileHash va khong tra null duoi WhatIfPreference'

    # --- tinh: quet 5 script tim mau "hai lenh tren mot dong" (vd "@splat    Verb-Noun", "}$bien")
    $gdir = Split-Path -Parent $PSScriptRoot
    $stuckRx = @('@[A-Za-z_]\w*\s{2,}[A-Z][a-z]+-[A-Z][A-Za-z]+', '\}\$[A-Za-z_]', '[\)\]]\s{3,}[A-Z][a-z]+-[A-Z][A-Za-z]+\b')
    Assert-Eq (@('Add-Row x @extra    Add-Row y', 'if ($a) { x }$failed = 0') | Where-Object { $l = $_; @($stuckRx | Where-Object { $l -match $_ }).Count -gt 0 }).Count 2 'quet dinh dong: mau bat duoc 2 vi du dinh dong'
    $stuck = @()
    foreach ($sf in @('Install-Gcs.ps1', 'Uninstall-Gcs.ps1', 'Test-Gcs.ps1', 'GcsLogic.ps1', 'Get-GcsPackages.ps1')) {
        $ln = 0
        foreach ($line in [IO.File]::ReadAllLines((Join-Path $gdir $sf))) {
            $ln++
            foreach ($rx in $stuckRx) { if ($line -match $rx) { $stuck += "${sf}:${ln}: $($line.Trim())"; break } }
        }
    }
    Assert-Eq $stuck.Count 0 ('quet dinh dong: khong co lenh dinh dong trong 5 script ' + ($stuck -join ' || '))
}
finally {
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
Write-Host ("=== PASS={0} FAIL={1} ===" -f $script:Pass, $script:Fail)
if ($script:Fail -gt 0) { exit 1 }
exit 0

