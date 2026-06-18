Write-Host "Top-level backend folder/file sizes:" -ForegroundColor Cyan
Get-ChildItem .\backend -Force | ForEach-Object {
  $path = $_.FullName
  if ($_.PSIsContainer) {
    $size = (Get-ChildItem $path -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  } else {
    $size = $_.Length
  }
  [PSCustomObject]@{Name=$_.Name; SizeMB=[Math]::Round(($size/1MB),2)}
} | Sort-Object SizeMB -Descending | Select-Object -First 30 | Format-Table -AutoSize

Write-Host "Top-level webapp folder/file sizes:" -ForegroundColor Cyan
Get-ChildItem .\webapp -Force | ForEach-Object {
  $path = $_.FullName
  if ($_.PSIsContainer) {
    $size = (Get-ChildItem $path -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  } else {
    $size = $_.Length
  }
  [PSCustomObject]@{Name=$_.Name; SizeMB=[Math]::Round(($size/1MB),2)}
} | Sort-Object SizeMB -Descending | Select-Object -First 30 | Format-Table -AutoSize
