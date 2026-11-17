<#
.SYNOPSIS
  Ham dung chung cho Install-Gcs / Uninstall-Gcs / Test-Gcs / Get-GcsPackages (nap bang dot-source).
  Chi chua ham kiem tra va phan tich; KHONG tu doi he thong khi nap. Khong can admin.
  Install-Gcs.ps1 chep file nay vao C:\GCS\tools\ cung Uninstall-Gcs.ps1 va Test-Gcs.ps1.
#>

function Get-GcsSidString([string]$Key) {
    switch ($Key) {
        'Admins'    { return 'S-1-5-32-544' }
        'System'    { return 'S-1-5-18' }
        'Users'     { return 'S-1-5-32-545' }
        'AuthUsers' { return 'S-1-5-11' }
        'Everyone'  { return 'S-1-1-0' }
        'TrustedInstaller' { return 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464' }
        default     { throw "SID khong biet: $Key" }
    }
}

function Get-GcsProp($obj, [string]$name, $default = $null) {
    if ($null -eq $obj) { return $default }
    if ($obj -is [System.Collections.IDictionary]) { if ($obj.Contains($name)) { return $obj[$name] } else { return $default } }
    $p = $obj.PSObject.Properties[$name]
    if ($null -eq $p) { return $default }
    return $p.Value
}

# ---------------------------------------------------------------- duong dan
# Chuan hoa duong dan tuyet doi dang o dia (C:\...). Tra ve $null neu co wildcard, UNC/\\?\, duong dan tuong doi,
# luong du lieu thay the (:), hoac khong chuan hoa duoc.
function ConvertTo-GcsFullPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    if ($Path -match '[\*\?<>\|"]') { return $null }
    if ($Path.StartsWith('\\')) { return $null }
    if ($Path -notmatch '^[A-Za-z]:\\') { return $null }
    if ($Path.IndexOf(':', 2) -ge 0) { return $null }
    try { return [IO.Path]::GetFullPath($Path).TrimEnd('\') } catch { return $null }
}
function Test-GcsPathEqual([string]$A, [string]$B) {
    $x = ConvertTo-GcsFullPath $A; $y = ConvertTo-GcsFullPath $B
    if ($null -eq $x -or $null -eq $y) { return $false }
    return [string]::Equals($x, $y, [StringComparison]::OrdinalIgnoreCase)
}
function Test-GcsPathUnder([string]$Path, [string]$Root) {
    $p = ConvertTo-GcsFullPath $Path; $r = ConvertTo-GcsFullPath $Root
    if ($null -eq $p -or $null -eq $r) { return $false }
    return $p.StartsWith($r + '\', [StringComparison]::OrdinalIgnoreCase)
}
# Shortcut hop le: duoi .lnk va nam truc tiep trong mot thu muc Desktop cho phep.
function Test-GcsShortcutPathAllowed([string]$Path, [string[]]$AllowedDirs) {
    $p = ConvertTo-GcsFullPath $Path
    if ($null -eq $p) { return $false }
    if (-not $p.EndsWith('.lnk', [StringComparison]::OrdinalIgnoreCase)) { return $false }
    $parent = Split-Path -Parent $p
    foreach ($d in @($AllowedDirs)) { if (Test-GcsPathEqual $parent $d) { return $true } }
    return $false
}

# ---------------------------------------------------------------- lenh he thong, thu muc goc
# Goi lenh he thong bang duong dan day du (khong de PATH quyet dinh khi chay quyen admin).
function Get-GcsSysExe([string]$Name) {
    $sr = $env:SystemRoot
    if ([string]::IsNullOrWhiteSpace($sr)) { $sr = 'C:\Windows' }
    return (Join-Path $sr ("System32\" + $Name))
}
# -GcsRoot hop le: duong dan tuyet doi tren o co dinh, khong phai goc o, khong nam trong C:\Windows, C:\Users,
# C:\Program Files*, C:\ProgramData. Tra ve danh sach van de (rong = hop le).
function Test-GcsRootPathValid([string]$Root) {
    $problems = New-Object System.Collections.ArrayList
    # Ten dai/ten dac biet (kiem tren chuoi goc, truoc khi chuan hoa): 8.3 (~1) va ten thiet bi danh rieng co the tro sang cho khac
    foreach ($seg in @($Root -split '[\\/]' | Select-Object -Skip 1)) {
        if ($seg -match '~\d') { [void]$problems.Add("ten '$seg' kieu 8.3 (~N): dung ten day du"); break }
        if ($seg.TrimEnd(' ', '.').Split('.')[0] -match '^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])$') { [void]$problems.Add("ten '$seg' la ten thiet bi danh rieng cua Windows"); break }
    }
    $full = ConvertTo-GcsFullPath $Root
    if ($null -eq $full) { return @(@($problems.ToArray()) + @("'$Root' khong phai duong dan tuyet doi dang o dia (C:\...) hoac co ky tu/luong khong cho phep")) }
    foreach ($rp in @(Test-GcsParentReparse $full)) { [void]$problems.Add("thu muc cha $rp la reparse point (junction/symlink)") }
    if ($full.Length -le 2) { [void]$problems.Add('khong duoc la goc o dia') }
    $letter = $full.Substring(0, 1)
    $fixed = $false
    try { $fixed = ((New-Object System.IO.DriveInfo($letter)).DriveType -eq [System.IO.DriveType]::Fixed) } catch { $fixed = $false }
    if (-not $fixed) { [void]$problems.Add("o $($letter): khong phai o dia co dinh") }
    $sd = $env:SystemDrive
    if ([string]::IsNullOrWhiteSpace($sd)) { $sd = 'C:' }
    $banned = @('C:\Windows', 'C:\Users', 'C:\ProgramData', 'C:\Program Files', 'C:\Program Files (x86)',
        (Join-Path $sd 'Windows'), (Join-Path $sd 'Users'), (Join-Path $sd 'ProgramData'), $env:SystemRoot, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData)
    foreach ($b in $banned) {
        if ([string]::IsNullOrWhiteSpace($b)) { continue }
        if ((Test-GcsPathEqual $full $b) -or (Test-GcsPathUnder $full $b)) { [void]$problems.Add("nam trong $b"); break }
    }
    if ($full -match '^[A-Za-z]:\\Program Files[^\\]*(\\|$)') { [void]$problems.Add('nam trong Program Files*') }
    return @($problems.ToArray())
}
# Cac thu muc cha (tru goc o dia) cua duong dan ma la reparse point. Tra ve danh sach duong dan.
function Test-GcsParentReparse([string]$Path) {
    $bad = @()
    $full = ConvertTo-GcsFullPath $Path
    if ($null -eq $full) { return @() }
    $cur = Split-Path -Parent $full
    while ($cur -and $cur.Length -gt 3) {
        $it = Get-Item -LiteralPath $cur -Force -ErrorAction SilentlyContinue
        if ($null -ne $it -and (($it.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { $bad += $cur }
        $cur = Split-Path -Parent $cur
    }
    return @($bad)
}
# Co muc nao (file/thu muc/reparse point, ke ca lien ket gay) o duong dan nay khong.
function Test-GcsAnyExists([string]$Path) {
    return ($null -ne (Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue))
}
# SHA256 (chu hoa) bang .NET; khong dung Get-FileHash vi no tra $null duoi -WhatIf.
function Get-GcsFileSha256([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $fs = [System.IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($fs)) -replace '-', '') }
    finally { $fs.Dispose(); $sha.Dispose() }
}

# ---------------------------------------------------------------- thu muc goc: tao nguyen tu + quyet dinh khi da co
# DirectorySecurity cho thu muc goc: bo thua ke, chu so huu = $OwnerSid, $FullControlSids toan quyen, $ReadSids chi doc/chay,
# ca hai thua ke cho con. Mac dinh: chu so huu Administrators; Administrators + SYSTEM toan quyen; Users doc/chay. Tham so hoa chi de kiem thu.
function New-GcsRootSecurity([string]$OwnerSid = '', [string[]]$FullControlSids = $null, [string[]]$ReadSids = $null) {
    if (-not $OwnerSid) { $OwnerSid = Get-GcsSidString 'Admins' }
    if ($null -eq $FullControlSids) { $FullControlSids = @((Get-GcsSidString 'Admins'), (Get-GcsSidString 'System')) }
    if ($null -eq $ReadSids) { $ReadSids = @((Get-GcsSidString 'Users')) }
    $sec = New-Object System.Security.AccessControl.DirectorySecurity
    $sec.SetOwner((New-Object System.Security.Principal.SecurityIdentifier($OwnerSid)))
    $sec.SetAccessRuleProtection($true, $false)
    $inh = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
    $prop = [System.Security.AccessControl.PropagationFlags]::None
    $allow = [System.Security.AccessControl.AccessControlType]::Allow
    foreach ($s in @($FullControlSids)) {
        $sid = New-Object System.Security.Principal.SecurityIdentifier($s)
        $sec.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($sid, [System.Security.AccessControl.FileSystemRights]::FullControl, $inh, $prop, $allow)))
    }
    foreach ($s in @($ReadSids)) {
        $sid = New-Object System.Security.Principal.SecurityIdentifier($s)
        $sec.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($sid, [System.Security.AccessControl.FileSystemRights]::ReadAndExecute, $inh, $prop, $allow)))
    }
    return $sec
}
# Tao thu muc KEM ACL + chu so huu trong cung mot lenh he thong (khong co khoang giua "tao" va "dat ACL").
# CreateDirectory khong bao loi neu thu muc da co (khi do ACL khong duoc ap) nen nguoi goi PHAI kiem lai bang Test-GcsRootTrusted.
function New-GcsRootDirectory([string]$Path, $Security) {
    return [System.IO.Directory]::CreateDirectory($Path, $Security)
}
# Thu muc goc va ca cay: khong reparse o cha/goc/con, chu so huu + ACL tung muc dung (xem Test-GcsTreeAcl). Rong = dang tin.
function Test-GcsRootTrusted([string]$Root, [string[]]$ExtraTrustedSids = @()) {
    $out = New-Object System.Collections.ArrayList
    foreach ($p in @(Test-GcsParentReparse $Root)) { [void]$out.Add("${p}: thu muc cha la reparse point (junction/symlink)") }
    if (-not (Test-GcsAnyExists $Root)) { [void]$out.Add("khong thay $Root"); return @($out.ToArray()) }
    foreach ($p in @(Test-GcsTreeAcl $Root $true $ExtraTrustedSids)) { [void]$out.Add($p) }
    return @($out.ToArray())
}
# Quyet dinh cho thu muc goc DA CO: chi 'Continue' khi khong co van de nao (tuc do chinh bo cai nay tao lan truoc). Con lai 'Stop' kem huong dan lam tay.
# Khong co nhanh "nhan lai": script khong doi ten, khong reset ACL, khong doc gi tu mot goc khong dat.
function Get-GcsRootDecision([string]$Root, [string[]]$Problems = @()) {
    $pr = @($Problems | Where-Object { $_ })
    if ($pr.Count -eq 0) { return [pscustomobject]@{ Action = 'Continue'; Message = '' } }
    $msg = ("{0} da ton tai nhung KHONG dat kiem tin cay (chu so huu/ACL/reparse point), nen script DUNG va khong dong cham vao no. " +
        "Hay doi ten hoac xoa thu muc do bang tai khoan admin (vd: ren {0} {1}.old) roi chay lai. Van de dau tien: {2}") -f $Root, (Split-Path -Leaf $Root), $pr[0]
    return [pscustomobject]@{ Action = 'Stop'; Message = $msg }
}

# ---------------------------------------------------------------- ACL
# Danh sach CHO PHEP: chi Administrators, SYSTEM, TrustedInstaller duoc co quyen ghi (Users chi doc/chay).
# $Acl: doi tuong FileSystemSecurity (Get-Acl hoac tao trong bo nho). Tra ve danh sach van de (rong = an toan).
# $ExtraTrustedSids chi de kiem thu (vd SID cua tai khoan dang chay test tren thu muc tam); bo cai khong bao gio truyen.
function Test-GcsAclSafe($Acl, [bool]$CheckOwner = $true, [string[]]$ExtraTrustedSids = @()) {
    $problems = New-Object System.Collections.ArrayList
    $trusted = @((Get-GcsSidString 'Admins'), (Get-GcsSidString 'System'))
    $mayWrite = @($trusted + @((Get-GcsSidString 'TrustedInstaller')) + @($ExtraTrustedSids))
    # WriteData, AppendData, WriteEA, DeleteSubdirectoriesAndFiles, WriteAttributes, Delete, ChangePermissions, TakeOwnership, GenericAll, GenericWrite
    $writeMask = [int64](0x2 -bor 0x4 -bor 0x10 -bor 0x40 -bor 0x100 -bor 0x10000 -bor 0x40000 -bor 0x80000 -bor 0x10000000 -bor 0x40000000)
    if ($CheckOwner) {
        $own = $null
        try { $own = $Acl.GetOwner([System.Security.Principal.SecurityIdentifier]) } catch { $own = $null }
        if ($null -eq $own) { [void]$problems.Add('khong doc duoc chu so huu') }
        elseif (($trusted + @($ExtraTrustedSids)) -notcontains $own.Value) { [void]$problems.Add("chu so huu la $($own.Value), khong phai Administrators/SYSTEM") }
    }
    foreach ($r in $Acl.Access) {
        if ([string]$r.AccessControlType -ne 'Allow') { continue }
        if (([int64]$r.FileSystemRights -band $writeMask) -eq 0) { continue }
        $sid = $null
        try {
            if ($r.IdentityReference -is [System.Security.Principal.SecurityIdentifier]) { $sid = $r.IdentityReference.Value }
            else { $sid = $r.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value }
        } catch { $sid = $null }
        if ($null -eq $sid) { [void]$problems.Add(("{0} (khong doi duoc sang SID) co quyen ghi ({1})" -f $r.IdentityReference.Value, $r.FileSystemRights)); continue }
        if ($mayWrite -contains $sid) { continue }
        [void]$problems.Add(("{0} co quyen ghi ({1})" -f $r.IdentityReference.Value, $r.FileSystemRights))
    }
    return @($problems.ToArray())
}
# Liet ke goc + moi thu muc/file ben duoi (khong di vao reparse point). Moi muc: Path, IsDir, Reparse, Error.
function Get-GcsTreeItems([string]$Root) {
    $out = New-Object System.Collections.ArrayList
    if (-not (Test-Path -LiteralPath $Root)) { return @() }
    $ri = Get-Item -LiteralPath $Root -Force
    $rp = (($ri.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
    [void]$out.Add([pscustomobject]@{ Path = $ri.FullName; IsDir = $true; Reparse = $rp; Error = '' })
    if ($rp) { return @($out.ToArray()) }
    $stack = New-Object System.Collections.Stack
    $stack.Push($ri.FullName)
    while ($stack.Count -gt 0) {
        $d = [string]$stack.Pop()
        $kids = @()
        try { $kids = @(Get-ChildItem -LiteralPath $d -Force -ErrorAction Stop) }
        catch { [void]$out.Add([pscustomobject]@{ Path = $d; IsDir = $true; Reparse = $false; Error = $_.Exception.Message }); continue }
        foreach ($k in $kids) {
            $isRp = (($k.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
            $isDir = (($k.Attributes -band [IO.FileAttributes]::Directory) -ne 0)
            [void]$out.Add([pscustomobject]@{ Path = $k.FullName; IsDir = $isDir; Reparse = $isRp; Error = '' })
            if ($isDir -and -not $isRp) { $stack.Push($k.FullName) }
        }
    }
    return @($out.ToArray())
}
# Duong dan reparse point (junction/symlink) trong cay $Root (goc, tools, backup, config, logs, MissionPlanner, packages va moi thu con).
function Test-GcsTreeReparse([string]$GcsRoot) {
    return @(Get-GcsTreeItems $GcsRoot | Where-Object { $_.Reparse } | ForEach-Object { $_.Path })
}
# Kiem CA cay: moi thu muc VA moi file (gom config) phai do Administrators/SYSTEM so huu va khong ai ngoai
# Administrators/SYSTEM/TrustedInstaller co quyen ghi; reparse point bi tu choi. Toi da 40 dong van de (+ dong tom tat).
function Test-GcsTreeAcl([string]$GcsRoot, [bool]$CheckOwner = $true, [string[]]$ExtraTrustedSids = @()) {
    $out = New-Object System.Collections.ArrayList
    foreach ($it in @(Get-GcsTreeItems $GcsRoot)) {
        if ($it.Error) { [void]$out.Add("$($it.Path): khong doc duoc thu muc: $($it.Error)"); continue }
        if ($it.Reparse) { [void]$out.Add("$($it.Path): la reparse point (junction/symlink)"); continue }
        $acl = $null
        try { $acl = Get-Acl -LiteralPath $it.Path } catch { [void]$out.Add("$($it.Path): khong doc duoc ACL: $($_.Exception.Message)"); continue }
        foreach ($p in @(Test-GcsAclSafe $acl $CheckOwner $ExtraTrustedSids)) { [void]$out.Add("$($it.Path): $p") }
    }
    if ($out.Count -gt 40) {
        $n = $out.Count - 40
        $out.RemoveRange(40, $n)
        [void]$out.Add("... va $n van de khac")
    }
    return @($out.ToArray())
}
# Mot file (va thu muc chua no) phai do Administrators/SYSTEM so huu, khong ai khac ghi duoc, khong la reparse point.
# Dung truoc khi nap/chay file tu C:\GCS\tools bang quyen admin.
function Test-GcsFileTrusted([string]$Path, [bool]$CheckOwner = $true, [string[]]$ExtraTrustedSids = @()) {
    $out = New-Object System.Collections.ArrayList
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return @("khong thay file $Path") }
    foreach ($t in @($Path, (Split-Path -Parent $Path))) {
        $it = Get-Item -LiteralPath $t -Force
        if (($it.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { [void]$out.Add("${t}: la reparse point (junction/symlink)"); continue }
        $acl = $null
        try { $acl = Get-Acl -LiteralPath $t } catch { [void]$out.Add("${t}: khong doc duoc ACL: $($_.Exception.Message)"); continue }
        foreach ($p in @(Test-GcsAclSafe $acl $CheckOwner $ExtraTrustedSids)) { [void]$out.Add("${t}: $p") }
    }
    return @($out.ToArray())
}
# state.json chi duoc tin khi nam trong <GcsRoot>\backup va file/thu muc cua no do Administrators/SYSTEM so huu, Users khong ghi duoc.
function Test-GcsStateTrusted([string]$StatePath, [string]$GcsRoot) {
    $problems = New-Object System.Collections.ArrayList
    $bd = Join-Path $GcsRoot 'backup'
    if (-not (Test-GcsPathUnder $StatePath $bd)) { return @("state.json nam ngoai $bd") }
    foreach ($t in @($StatePath, (Split-Path -Parent $StatePath), $bd, $GcsRoot)) {
        if (-not (Test-Path -LiteralPath $t)) { [void]$problems.Add("khong thay $t"); continue }
        $acl = Get-Acl -LiteralPath $t
        foreach ($p in @(Test-GcsAclSafe $acl $true)) { [void]$problems.Add("${t}: $p") }
    }
    return @($problems.ToArray())
}

# ---------------------------------------------------------------- chu ky so
function Get-GcsFileSignature([string]$Path) {
    $ext = [IO.Path]::GetExtension($Path).ToLowerInvariant()
    if (@('.msi', '.exe', '.cat', '.dll', '.sys') -notcontains $ext) {
        return [pscustomobject]@{ status = 'NotApplicable'; subject = ''; thumbprint = '' }
    }
    $s = Get-AuthenticodeSignature -LiteralPath $Path
    $sub = ''; $th = ''
    if ($null -ne $s.SignerCertificate) { $sub = [string]$s.SignerCertificate.Subject; $th = [string]$s.SignerCertificate.Thumbprint }
    return [pscustomobject]@{ status = [string]$s.Status; subject = $sub; thumbprint = $th }
}
# $Sig: ket qua Get-GcsFileSignature luc cai; $Record: muc checksums.json (signed, signerSubject, signerThumbprint) luc tai.
function Test-GcsSignatureMatch($Sig, $Record) {
    $reasons = New-Object System.Collections.ArrayList
    $recSigned = $null
    if ($null -eq $Record) { [void]$reasons.Add('khong co ban ghi chu ky luc tai (checksums.json)') }
    else {
        $recSigned = Get-GcsProp $Record 'signed' $null
        if ($null -eq $recSigned) { [void]$reasons.Add('checksums.json khong co thong tin chu ky (tao bang Get-GcsPackages ban cu)') }
        elseif (-not [bool]$recSigned) { [void]$reasons.Add('luc tai goi nay khong co chu ky hop le (signed=false)') }
    }
    if ([string]$Sig.status -ne 'Valid') { [void]$reasons.Add(("Authenticode hien tai: {0} (can Valid)" -f $Sig.status)) }
    if ($null -ne $recSigned -and [bool]$recSigned) {
        $rt = [string](Get-GcsProp $Record 'signerThumbprint' '')
        $rs = [string](Get-GcsProp $Record 'signerSubject' '')
        if (-not $rt -or -not [string]::Equals($rt, [string]$Sig.thumbprint, [StringComparison]::OrdinalIgnoreCase)) { [void]$reasons.Add('thumbprint nguoi ky khac ban ghi luc tai') }
        if (-not $rs -or -not [string]::Equals($rs, [string]$Sig.subject, [StringComparison]::OrdinalIgnoreCase)) { [void]$reasons.Add('subject nguoi ky khac ban ghi luc tai') }
    }
    return [pscustomobject]@{ Ok = ($reasons.Count -eq 0); Reason = ($reasons -join '; ') }
}
# Lay ten file .cat tu noi dung .inf (uu tien CatalogFile.NTamd64, roi CatalogFile). Tra ve $null neu khong co hoac co dau phan cach duong dan.
function Get-GcsInfCatalogName([string]$InfText) {
    $found = @{}
    foreach ($line in ($InfText -split "`r?`n")) {
        $l = ($line -replace ';.*$', '').Trim()
        if ($l -match '^CatalogFile(\.([A-Za-z0-9]+))?\s*=\s*"?([^"\s]+)"?\s*$') {
            $suffix = ''
            if ($Matches[2]) { $suffix = $Matches[2].ToLowerInvariant() }
            if (-not $found.ContainsKey($suffix)) { $found[$suffix] = $Matches[3] }
        }
    }
    $name = $null
    if ($found.ContainsKey('ntamd64')) { $name = $found['ntamd64'] }
    elseif ($found.ContainsKey('')) { $name = $found[''] }
    elseif ($found.Count -gt 0) { $name = @($found.Values)[0] }
    if ($null -eq $name) { return $null }
    if ($name -match '[\\/:]') { return $null }
    return $name
}

# ---------------------------------------------------------------- tuong lua, dong ho
# Quy tac cho phep vao tren profile Public (ke ca Any) = lo ra mang cong cong.
function Test-GcsFirewallRulePublicInbound([string]$Enabled, [string]$Direction, [string]$Action, [string]$Profile) {
    if ($Enabled -ne 'True') { return $false }
    if ($Direction -ne 'Inbound') { return $false }
    if ($Action -ne 'Allow') { return $false }
    return [bool]($Profile -match 'Public|Any|All')
}
function Get-GcsClockVerdict([datetime]$Now, [datetime]$Reference) {
    if ($Now -lt $Reference.AddDays(-1)) { return 'SUSPECT' }
    return 'OK'
}

# ---------------------------------------------------------------- Windows Installer
# $true neu mot luot cai Windows Installer dang chay (mutex Global\_MSIExecute dang bi giu). Chi doc.
# $MutexName chi doi khi kiem thu (ten Local\...); bo cai dung mac dinh.
function Test-GcsMsiBusy([string]$MutexName = 'Global\_MSIExecute') {
    $m = $null
    $ok = $false
    try { $ok = [System.Threading.Mutex]::TryOpenExisting($MutexName, [System.Security.AccessControl.MutexRights]::Synchronize, [ref]$m) }
    catch { return $false }   # khong mo duoc (quyen): coi nhu khong biet; cai dat se tu thu lai khi gap 1618
    if (-not $ok) { return $false }
    try {
        $got = $false
        try { $got = $m.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $got = $true }
        if ($got) { try { $m.ReleaseMutex() } catch { }; return $false }
        return $true
    } finally { $m.Dispose() }
}
function Wait-GcsMsiIdle([int]$MaxSeconds, [string]$MutexName = 'Global\_MSIExecute', [int]$PollSeconds = 5) {
    $deadline = (Get-Date).AddSeconds($MaxSeconds)
    while (Test-GcsMsiBusy $MutexName) {
        if ((Get-Date) -ge $deadline) { return $false }
        Start-Sleep -Seconds $PollSeconds
    }
    return $true
}

# ---------------------------------------------------------------- loc state.json truoc khi dung
# Chi tra ve cac gia tri da qua kiem tra pham vi; cai gi khong hop le di vao .Rejected.
function Get-GcsSanitizedState($State, [string]$GcsRoot, [string[]]$DesktopDirs) {
    $guidRx = '^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$'
    $codeRx = '^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$'
    $fwNameRx = '^GCS-DroneTracking[A-Za-z0-9_.-]*$'
    $rej = New-Object System.Collections.ArrayList
    $power = New-Object System.Collections.ArrayList
    $fwRules = New-Object System.Collections.ArrayList
    $fwMod = New-Object System.Collections.ArrayList
    $links = New-Object System.Collections.ArrayList
    $drivers = New-Object System.Collections.ArrayList
    $apps = New-Object System.Collections.ArrayList
    $orig = Get-GcsProp $State 'original' $null
    $cr = Get-GcsProp $State 'created' $null

    # nguon
    $guid = $null
    $g = Get-GcsProp $orig 'powerScheme' $null
    if ($g) { if ([string]$g -match $guidRx) { $guid = [string]$g } else { [void]$rej.Add("powerScheme: '$g' khong phai GUID") } }
    $activeBefore = $null
    $ab = Get-GcsProp $cr 'powerActiveBefore' $null
    if ($ab) { if ([string]$ab -match $guidRx) { $activeBefore = [string]$ab } else { [void]$rej.Add("powerActiveBefore: '$ab' khong phai GUID") } }
    $pw = Get-GcsProp $orig 'power' $null
    if ($guid -and $null -ne $pw) {
        $subMap = @{ STANDBYIDLE = 'SUB_SLEEP'; HIBERNATEIDLE = 'SUB_SLEEP'; VIDEOIDLE = 'SUB_VIDEO'; LIDACTION = 'SUB_BUTTONS' }
        foreach ($p in $pw.PSObject.Properties) {
            if ($null -eq $p.Value) { continue }
            $name = @($subMap.Keys | Where-Object { $_ -ieq [string]$p.Name }) | Select-Object -First 1
            if (-not $name) { [void]$rej.Add("power: thiet lap '$($p.Name)' khong trong danh sach cho phep"); continue }
            $sub = [string](Get-GcsProp $p.Value 'sub' '')
            if ($sub -ne $subMap[$name]) { [void]$rej.Add("power ${name}: nhom '$sub' sai (can $($subMap[$name]))"); continue }
            $ac = 0L; $dc = 0L
            $okAc = [int64]::TryParse([string](Get-GcsProp $p.Value 'ac' ''), [ref]$ac)
            $okDc = [int64]::TryParse([string](Get-GcsProp $p.Value 'dc' ''), [ref]$dc)
            if (-not $okAc -or -not $okDc -or $ac -lt 0 -or $dc -lt 0 -or $ac -gt 4294967295 -or $dc -gt 4294967295) { [void]$rej.Add("power ${name}: gia tri ac/dc khong hop le"); continue }
            [void]$power.Add([pscustomobject]@{ Name = $name; Sub = $sub; Ac = $ac; Dc = $dc })
        }
    }

    # tuong lua
    foreach ($r in @(Get-GcsProp $cr 'firewallRules' @())) {
        if ([string]$r -match $fwNameRx) { [void]$fwRules.Add([string]$r) } else { [void]$rej.Add("firewallRules: '$r' khong dung dinh dang GCS-DroneTracking[A-Za-z0-9_.-]*") }
    }
    foreach ($b in @(Get-GcsProp $cr 'firewallModified' @())) {
        $n = [string](Get-GcsProp $b 'name' '')
        $prof = [string](Get-GcsProp $b 'profile' '')
        $en = [string](Get-GcsProp $b 'enabled' '')
        $prog = [string](Get-GcsProp $b 'program' '')
        $ras = @(Get-GcsProp $b 'remoteAddress' @() | ForEach-Object { [string]$_ })
        $bad = @()
        if ($n -notmatch $fwNameRx) { $bad += 'ten' }
        if ($prof -notmatch '^(Any|Domain|Private|Public)(\s*,\s*(Domain|Private|Public))*$') { $bad += 'profile' }
        if ($en -notmatch '^(True|False)$') { $bad += 'enabled' }
        if ($prog -notmatch '^(Any|[A-Za-z]:\\[^\*\?<>\|"]+|%[A-Za-z0-9_]+%\\[^\*\?<>\|"]+)$') { $bad += 'program' }
        foreach ($ra in $ras) { if ($ra -notmatch '^[0-9A-Za-z./:_-]+$') { $bad += 'remoteAddress' } }
        if ($ras.Count -eq 0) { $bad += 'remoteAddress' }
        # truong tuy chon (state ban cu khong co): giao thuc, cong, huong, hanh dong cua quy tac cu
        $proto = [string](Get-GcsProp $b 'protocol' '')
        $dir = [string](Get-GcsProp $b 'direction' '')
        $act = [string](Get-GcsProp $b 'action' '')
        $lps = @(Get-GcsProp $b 'localPort' @() | ForEach-Object { [string]$_ })
        if ($proto -and $proto -notmatch '^(Any|TCP|UDP|ICMPv4|ICMPv6|[0-9]{1,3})$') { $bad += 'protocol' }
        if ($dir -and $dir -notmatch '^(Inbound|Outbound)$') { $bad += 'direction' }
        if ($act -and $act -notmatch '^(Allow|Block)$') { $bad += 'action' }
        foreach ($lp in $lps) { if ($lp -notmatch '^[A-Za-z0-9,-]+$') { $bad += 'localPort' } }
        if ($bad.Count -gt 0) { [void]$rej.Add("firewallModified '$n': truong khong hop le: $($bad -join ',')"); continue }
        [void]$fwMod.Add([pscustomobject]@{ Name = $n; Profile = $prof; Enabled = $en; Program = $prog; RemoteAddress = $ras; Protocol = $proto; LocalPort = $lps; Direction = $dir; Action = $act })
    }

    # shortcut
    foreach ($s in @(Get-GcsProp $cr 'shortcuts' @())) {
        if (Test-GcsShortcutPathAllowed ([string]$s) $DesktopDirs) { [void]$links.Add([string]$s) }
        else { [void]$rej.Add("shortcut: '$s' khong phai file .lnk truc tiep trong thu muc Desktop cho phep") }
    }

    # Mission Planner
    $mpOut = $null
    $mp = Get-GcsProp $cr 'mp' $null
    if ($null -ne $mp) {
        $method = [string](Get-GcsProp $mp 'method' '')
        $byUs = [bool](Get-GcsProp $mp 'byUs' $false)
        $status = [string](Get-GcsProp $mp 'status' '')
        if ($method -eq 'zip') {
            $path = [string](Get-GcsProp $mp 'path' '')
            if (Test-GcsPathEqual $path (Join-Path $GcsRoot 'MissionPlanner')) { $mpOut = [pscustomobject]@{ Method = 'zip'; ByUs = $byUs; Path = (ConvertTo-GcsFullPath $path); Key = $null; Status = $status } }
            else { [void]$rej.Add("mp.path: '$path' khac $(Join-Path $GcsRoot 'MissionPlanner')") }
        } elseif ($method -eq 'msi') {
            $key = $null
            foreach ($c in @((Get-GcsProp $mp 'uninstallKey' ''), (Get-GcsProp $mp 'productCode' ''))) {
                if ($c -and [string]$c -match $codeRx) { $key = [string]$c; break }
            }
            $mpOut = [pscustomobject]@{ Method = 'msi'; ByUs = $byUs; Path = $null; Key = $key; Status = $status }
        } else { [void]$rej.Add("mp.method: '$method' khong biet") }
    }

    # chi de hien thi
    foreach ($d in @(Get-GcsProp $cr 'drivers' @())) {
        $pub = [string](Get-GcsProp $d 'published' '')
        if ($pub -and $pub -notmatch '^oem\d+\.inf$') { [void]$rej.Add("driver published: '$pub' khong dung dang oemNN.inf"); continue }
        if ($pub) { [void]$drivers.Add([pscustomobject]@{ Published = $pub; Inf = ([string](Get-GcsProp $d 'inf' '') -replace '[\r\n]', ' ') }) }
    }
    foreach ($a in @(Get-GcsProp $cr 'apps' @())) {
        if ([string]$a -match '^[A-Za-z0-9._ -]+$') { [void]$apps.Add([string]$a) } else { [void]$rej.Add("apps: '$a' khong hop le") }
    }

    return [pscustomobject]@{
        PowerGuid = $guid; Power = @($power.ToArray()); ActiveBefore = $activeBefore
        FirewallRules = @($fwRules.ToArray()); FirewallModified = @($fwMod.ToArray())
        Shortcuts = @($links.ToArray()); Mp = $mpOut; Drivers = @($drivers.ToArray()); Apps = @($apps.ToArray())
        Rejected = @($rej.ToArray())
    }
}

# ---------------------------------------------------------------- tin cay goi (logic thuan, de kiem thu)
# Mau nguoi ky mong doi: wildcard -like, khong phan biet hoa thuong, vd '*O=Ardupilot*'. Mang rong = chua ghim.
function Get-GcsPinnedPublishers($Pk) {
    return @(@(Get-GcsProp $Pk 'expectedPublisher' @()) | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}
function Test-GcsPublisherMatch([string]$Subject, [string[]]$Patterns) {
    foreach ($p in @($Patterns)) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        if ($Subject -like $p) { return $true }
    }
    return $false
}
# Quyet dinh cho mot goi. $Record: muc checksums.json (hoac $null). $ActualSha256: hash that cua file dang kiem ('' neu khong co ban ghi).
# $Sig: ket qua Get-GcsFileSignature (voi .msi/.exe). $AllowIds: id goi duoc -AllowUnsigned.
# Action: 'Stop' (dung), 'Confirm' (phai hoi nguoi dung), 'Allow' (cho chay).
#  - SHA256 sai, hoac expectedPublisher co gia tri ma nguoi ky khong khop: luon Stop (khong bo qua duoc bang -AllowUnsigned).
#  - Thieu muc checksum / chu ky khong hop le / khong khop ban ghi luc tai: Stop, tru khi id nam trong $AllowIds.
#  - .zip (khong co chu ky) hoac chu ky hop le nhung expectedPublisher rong: Confirm, tru khi id nam trong $AllowIds.
#  - Chu ky hop le + khop expectedPublisher: Allow.
function Get-GcsPackageVerdict($Pk, $Record, [string]$ActualSha256, $Sig, [string[]]$AllowIds = @()) {
    $id = [string](Get-GcsProp $Pk 'id' '')
    $file = [string](Get-GcsProp $Pk 'file' '')
    $ext = [IO.Path]::GetExtension($file).ToLowerInvariant()
    $isPe = ($ext -eq '.msi' -or $ext -eq '.exe')
    $allowed = (@($AllowIds) -contains $id)
    $pins = @(Get-GcsPinnedPublishers $Pk)
    $problems = New-Object System.Collections.ArrayList
    $fatal = ''
    if ($null -eq $Record) { [void]$problems.Add('khong co muc checksum trong packages\checksums.json') }
    elseif (-not [string]::Equals($ActualSha256, [string](Get-GcsProp $Record 'sha256' ''), [StringComparison]::OrdinalIgnoreCase)) {
        $fatal = "SHA256 khong khop voi checksums.json: $file (file hong hoac bi doi) - KHONG the bo qua bang -AllowUnsigned"
    }
    $subject = ''
    if ($null -ne $Sig) { $subject = [string](Get-GcsProp $Sig 'subject' '') }
    if ($isPe) {
        $res = Test-GcsSignatureMatch $Sig $Record
        if (-not $res.Ok) { [void]$problems.Add($res.Reason) }
    }
    if (-not $fatal -and $pins.Count -gt 0) {
        if (-not $isPe -or -not (Test-GcsPublisherMatch $subject $pins)) {
            $fatal = ("nguoi ky '{0}' khong khop expectedPublisher ({1}) cua goi {2} - KHONG the bo qua bang -AllowUnsigned" -f $subject, ($pins -join ' | '), $id)
        }
    }
    $action = 'Allow'
    $msg = ''
    if ($fatal) { $action = 'Stop'; $msg = $fatal }
    elseif ($problems.Count -gt 0) {
        $msg = ($problems -join '; ')
        if ($allowed) { $action = 'Allow' } else { $action = 'Stop' }
    }
    elseif (-not $isPe) {
        $msg = "$file khong co chu ky so; chi co SHA256 (cung USB: chi chong hong file, khong chong thay file)"
        if ($allowed) { $action = 'Allow' } else { $action = 'Confirm' }
    }
    elseif ($pins.Count -eq 0) {
        $msg = 'expectedPublisher trong manifest.json dang rong: chua co diem tin cay ngoai USB'
        if ($allowed) { $action = 'Allow' } else { $action = 'Confirm' }
    }
    return [pscustomobject]@{ Action = $action; Message = $msg; Problems = @($problems.ToArray()); Pinned = ($pins.Count -gt 0); Allowed = $allowed }
}

# ---------------------------------------------------------------- dau hieu "MP do bo cai nay cai" (ben vung qua Uninstall)
# $Marker: noi dung file danh dau trong <GcsRoot>; $Installed: danh sach {name, version, key} cua cac muc Mission Planner trong danh sach phan mem.
function Test-GcsMpMarkerMatches($Marker, $Installed, [bool]$ZipPresent = $false) {
    if ($null -eq $Marker) { return $false }
    $codeRx = '^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$'
    $method = [string](Get-GcsProp $Marker 'method' '')
    if ($method -eq 'zip') { return $ZipPresent }
    if ($method -ne 'msi') { return $false }
    $keys = @()
    foreach ($k in @((Get-GcsProp $Marker 'uninstallKey' ''), (Get-GcsProp $Marker 'productCode' ''))) {
        if ($k -and ([string]$k -match $codeRx)) { $keys += [string]$k }
    }
    foreach ($i in @($Installed)) {
        $ik = [string](Get-GcsProp $i 'key' '')
        foreach ($k in $keys) { if ([string]::Equals($ik, $k, [StringComparison]::OrdinalIgnoreCase)) { return $true } }
    }
    return $false
}