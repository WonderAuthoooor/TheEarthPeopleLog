param([string]$OutputDir = (Join-Path $PSScriptRoot 'graphics'))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
[System.IO.Directory]::CreateDirectory($OutputDir) | Out-Null
$bg=[System.Drawing.ColorTranslator]::FromHtml('#F4F2E9')
$ink=[System.Drawing.ColorTranslator]::FromHtml('#172B31')
$muted=[System.Drawing.ColorTranslator]::FromHtml('#526666')
$accent=[System.Drawing.ColorTranslator]::FromHtml('#007D70')
$cards=@(
 @{n='01'; label='今日地球记录'; title=@('AI → SI','名字升级了，','能力呢？'); body=@('特朗普推动行政部门调整用词','2026.09.29 事件回看'); source='来源：白宫 EO14434，2026-09-29'},
 @{n='02'; label='发生了什么'; title=@('美国行政部门','调整官方用词'); body=@('AI  →  SI / Super Intelligence','适用于相关官方用途','前提：在法律允许的范围内'); source='来源：白宫 EO14434，第2(a)条'},
 @{n='03'; label='白宫给出的理由'; title=@('新名字','更能体现潜力'); body=@('这是文件中的政府表述','不是独立的技术测评结论'); source='来源：白宫 EO14434，第1条'},
 @{n='04'; label='容易忽略的细节'; title=@('本令中的 SI','承接原有范围'); body=@('沿用现有法律中 AI 涵盖的','技术和系统范围','法律另有规定的除外'); source='来源：白宫 EO14434，第3(a)条'},
 @{n='05'; label='这意味着什么'; title=@('用词调整','≠','能力证明'); body=@('不能据此认定技术突破','也不等于全球统一改名'); source='编辑解读｜依据 EO14434 第2、3条'},
 @{n='06'; label='观察员备注'; title=@('名字可以先升级','能力还得','交作业。'); body=@('地球人日志','记录进展，也检查进度'); source='本页为原创观察评论'},
 @{n='07'; label='文明记账'; title=@('本次','0 分'); body=@('仅评名称替换本身','后续实际影响，继续观察','指数为编辑性观察账本'); source='白宫 EO14434｜GovInfo 91 FR 63129–63130'}
)
$script:fontFamily='Microsoft YaHei'
function Draw-Line($g,[string]$text,[single]$x,[single]$y,[single]$size,$color,[bool]$bold=$false){
 $style=[System.Drawing.FontStyle]::Regular
 if($bold){$style=[System.Drawing.FontStyle]::Bold}
 $font=New-Object System.Drawing.Font($script:fontFamily,$size,$style,[System.Drawing.GraphicsUnit]::Pixel)
 $brush=New-Object System.Drawing.SolidBrush($color)
 try{
  $measured=$g.MeasureString($text,$font)
  if($measured.Width -gt 840){throw "Line too wide ($($measured.Width)): $text"}
  $g.DrawString($text,$font,$brush,$x,$y)
 }finally{$font.Dispose();$brush.Dispose()}
}
foreach($c in $cards){
 $bmp=New-Object System.Drawing.Bitmap(1080,1920)
 $g=[System.Drawing.Graphics]::FromImage($bmp)
 try{
  $g.Clear($bg)
  $g.SmoothingMode=[System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint=[System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $brush=New-Object System.Drawing.SolidBrush($accent)
  $g.FillRectangle($brush,100,170,10,48)
  $brush.Dispose()
  Draw-Line $g '地球人日志' 132 166 38 $ink $true
  Draw-Line $g ('档案 001  /  '+$c.n) 132 230 26 $muted
  $pen=New-Object System.Drawing.Pen($ink,2)
  $g.DrawLine($pen,110,314,950,314)
  $pen.Dispose()
  Draw-Line $g $c.label 110 365 32 $accent $true
  $y=470
  foreach($line in $c.title){Draw-Line $g $line 104 $y 74 $ink $true;$y+=108}
  $y=920
  foreach($line in $c.body){Draw-Line $g $line 110 $y 39 $ink;$y+=72}
  Draw-Line $g 'AI 配音 · 原创解读' 110 1275 27 $accent
  Draw-Line $g $c.source 110 1334 25 $muted
  Draw-Line $g '核查：2026.10.11 14:16 北京时间' 110 1379 25 $muted
  Draw-Line $g 'EARTH PEOPLE LOG' 110 1550 24 $muted
  $bmp.Save((Join-Path $OutputDir ('scene-'+$c.n+'.png')),[System.Drawing.Imaging.ImageFormat]::Png)
 }finally{$g.Dispose();$bmp.Dispose()}
}
$sheet=New-Object System.Drawing.Bitmap(1120,1000)
$g=[System.Drawing.Graphics]::FromImage($sheet)
try{
 $g.Clear([System.Drawing.Color]::FromArgb(220,224,222))
 for($i=0;$i -lt $cards.Count;$i++){
  $img=[System.Drawing.Image]::FromFile((Join-Path $OutputDir ('scene-'+$cards[$i].n+'.png')))
  try{$x=($i%4)*280+6;$y=[math]::Floor($i/4)*500+6;$g.DrawImage($img,[int]$x,[int]$y,268,476)}finally{$img.Dispose()}
 }
 $sheet.Save((Join-Path $OutputDir 'preview-contact-sheet.png'),[System.Drawing.Imaging.ImageFormat]::Png)
}finally{$g.Dispose();$sheet.Dispose()}
'Rendered 7 original text cards (1080x1920) and preview contact sheet.'
