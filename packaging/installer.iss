; Complete onedir installation. User data is deliberately outside {app}.
#ifndef BundleDir
  #error BundleDir must point to the verified AISWESystem directory
#endif
#ifndef InstallerOutput
  #error InstallerOutput must be a new artifact directory
#endif

[Setup]
AppId={{7202DDE2-BCB0-4CFE-8C15-33D97B136DD8}
AppName=AI Software Engineering System
AppVersion=0.1.0
AppPublisher=AI SWE System
DefaultDirName={localappdata}\Programs\AISWESystem
DefaultGroupName=AI Software Engineering System
DisableProgramGroupPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#InstallerOutput}
OutputBaseFilename=AISWESystem-v0.1.0-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\AISWESystem.exe
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=no

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AI Software Engineering System"; Filename: "{app}\AISWESystem.exe"; WorkingDir: "{app}"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AI Software Engineering System"; Filename: "{app}\AISWESystem.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\AISWESystem.exe"; Description: "Iniciar AI Software Engineering System"; Flags: nowait postinstall skipifsilent

; No [UninstallDelete] or user-data entries: uninstall removes only owned program
; files, shortcuts and its registration. %LOCALAPPDATA%/AISWESystem is preserved.
