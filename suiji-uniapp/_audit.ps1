# 审计：1) keyframes 内使用 rpx  2) 残留内联 <svg>  3) 触屏不可靠的 :active  4) gap/backdrop-filter 计数
$files = Get-ChildItem -Path 'd:\project\traeData\suiji\suiji-uniapp\src' -Recurse -Include *.vue
foreach ($f in $files) {
  $c = [IO.File]::ReadAllText($f.FullName)
  # keyframes blocks (naive brace matching)
  $matches2 = [regex]::Matches($c, '@keyframes\s+[\w-]+\s*\{')
  foreach ($m in $matches2) {
    $i = $m.Index + $m.Length - 1
    $depth = 0; $start = $i
    while ($i -lt $c.Length) {
      $ch = $c[$i]
      if ($ch -eq '{') { $depth++ }
      elseif ($ch -eq '}') { $depth--; if ($depth -eq 0) { break } }
      $i++
    }
    $block = $c.Substring($start, $i - $start + 1)
    if ($block -match '\d+rpx') {
      Write-Host ("KEYFRAMES-RPX: {0} :: {1}" -f $f.Name, ($block -replace '\s+', ' ').Substring(0, [Math]::Min(120, $block.Length)))
    }
  }
  if ($c -match '<svg') { Write-Host ("INLINE-SVG: " + $f.Name) }
  $act = ([regex]::Matches($c, ':active')).Count
  if ($act -gt 0) { Write-Host ("ACTIVE-PSUDO({0}): {1}" -f $act, $f.Name) }
}
