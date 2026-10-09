# Distribution guide

Goal: one app that installs and runs on **any** mainstream Linux desktop
(Debian/Ubuntu/Mint, Fedora, Arch, openSUSE…) without per-distro rebuilds.

## What the app needs at runtime

- Python 3.10+ and Tk (for the GUI; the CLI works without Tk)
- The **host** `flatpak` binary on `PATH` (the app shells out to it)
- Network access to Flathub (only when loading the catalog / installing)

That middle point decides everything: anything that sandboxes the app away
from the host `flatpak` needs extra bridging work.

## Option comparison

| Method | Distro coverage | Needs host flatpak visible? | Effort | Verdict |
|---|---|---|---|---|
| **AppImage** | All distros, one file | Yes — and it is (no sandbox) | Low (script provided) | **Recommended primary download** |
| **pipx / pip (`pip install .`)** | Any distro with Python | Yes — native by definition | Zero (already works) | **Recommended for CLI/tech users** |
| **Native .deb / .rpm** | Per-distro builds | Yes — proper deps | High (per release, per distro) | Best UX, do via metadata provided; leave builds to distro packagers / contributors |
| **Flatpak (self-hosted)** | Flathub reach | **No** — sandboxed; needs `flatpak-spawn --host` bridging or a D-Bus Transaction rewrite | Medium code change + Flathub review | Experimental (manifest provided, works except host calls) |
| **Snap** | Ubuntu-centric | Strict mode blocks host flatpak; classic needs store approval | Medium + review friction | Not recommended |
| **From source (`flatpak-gui.py`)** | Everywhere | Yes | Zero | Fine for developers |

## Recommended setup

1. **Primary: AppImage.** `bash packaging/appimage/build-appimage.sh` on the
   oldest supported base (Ubuntu 22.04) produces one
   `Flatpak-Batch-Installer-<version>-x86_64.AppImage` that runs on Debian-,
   Arch- and RPM-family desktops alike. It bundles Python + Tk; the host
   supplies only the display stack and `flatpak`. Attach it to every GitHub
   Release (the `release` workflow does this automatically on `v*` tags).
2. **Secondary: PyPI/pipx.** Publish the existing `pyproject.toml` package
   (`python -m build`, `twine upload`) so technical users can
   `pipx install flatpak-batch-installer`. Zero maintenance beyond releases.
3. **Native packages: enable, don't own.** This repo ships everything a
   packager needs — `.desktop` file, AppStream metainfo, hicolor icons,
   `setuptools` config — so a Debian/Fedora/Arch contributor can package it
   without upstream changes. Maintaining your own PPA/COPR/AUR is a
   follow-up once the user base asks for it.
4. **Flatpak: park it.** The manifest in `packaging/flatpak/` builds, but
   host `flatpak` calls need bridging first (see the manifest header for the
   two routes: `flatpak-spawn --host` wrapper vs D-Bus Transaction API).
   Flathub's own submission rules confirm this reading (verified
   2026-10-09 in the official requirements):
   "host-dependent applications" and "system utilities … generally used on
   host" are not accepted, and a future submission would additionally need
   vendored PyPI sources (no network during build — relevant now that the
   app depends on ttkbootstrap), complete English localisation, and a
   trademark-clean name/icon. Our rename to *Flatpak Batch Installer*
   already satisfies the last point: Flathub forbids implying official
   affiliation via a vendor name ("Flathub … Installer" would have
   violated it), while naming the open technology is the established
   pattern (cf. Flatseal). Submitting before the bridging lands would
   ship a broken app — don't.

## Before publishing (rename checklist)

The placeholder reverse-DNS ID `io.github.flatpak-batch-installer` (and
`example` URLs) appear in these files — replace with the real publisher ID:

- `assets/make_assets.py` (`APP_ID`, regenerates icon filenames)
- `packaging/desktop/*.desktop` + `install-user.sh` + `Makefile`
- `packaging/metainfo/*.metainfo.xml`
- `packaging/flatpak/*.yml`
- `flatpak_batch_installer/helptext.py` (`HOMEPAGE`, `ISSUES`), `pyproject.toml` URLs
- Regenerate assets (`make assets`) after the rename.

## Building each artifact

```bash
make assets                    # regenerate icon.png, hicolor set, banner
bash packaging/appimage/build-appimage.sh   # AppImage (needs squashfs-tools)
python3 -m build               # sdist + wheel (needs `build` package)
flatpak-builder --force-clean build-dir packaging/flatpak/*.yml   # manifest check
make install-user              # desktop file + icon + shim, no root
```
