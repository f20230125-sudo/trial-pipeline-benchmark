# Opens the workbook in Excel, recalculates and saves it (so previews and other readers see values, not zeros),
# and optionally exports each sheet to PDF.
param([string]$Path, [string]$PdfDir = "")
$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Path)
  $wb.Application.CalculateFull()
  if ($PdfDir) {
    New-Item -ItemType Directory -Force $PdfDir | Out-Null
    foreach ($name in 'Inputs','Scorecard','Area matrix','Expiring revenue','Checks','Read me') {
      $ws = $wb.Worksheets.Item($name)
      $ws.PageSetup.Orientation = 2; $ws.PageSetup.Zoom = $false; $ws.PageSetup.FitToPagesWide = 1; $ws.PageSetup.FitToPagesTall = 1
      $ws.ExportAsFixedFormat(0, (Join-Path $PdfDir ($name.Replace(' ','_') + '.pdf')))
    }
  }
  $wb.Worksheets.Item('Inputs').Activate()
  $wb.Save(); $wb.Close($true); "recalculated and saved"
} finally { $xl.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
