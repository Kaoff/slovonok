# Releasing Slovonok

A release is a GitHub release `vX.Y.Z` carrying the installer. The app finds it by itself:
it asks `releases/latest` at startup, every six hours and when "Check for updates" is clicked.

## One-time setup

- The repository **must be public**: the app reads its releases anonymously. (It also is what
  the GPL requires: the source of what you ship must be available.)
- On the build machine: the backend venv with `pip install -r backend/requirements-build.txt`,
  Node.js, espeak-ng (the `.msi`), the Vosk model in `backend/models/`, and Inno Setup 6
  (`winget install JRSoftware.InnoSetup --scope user`).

## Making a release

1. **Bump the version** in `backend/version.py` (`__version__ = "0.2.0"`), commit it.
   Plain `MAJOR.MINOR.PATCH` only: the updater compares the numbers.
2. **Check everything**:
   `python -m unittest test_detection test_words test_fuzzy test_engine test_updater` in `backend/`,
   `npm run check && npm run lint && npm run test:unit -- --run --project server` in `frontend/`.
3. **Build**: `powershell -File packaging\build.ps1`
   It builds the frontend, packages the app with PyInstaller, runs the package's self-test
   (`Slovonok.exe --smoke`: phonemizer, Vosk model, ffmpeg, Windows audio API, web engine, served
   pages) and **refuses to make an installer if it fails**, then compiles the installer.
   Output: `packaging\output\Slovonok-Setup-0.2.0.exe` and `Slovonok-Setup-0.2.0.exe.sha256`.
4. **Try the installer** on a clean-ish setup (at least once per release that changes packaging):
   install, launch, say a forbidden word, quit from the tray, uninstall.
   To check the **update path** itself (once, and whenever `updater.py` or `installer.iss` changes):
   build two consecutive versions (bump `version.py` temporarily, build, bump again, build, then
   revert the bump) and run `python packaging\update_e2e.py <old>.exe <new>.exe <scratch folder>`.
   It installs the old one silently into the scratch folder, serves the new one from a local
   server posing as GitHub, updates through the app's own API and checks the relaunch, the new
   version, that user data survived and that the uninstall is clean.
5. **Tag and publish**:
   ```powershell
   git tag v0.2.0
   git push origin main v0.2.0
   ```
   Then on GitHub: *Releases → Draft a new release*, choose the tag `v0.2.0`, write the notes
   (they are shown in the app's update screen), attach **both files** (`.exe` and `.exe.sha256`),
   and publish. Not a draft, not a pre-release: those are invisible to the updater.
   With the GitHub CLI: `gh release create v0.2.0 packaging\output\Slovonok-Setup-0.2.0.exe packaging\output\Slovonok-Setup-0.2.0.exe.sha256 --notes-file notes.md`

The tag must be `v` + the version in `version.py`, and the installer must be named
`Slovonok-Setup-<version>.exe`: the updater looks for exactly that.

## What the updater does and refuses

- Installs only a version **newer** than the running one, only in the **packaged** app.
- Refuses an installer with no published checksum: GitHub's asset digest is used, or a
  `Slovonok-Setup-<version>.exe.sha256` asset (a line `<64 hex>  <file name>`).
- Verifies the SHA-256 after downloading, then waits for the app to quit and runs the installer
  silently. The installer relaunches the app. Settings, words, punishments and media live in
  `%APPDATA%\Slovonok`, outside the install folder, and are untouched.

## Good to know

- **Installer identity**: `AppId` in `installer.iss` must never change, or an update would install
  next to the old version instead of replacing it.
- **Unsigned**: the exe and the installer are not code-signed, so Windows SmartScreen warns at the
  first install ("More info → Run anyway"). Signing needs a certificate; it is the real protection
  too, because an update is trusted exactly as far as the GitHub account and release are.
- **A bad release**: delete it on GitHub (`releases/latest` goes back to the previous one) and
  publish a higher version with the fix. People who already updated stay on the bad version until
  that new one is out: there is no downgrade.
- **Size**: the installer is several hundred MB (Qt WebEngine, the Vosk model, ffmpeg), and an
  update downloads all of it again.
- **Testing the updater without GitHub**: set `SLOVONOK_UPDATE_URL` to a URL serving a JSON like
  GitHub's `releases/latest` (see `backend/test_updater.py` for the shape).
