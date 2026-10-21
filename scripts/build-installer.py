"""Compile a per-user NSIS installer; never installs anything during build."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--app',choices=('studio','globe'),default='studio')
options=parser.parse_args()
if options.app=='globe':
    from globe_app import __version__
    PRODUCT='EarthPeopleLogGlobe';TITLE='地球地点动画';ICON=ROOT/'globe_app/assets/app-icon.ico'
    APP=ROOT/'dist/globe'/__version__/PRODUCT
else:
    from studio import __version__
    PRODUCT='EarthPeopleLogStudio';TITLE='地球人日志工作室';ICON=ROOT/'studio/assets/app-icon.ico'
    APP=ROOT/'dist'/__version__/PRODUCT
NSIS = ROOT / ".runtime" / "nsis" / "nsis-3.11" / "makensis.exe"


def escaped(value):
    return str(value).replace("$", "$$").replace('"', '$\\"')


if __name__ == "__main__":
    files = [p for p in APP.rglob("*") if p.is_file()]
    directories = sorted([p for p in APP.rglob("*") if p.is_dir()], key=lambda p: len(p.parts), reverse=True)
    # Exact-file uninstall preserves workspace files even if placed in install dir.
    uninstall = "\n".join(f'  Delete "$INSTDIR\\{escaped(p.relative_to(APP))}"' for p in files)
    uninstall += "\n" + "\n".join(f'  RMDir "$INSTDIR\\{escaped(p.relative_to(APP))}"' for p in directories)
    script = r'''
Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
Name "地球人日志工作室 __VERSION__"
OutFile "__OUTPUT__"
InstallDir "$LOCALAPPDATA\Programs\EarthPeopleLogStudio"
RequestExecutionLevel user
SetCompressor zlib
Var TestMode
!define MUI_ICON "__ICON__"
!define MUI_UNICON "__ICON__"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
Function .onInit
  SetShellVarContext current
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/TEST" $R1
  ${IfNot} ${Errors}
    StrCpy $TestMode "1"
  ${EndIf}
FunctionEnd
Section "工作室"
  SetOutPath "$INSTDIR"
  File /r "__APP__\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  ${If} $TestMode != "1"
    CreateDirectory "$SMPROGRAMS\地球人日志工作室"
    CreateShortcut "$SMPROGRAMS\地球人日志工作室\地球人日志工作室.lnk" "$INSTDIR\EarthPeopleLogStudio.exe" "" "$INSTDIR\EarthPeopleLogStudio.exe" 0
    CreateShortcut "$DESKTOP\地球人日志工作室.lnk" "$INSTDIR\EarthPeopleLogStudio.exe" "" "$INSTDIR\EarthPeopleLogStudio.exe" 0
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EarthPeopleLogStudio" "DisplayName" "地球人日志工作室"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EarthPeopleLogStudio" "DisplayVersion" "__VERSION__"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EarthPeopleLogStudio" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EarthPeopleLogStudio" "DisplayIcon" "$INSTDIR\EarthPeopleLogStudio.exe"
  ${Else}
    FileOpen $R0 "$INSTDIR\test-install.marker" w
    FileWrite $R0 "test"
    FileClose $R0
  ${EndIf}
SectionEnd
Section "Uninstall"
  SetShellVarContext current
  IfFileExists "$INSTDIR\test-install.marker" skip_registry
    Delete "$DESKTOP\地球人日志工作室.lnk"
    Delete "$SMPROGRAMS\地球人日志工作室\地球人日志工作室.lnk"
    RMDir "$SMPROGRAMS\地球人日志工作室"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EarthPeopleLogStudio"
  skip_registry:
  __UNINSTALL__
  Delete "$INSTDIR\test-install.marker"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
'''.replace('EarthPeopleLogStudio',PRODUCT).replace('地球人日志工作室',TITLE).replace("__OUTPUT__", escaped(ROOT / "dist" / f"{PRODUCT}-{__version__}-Setup.exe")).replace("__APP__", escaped(APP)).replace("__UNINSTALL__", uninstall).replace("__VERSION__", __version__).replace("__ICON__", escaped(ICON))
    destination = (ROOT / "build" / "globe" / __version__ if options.app=="globe" else ROOT / "build" / __version__) / "studio-installer.nsi"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(script, encoding="utf-8-sig")
    subprocess.run([str(NSIS), "/V2", str(destination)], check=True, cwd=ROOT)
    print(ROOT / "dist" / f"{PRODUCT}-{__version__}-Setup.exe")
