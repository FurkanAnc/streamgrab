; Inno Setup betigi. Tek basina degil, packaging\build.ps1 uzerinden derlenir.
; Yonetici izni istemez; kullanici profiline kurulur.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7F3C2A61-5B0E-4D7B-9C41-2E8A6F1D3B90}
AppName=StreamGrab
AppVersion={#AppVersion}
AppPublisher=StreamGrab
DefaultDirName={localappdata}\Programs\StreamGrab
DefaultGroupName=StreamGrab
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=StreamGrab-Setup-{#AppVersion}
SetupIconFile=..\streamgrab\assets\icon.ico
UninstallDisplayIcon={app}\StreamGrab.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"

[Files]
Source: "..\dist\StreamGrab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\StreamGrab"; Filename: "{app}\StreamGrab.exe"
Name: "{userdesktop}\StreamGrab"; Filename: "{app}\StreamGrab.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StreamGrab.exe"; Description: "StreamGrab'i başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Ilk acilista indirilen araclar. Ayarlar, gecmis ve arsiv %APPDATA% altinda kalir.
Type: filesandordirs; Name: "{localappdata}\StreamGrab\bin"
