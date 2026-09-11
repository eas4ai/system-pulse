; Compile through scripts/system-pulse/package_windows_installer.py.
#ifndef PackageDir
  #error PackageDir must identify a verified signed native package
#endif
#ifndef PawnIOSetup
  #error PawnIOSetup must identify the pinned official PawnIO 2.2.0 installer
#endif

[Setup]
AppId={{82C76189-3134-4B89-A742-5CBAA4388645}
AppName=System Pulse
AppVersion={#AppVersion}
AppPublisher=System Pulse
AppPublisherURL=https://github.com/eas4ai/system-pulse
DefaultDirName={autopf}\System Pulse
DefaultGroupName=System Pulse
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
OutputDir={#OutputDir}
OutputBaseFilename=system-pulse-{#AppVersion}-windows-x86_64-{#SourceRevision}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile={#PackageDir}\COPYING
UninstallDisplayIcon={app}\system-pulse.exe
SignTool=systempulse
SignedUninstaller=yes

[Tasks]
Name: "cputemperature"; Description: "Install PawnIO for optional CPU temperature readings (administrator access)"; GroupDescription: "Hardware sensor access:"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PawnIOSetup}"; DestName: "PawnIO_setup-2.2.0.exe"; Flags: dontcopy

[Icons]
Name: "{group}\System Pulse"; Filename: "{app}\system-pulse.exe"
Name: "{autodesktop}\System Pulse"; Filename: "{app}\system-pulse.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\system-pulse.exe"; Description: "Launch System Pulse"; Flags: postinstall nowait skipifsilent unchecked runasoriginaluser

[Code]
const
  PawnIOKey = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO';
  PawnIOHash = '1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032';

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  InstallerPath: String;
  ExitCode: Integer;
begin
  Result := '';
  if not WizardIsTaskSelected('cputemperature') then Exit;
  { PawnIO is shared by other applications. Never replace or downgrade an existing installation. }
  if RegKeyExists(HKLM64, PawnIOKey) then begin
    Log('Keeping the existing shared PawnIO installation.');
    Exit;
  end;
  ExtractTemporaryFile('PawnIO_setup-2.2.0.exe');
  InstallerPath := ExpandConstant('{tmp}\PawnIO_setup-2.2.0.exe');
  if CompareText(GetSHA256OfFile(InstallerPath), PawnIOHash) <> 0 then begin
    Result := 'The bundled PawnIO installer failed its integrity check.';
    Exit;
  end;
  if not Exec(InstallerPath, '-install -silent', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
    Result := 'PawnIO could not start. Retry, or deselect CPU temperature support to install System Pulse without it.';
    Exit;
  end;
  if (ExitCode <> 0) and (ExitCode <> 3010) then begin
    Result := 'PawnIO installation failed with exit code ' + IntToStr(ExitCode) + '. Retry, or deselect CPU temperature support.';
    Exit;
  end;
  if not RegKeyExists(HKLM64, PawnIOKey) then begin
    Result := 'PawnIO did not register its installation. Retry, or deselect CPU temperature support.';
    Exit;
  end;
  NeedsRestart := ExitCode = 3010;
end;
