# ============================================================
# 文件检索插件 v1.0
# 作者：AI助手
# 功能：扫描所有磁盘，生成 HTML 可浏览报告
# 用法：在 PowerShell 中运行此脚本，然后打开生成的 HTML 文件
# ============================================================

param(
    [string]$KeyWord = "",          # 搜索关键词，留空则列出所有
    [string]$Extension = "",        # 文件扩展名，如 .pdf .docx .mp4
    [string]$OutputPath = "C:\Users\yyds\Desktop\AI日记本\检索报告_$(Get-Date -Format 'yyyyMMdd_HHmmss').html"
)

Write-Host "🔍 开始扫描磁盘..." -ForegroundColor Cyan

# 获取所有逻辑磁盘
$drives = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Root -match '^[A-Z]:\\' }

$allFiles = @()
$driveStats = @()

foreach ($drive in $drives) {
    $root = $drive.Root
    Write-Host "  扫描: $root ..." -ForegroundColor Yellow
    
    try {
        $files = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object {
                ($KeyWord -eq "" -or $_.Name -like "*$KeyWord*") -and
                ($Extension -eq "" -or $_.Extension -eq $Extension)
            } |
            Select-Object Name, DirectoryName, Extension, 
                @{N="大小(MB)";E={[math]::Round($_.Length/1MB, 2)}},
                LastWriteTime |
            Sort-Object LastWriteTime -Descending
        
        $driveStats += [PSCustomObject]@{
            盘符 = $root
            文件数 = $files.Count
        }
        $allFiles += $files
    } catch {
        Write-Host "    跳过 $root (无权限或不可访问)" -ForegroundColor Red
    }
}

Write-Host "✅ 扫描完成，共找到 $($allFiles.Count) 个文件" -ForegroundColor Green

# 生成 HTML 报告
$scanTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$keyword_display = if ($KeyWord) { $KeyWord } else { "全部" }
$ext_display = if ($Extension) { $Extension } else { "全部" }

$tableRows = ""
foreach ($f in $allFiles | Select-Object -First 5000) {
    $sizeDisplay = if ($f."大小(MB)" -lt 1) { "<span style='color:#aaa'>&lt;1 MB</span>" } 
                   elseif ($f."大小(MB)" -gt 500) { "<span style='color:#e74c3c;font-weight:bold'>$($f.'大小(MB)') MB</span>" }
                   else { "$($f.'大小(MB)') MB" }
    
    $extBadge = switch ($f.Extension.ToLower()) {
        ".pdf"  { "<span class='badge pdf'>PDF</span>" }
        ".docx" { "<span class='badge docx'>DOCX</span>" }
        ".xlsx" { "<span class='badge xlsx'>XLSX</span>" }
        ".mp4"  { "<span class='badge mp4'>MP4</span>" }
        ".mp3"  { "<span class='badge mp3'>MP3</span>" }
        ".zip"  { "<span class='badge zip'>ZIP</span>" }
        ".exe"  { "<span class='badge exe'>EXE</span>" }
        ".png"  { "<span class='badge img'>PNG</span>" }
        ".jpg"  { "<span class='badge img'>JPG</span>" }
        default { "<span class='badge other'>$($f.Extension)</span>" }
    }
    
    $tableRows += "<tr><td>$($f.Name) $extBadge</td><td class='path'>$($f.DirectoryName)</td><td>$sizeDisplay</td><td>$($f.LastWriteTime.ToString('yyyy-MM-dd'))</td></tr>`n"
}

$statsHtml = ""
foreach ($s in $driveStats) {
    $statsHtml += "<div class='stat-card'><div class='stat-drive'>$($s.盘符)</div><div class='stat-count'>$($s.文件数) 个文件</div></div>"
}

$html = @"
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文件检索报告 - $scanTime</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Microsoft YaHei', sans-serif; background: #0f1117; color: #e0e0e0; }
  .header { background: linear-gradient(135deg, #1a1f2e 0%, #16213e 100%); padding: 30px 40px; border-bottom: 1px solid #2d3561; }
  .header h1 { font-size: 24px; color: #7c83fd; margin-bottom: 8px; }
  .header p { color: #888; font-size: 13px; }
  .meta { display: flex; gap: 20px; margin-top: 15px; flex-wrap: wrap; }
  .meta-item { background: #1e2235; border-radius: 8px; padding: 10px 18px; }
  .meta-item .label { font-size: 11px; color: #666; text-transform: uppercase; }
  .meta-item .value { font-size: 18px; color: #7c83fd; font-weight: bold; margin-top: 3px; }
  .stats { display: flex; gap: 15px; padding: 20px 40px; flex-wrap: wrap; background: #0f1117; }
  .stat-card { background: #1a1f2e; border-radius: 10px; padding: 15px 25px; border-left: 3px solid #7c83fd; }
  .stat-drive { font-size: 20px; font-weight: bold; color: #fff; }
  .stat-count { font-size: 12px; color: #888; margin-top: 4px; }
  .search-bar { padding: 15px 40px; background: #0f1117; }
  .search-bar input { width: 100%; max-width: 500px; padding: 10px 15px; border-radius: 8px; border: 1px solid #2d3561; background: #1a1f2e; color: #fff; font-size: 14px; outline: none; }
  .search-bar input:focus { border-color: #7c83fd; }
  table { width: 100%; border-collapse: collapse; }
  thead th { background: #1a1f2e; padding: 12px 40px; text-align: left; font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 1px; position: sticky; top: 0; }
  tbody tr { border-bottom: 1px solid #1a1f2e; }
  tbody tr:hover { background: #1a1f2e; }
  tbody td { padding: 10px 40px; font-size: 13px; }
  .path { color: #555; font-size: 11px; word-break: break-all; max-width: 400px; }
  .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px; vertical-align: middle; }
  .badge.pdf { background: #e74c3c22; color: #e74c3c; }
  .badge.docx { background: #3498db22; color: #3498db; }
  .badge.xlsx { background: #2ecc7122; color: #2ecc71; }
  .badge.mp4, .badge.mp3 { background: #9b59b622; color: #9b59b6; }
  .badge.zip { background: #f39c1222; color: #f39c12; }
  .badge.exe { background: #e74c3c22; color: #e74c3c; }
  .badge.img { background: #1abc9c22; color: #1abc9c; }
  .badge.other { background: #ffffff11; color: #999; }
  .footer { padding: 20px 40px; color: #444; font-size: 12px; text-align: center; }
</style>
</head>
<body>
<div class="header">
  <h1>🗂️ 文件检索报告</h1>
  <p>由 AI助手 生成 · $scanTime</p>
  <div class="meta">
    <div class="meta-item"><div class="label">总文件数</div><div class="value">$($allFiles.Count)</div></div>
    <div class="meta-item"><div class="label">关键词</div><div class="value">$keyword_display</div></div>
    <div class="meta-item"><div class="label">扩展名</div><div class="value">$ext_display</div></div>
    <div class="meta-item"><div class="label">扫描磁盘</div><div class="value">$($drives.Count) 个</div></div>
  </div>
</div>

<div class="stats">$statsHtml</div>

<div class="search-bar">
  <input type="text" id="searchInput" placeholder="🔍 在结果中搜索文件名..." oninput="filterTable(this.value)">
</div>

<table id="fileTable">
<thead><tr><th>文件名</th><th>路径</th><th>大小</th><th>修改时间</th></tr></thead>
<tbody>
$tableRows
</tbody>
</table>

<div class="footer">共展示前 5000 条记录 · 按修改时间倒序 · 由 AI助手文件检索插件生成</div>

<script>
function filterTable(q) {
  const rows = document.querySelectorAll('#fileTable tbody tr');
  q = q.toLowerCase();
  rows.forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}
</script>
</body>
</html>
"@

$html | Out-File -FilePath $OutputPath -Encoding UTF8
Write-Host "📄 报告已生成：$OutputPath" -ForegroundColor Green

# 打开报告
Start-Process $OutputPath
Write-Host "🌐 已在浏览器中打开报告" -ForegroundColor Cyan
