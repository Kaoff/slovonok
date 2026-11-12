; Inno Setup script. Compile with build.ps1 (it passes AppVersion and SourceDir), or by hand:
;   ISCC.exe /DAppVersion=0.1.0 /DSourceDir=dist\Slovonok installer.iss
;
; Per-user install (no administrator rights): the app can then update itself without a UAC prompt.
; The same installer is what the in-app updater downloads and runs silently.

#ifndef AppVersion
  #error Pass /DAppVersion=x.y.z (build.ps1 reads it from backend/version.py)
#endif
#ifndef SourceDir
  #define SourceDir "dist\Slovonok"
#endif

#define AppName "Slovonok"
#define AppExe "Slovonok.exe"

[Setup]
; Identifies the app for upgrades and uninstall: NEVER change it, or an update would install
; next to the old version instead of replacing it.
AppId={{DE448794-5C21-4A39-B724-8740863AF477}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Slovonok
AppPublisherURL=https://github.com/Kaoff/slovonok
AppSupportURL=https://github.com/Kaoff/slovonok/issues
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; The app creates this mutex while it runs: Setup and the uninstaller then ask to close it first
AppMutex=Slovonok.SingleInstance
LicenseFile=..\LICENSE
SetupIconFile=..\backend\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputDir=output
OutputBaseFilename=Slovonok-Setup-{#AppVersion}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked
Name: "autostart"; Description: "{cm:AutoStart}"; Flags: unchecked

[CustomMessages]
french.AutoStart=Lancer Slovonok au démarrage de Windows (réduit dans la zone de notification)
english.AutoStart=Start Slovonok with Windows (minimized to the tray)
french.KeepData=Supprimer aussi vos réglages, mots, punitions et médias ?%n%nChoisissez Non pour les conserver (utile si vous réinstallez plus tard).
english.KeepData=Also delete your settings, words, punishments and media?%n%nChoose No to keep them (useful if you reinstall later).

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; An update must not leave the previous version's libraries behind in _internal
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExe}"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
; Normal install: the usual "launch" checkbox on the last page
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Silent install = the in-app updater: bring the app back (NORELAUNCH=1 is for tests)
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:NORELAUNCH|0}') <> '1');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { Settings and media live in %APPDATA%\Slovonok, outside the install folder: ask before removing them }
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(CustomMessage('KeepData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\{#AppName}'), True, True, True);
end;
