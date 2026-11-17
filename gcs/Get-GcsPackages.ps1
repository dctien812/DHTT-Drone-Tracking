<#
.SYNOPSIS
  Tai cac goi trong manifest.json vao gcs\packages\ va ghi packages\checksums.json
  (SHA256 + trang thai chu ky Authenticode, subject, thumbprint cua tung .msi/.exe).
  Chay tren MOT MAY CO INTERNET. Khong can admin.
.PARAMETER CheckOnly
  Chi gui yeu cau HEAD de kiem URL con song, in bang, khong tai gi.
.PARAMETER RequiredOnly
  Chi tai goi required=true.
.PARAMETER Force
  Tai lai ke ca khi file da co va khop checksum da ghi.
.EXAMPLE
  .\Get-GcsPackages.ps1 -CheckOnly
  .\Get-GcsPackages.ps1
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$RequiredOnly,
    [switch]$Force,
    [string]$ManifestPath = '',
    [string]$OutDir = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ManifestPath) { $ManifestPath = Join-Path $ScriptDir 'manifest.json' }
if (-not $OutDir) { $OutDir = Join-Path $ScriptDir 'packages' }
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

function Get-Prop($obj, [string]$name, $default = $null) {
    $p = $obj.PSObject.Properties[$name]
    if ($null -eq $p) { return $default }
    return $p.Value
}
$logicPath = Join-Path $ScriptDir 'GcsLogic.ps1'
if (-not (Test-Path -LiteralPath $logicPath)) { throw "Thieu $logicPath" }
. $logicPath

# Ban ghi checksums.json: SHA256 + trang thai chu ky Authenticode (.msi/.exe). File .zip khong co chu ky: signed=false.
# SHA256 nam cung USB chi chong hong file; chu ky so (thumbprint/subject nguoi ky) moi la diem tin cay (xem README).
function New-PackageRecord($p, [string]$dest, [string]$url, [string]$hash, $fi, [string]$downloaded) {
    $signed = $false
    $status = 'NotApplicable (khong phai .msi/.exe)'
    $subject = ''
    $thumb = ''
    $ext = [IO.Path]::GetExtension($dest).ToLowerInvariant()
    if ($ext -eq '.msi' -or $ext -eq '.exe') {
        $sig = Get-GcsFileSignature $dest
        $status = $sig.status; $subject = $sig.subject; $thumb = $sig.thumbprint
        $signed = ($sig.status -eq 'Valid')
    } elseif ($ext -eq '.zip') { $status = 'NotApplicable (zip khong co chu ky)' }
    return [pscustomobject]@{
        id = $p.id; file = $p.file; url = $url; sha256 = $hash; size = $fi.Length
        downloaded = $downloaded
        signed = $signed; signatureStatus = $status; signerSubject = $subject; signerThumbprint = $thumb
    }
}

# Chuoi mo ta nguoi ky + doi chieu expectedPublisher trong manifest: day la thong tin ban DOC de dien expectedPublisher (khong tu dien).
function Format-SignerNote($rec, $p) {
    if ($rec.file -notmatch '\.(msi|exe)$') { return '' }
    $s = "NGUOI KY: subject=[{0}] thumbprint=[{1}] trang thai={2}" -f $rec.signerSubject, $rec.signerThumbprint, $rec.signatureStatus
    $pins = @(Get-GcsPinnedPublishers $p)
    if ($pins.Count -eq 0) { return $s + '; expectedPublisher CHUA dat (Install se hoi xac nhan tung goi)' }
    if (Test-GcsPublisherMatch ([string]$rec.signerSubject) $pins) { return $s + '; khop expectedPublisher' }
    return $s + '; KHONG KHOP expectedPublisher (Install se dung goi nay)'
}

if (-not (Test-Path -LiteralPath $ManifestPath)) { throw "Khong thay manifest: $ManifestPath" }
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$pkgs = @($manifest.packages)
if ($RequiredOnly) { $pkgs = @($pkgs | Where-Object { $_.required }) }

function Test-Url([string]$url) {
    # Tra ve doi tuong: Status, Size, Note
    try {
        $r = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 30
        $len = $null
        if ($r.Headers.ContainsKey('Content-Length')) { $len = [int64]($r.Headers['Content-Length'] | Select-Object -First 1) }
        return [pscustomobject]@{ Status = [int]$r.StatusCode; Size = $len; Note = 'OK' }
    }
    catch {
        $code = 0
        $resp = $_.Exception.PSObject.Properties['Response']
        if ($null -ne $resp -and $null -ne $resp.Value) { $code = [int]$resp.Value.StatusCode }
        return [pscustomobject]@{ Status = $code; Size = $null; Note = $_.Exception.Message }
    }
}

$rows = @()
$requiredFailed = $false

if ($CheckOnly) {
    foreach ($p in $pkgs) {
        $url = Get-Prop $p 'url'
        if (-not $url) {
            $rows += [pscustomobject]@{ Id = $p.id; Required = $p.required; Verified = $p.verified; Status = 'n/a'; SizeMB = ''; Note = ('winget: ' + (Get-Prop $p 'winget' '')) }
            continue
        }
        $t = Test-Url $url
        $mb = ''
        if ($null -ne $t.Size) { $mb = [math]::Round($t.Size / 1MB, 1) }
        $state = if ($t.Status -ge 200 -and $t.Status -lt 300) { 'SONG' } else { 'LOI' }
        if ($state -eq 'LOI' -and $p.required) { $requiredFailed = $true }
        $note = $t.Note
        if ($url -like 'http://*') { $note = 'URL http (khong ma hoa); ' + $note }
        $rows += [pscustomobject]@{ Id = $p.id; Required = $p.required; Verified = $p.verified; Status = ("{0} {1}" -f $state, $t.Status); SizeMB = $mb; Note = $note }
    }
    $rows | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
    if ($requiredFailed) { Write-Host 'Co goi BAT BUOC khong truy cap duoc.'; exit 1 }
    exit 0
}

# ---- Che do tai ----
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$sumPath = Join-Path $OutDir 'checksums.json'
$existing = @{}
if (Test-Path -LiteralPath $sumPath) {
    try {
        $old = Get-Content -LiteralPath $sumPath -Raw | ConvertFrom-Json
        foreach ($e in @($old.packages)) { $existing[$e.file] = $e }
    } catch { Write-Warning "checksums.json cu khong doc duoc, se ghi moi: $($_.Exception.Message)" }
}

foreach ($p in $pkgs) {
    $url = Get-Prop $p 'url'
    if (-not $url) {
        $rows += [pscustomobject]@{ Id = $p.id; Required = $p.required; Result = 'BO QUA'; Note = 'goi winget, cai tren laptop khi co Internet' }
        continue
    }
    $dest = Join-Path $OutDir $p.file
    try {
        if ((Test-Path -LiteralPath $dest) -and -not $Force -and $existing.ContainsKey($p.file)) {
            $h = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
            if ($h -eq $existing[$p.file].sha256) {
                # Khong tai lai nhung ghi moi trang thai chu ky (ban ghi cu co the chua co truong nay)
                $old = $existing[$p.file]
                $rec = New-PackageRecord $p $dest ([string](Get-Prop $old 'url' $url)) $h (Get-Item -LiteralPath $dest) ([string](Get-Prop $old 'downloaded' ''))
                $existing[$p.file] = $rec
                $rows += [pscustomobject]@{ Id = $p.id; Required = $p.required; Result = 'DA CO'; Note = ('checksum khop, khong tai lai; chu ky: ' + $rec.signatureStatus + '; ' + (Format-SignerNote $rec $p)) }
                continue
            }
        }
        Write-Host ("Dang tai {0} ..." -f $url)
        $part = $dest + '.part'
        if (Test-Path -LiteralPath $part) { Remove-Item -LiteralPath $part -Force }
        Invoke-WebRequest -Uri $url -OutFile $part -UseBasicParsing -TimeoutSec 1800
        Move-Item -LiteralPath $part -Destination $dest -Force
        $fi = Get-Item -LiteralPath $dest
        $hash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
        $rec = New-PackageRecord $p $dest $url $hash $fi ((Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz'))
        $existing[$p.file] = $rec
        $sigNote = 'chu ky: ' + $rec.signatureStatus
        if (-not $rec.signed -and $rec.file -match '\.(msi|exe)$') { $sigNote = 'CHU KY KHONG HOP LE (' + $rec.signatureStatus + '): Install-Gcs se dung goi nay tru khi dung -AllowUnsigned <id goi>' }
        $rows += [pscustomobject]@{ Id = $p.id; Required = $p.required; Result = 'DA TAI'; Note = ("{0} MB, SHA256 {1}; {2}; {3}" -f [math]::Round($fi.Length / 1MB, 1), $hash.Substring(0, 12), $sigNote, (Format-SignerNote $rec $p)) }
    }
    catch {
        if ($p.required) { $requiredFailed = $true }
        $rows += [pscustomobject]@{ Id = $p.id; Required = $p.required; Result = 'LOI'; Note = $_.Exception.Message }
        if (Test-Path -LiteralPath ($dest + '.part')) { Remove-Item -LiteralPath ($dest + '.part') -Force -ErrorAction SilentlyContinue }
    }
}

$out = [ordered]@{
    generated = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    packages  = @($existing.Values | Sort-Object id)
}
($out | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $sumPath -Encoding UTF8

$rows | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
Write-Host "Da ghi $sumPath"
if ($requiredFailed) { Write-Host 'LOI: co goi BAT BUOC tai that bai. Chay lai truoc khi chep sang USB.'; exit 1 }
exit 0
