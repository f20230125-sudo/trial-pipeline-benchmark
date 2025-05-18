param([string]$Path, [string]$Out)
# Drives Excel itself through six input scenarios and writes every Scorecard result to JSON, so that
# tools/verify_workbook.py can compare Excel's own formulas with an independent Python calculation.
$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Path)
  $inp = $wb.Worksheets.Item('Inputs'); $sc = $wb.Worksheets.Item('Scorecard'); $chk = $wb.Worksheets.Item('Checks')
  $ex = $wb.Worksheets.Item('Expiring revenue'); $mx = $wb.Worksheets.Item('Area matrix')
  $scenarios = @(
    @{ id='S1'; focus='MSD';         area='All areas';                    stage='All clinical';   scope='Active only';  window=24; asof='2026-10-14'; preset='Balanced';  horizon=2028; custom=@(25,25,25,15,10) },
    @{ id='S2'; focus='AstraZeneca'; area='Oncology';                     stage='Late (Phase 3)'; scope='Active only';  window=18; asof='2026-10-14'; preset='Near-term'; horizon=2027; custom=@(25,25,25,15,10) },
    @{ id='S3'; focus='Lilly';       area='Diabetes & obesity';           stage='All clinical';   scope='All statuses'; window=12; asof='2026-10-14'; preset='Balanced';  horizon=2026; custom=@(25,25,25,15,10) },
    @{ id='S4'; focus='MSD';         area='Infectious disease (non-HIV)'; stage='Mid (Phase 2)';  scope='Active only';  window=36; asof='2026-10-14'; preset='Regional';  horizon=2028; custom=@(25,25,25,15,10) },
    @{ id='S5'; focus='Pfizer';      area='All areas';                    stage='Early (Phase 1)'; scope='Active only'; window=24; asof='2026-10-14'; preset='Custom';    horizon=2027; custom=@(40,10,10,30,10) },
    @{ id='S6'; focus='Novartis';    area='Immunology & inflammation';    stage='All clinical';   scope='All statuses'; window=24; asof='2026-06-30'; preset='Near-term'; horizon=2028; custom=@(25,25,25,15,10) }
  )
  $result = @()
  foreach ($s in $scenarios) {
    $inp.Range('C4').Value2 = $s.focus
    $inp.Range('C5').Value2 = $s.area
    $inp.Range('C6').Value2 = $s.stage
    $inp.Range('C7').Value2 = $s.scope
    $inp.Range('C8').Value2 = [double]$s.window
    $inp.Range('C9').Value2 = [double]([datetime]::ParseExact($s.asof, 'yyyy-MM-dd', $null)).ToOADate()
    $inp.Range('C10').Value2 = $s.preset
    for ($j = 0; $j -lt 5; $j++) { $inp.Cells.Item(16, 3 + $j).Value2 = [double]$s.custom[$j] }
    $ex.Range('C4').Value2 = [double]$s.horizon
    $wb.Application.CalculateFull()
    $vals = $sc.Range('A8:T19').Value2
    $rows = @()
    for ($i = 1; $i -le 12; $i++) {
      $r = @(); for ($c = 1; $c -le 20; $c++) { $r += ,$vals[$i, $c] }
      $rows += ,$r
    }
    $checks = @(); foreach ($r in 5..10) { $checks += [string]$chk.Cells.Item($r, 5).Value2 }
    $exp = @(); foreach ($r in 13..15) { $exp += ,@([string]$ex.Cells.Item($r,1).Value2, $ex.Cells.Item($r,2).Value2, $ex.Cells.Item($r,3).Value2, $ex.Cells.Item($r,4).Value2, $ex.Cells.Item($r,5).Value2) }
    $mxv = $mx.Range('B5:S16').Value2
    $matrix = @(); for ($i = 1; $i -le 12; $i++) { $r = @(); for ($c = 1; $c -le 18; $c++) { $r += ,$mxv[$i, $c] }; $matrix += ,$r }
    $result += [pscustomobject]@{ id=$s.id; inputs=$s; rows=$rows; checks=$checks; overall=[string]$chk.Range('E12').Value2;
        focus_rank=$sc.Range('E4').Value2; focus_tier=[string]$sc.Range('H4').Value2; focus_studies=$sc.Range('J4').Value2;
        peer_median=$sc.Range('L4').Value2; gap=$sc.Range('N4').Value2; expiring=$exp; matrix=$matrix;
        weights=@($inp.Range('C17').Value2, $inp.Range('D17').Value2, $inp.Range('E17').Value2, $inp.Range('F17').Value2, $inp.Range('G17').Value2) }
  }
  $result | ConvertTo-Json -Depth 7 -Compress | Set-Content -Path $Out -Encoding UTF8
  $wb.Close($false)
  "ok"
} finally { $xl.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
