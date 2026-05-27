#define MyAppName "Movie Watchlist"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "TurtleWithGlasses"
#define MyAppExeName "MovieWatchlist.exe"
#define MyAppInstallDir "{localappdata}\MovieWatchlist"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppVerName={#MyAppName} {#MyAppVersion}

; Install to AppData\Local (no admin rights needed — required for auto-updater)
DefaultDirName={#MyAppInstallDir}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output
OutputDir=installer
OutputBaseFilename=MovieWatchlistInstaller
SetupIconFile=assets\movie-icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; No admin required — user-level install so the auto-updater can replace the exe
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

; Prevent running the old version while installing an update
CloseApplications=yes
CloseApplicationsFilter=MovieWatchlist.exe
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Main executable
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Google Drive credentials (only copied if the file exists next to the .iss)
Source: "dist\credentials.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"

; Desktop (optional — user chooses during install)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch the app after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up files the auto-updater creates at runtime
Type: files; Name: "{app}\token.json"
Type: files; Name: "{app}\_update_staged.exe"
Type: files; Name: "{app}\_old_version.exe"
Type: files; Name: "{app}\watchlist.db"
