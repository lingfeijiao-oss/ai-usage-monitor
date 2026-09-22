#define MyAppName "AI Usage Monitor"
#define MyAppVersion "0.3.1"
#define MyAppExeName "AIUsageMonitor.exe"

[Setup]
AppId={{E1C0A802-53F5-4A52-9300-7196A4A034A7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\AI Usage Monitor
DefaultGroupName=AI Usage Monitor
OutputDir=..\..\release
OutputBaseFilename=AIUsageMonitor-Setup-Windows-x64
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
LicenseFile=..\..\LICENSE
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\..\dist\AIUsageMonitor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\AI Usage Monitor"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch AI Usage Monitor"; Flags: nowait postinstall skipifsilent
