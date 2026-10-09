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
| **Native .deb** | Debian/Ubuntu/Mint/Pop!_OS… | Yes — proper Depends | Low (`make deb`, no root) | **Recommended primary on Debian family; officially supported** |
| **AppImage** | All distros, one file | Yes — and it is (no sandbox) | Low (script provided) | **Universal fallback** |
| **pipx / pip (`pip install .`)** | Any distro with Python | Yes — native by definition | Zero (already works) | **Recommended for CLI/tech users** |
| **Native .rpm** | Fedora/openSUSE/Arch… | Yes — proper deps | Medium (spec file, per distro) | Community follow-up; metadata provided |
| **Flatpak (self-hosted)** | Flathub reach | **No** — sandboxed; needs `flatpak-spawn --host` bridging or a D-Bus Transaction rewrite | Medium code change + Flathub review | Experimental (manifest provided, works except host calls) |
| **Snap** | Ubuntu-centric | Strict mode blocks host flatpak; classic needs store approval | Medium + review friction | Not recommended |
| **From source (`flatpak-gui.py`)** | Everywhere | Yes | Zero | Fine for developers |

## Recommended setup

1. **Primary on Debian family: .deb.** `make deb` (or the release
   workflow) produces `flatpak-batch-installer_<ver>-1_all.deb`:
   pure-Python app plus a man page, desktop file, AppStream metainfo and
   icons, with Tk/Pillow/Flatpak pulled from the distro. Install with
   `sudo apt install ./flatpak-batch-installer_*_all.deb`. These systems
   are the officially supported target (Debian 12+, Ubuntu 22.04+ and
   derivatives) and every release is CI-tested there.
2. **Universal fallback: AppImage.** `bash packaging/appimage/build-appimage.sh` on the
   oldest supported base (Ubuntu 22.04) produces one
   `Flatpak-Batch-Installer-<version>-x86_64.AppImage` that runs on Debian-,
   Arch- and RPM-family desktops alike. It bundles Python + Tk; the host
   supplies only the display stack and `flatpak`. The file must be
   executable (`chmod +x`) and needs FUSE (`libfuse2`) — without FUSE,
   run it with `--appimage-extract` instead. Attach it to every GitHub
   Release (the `release` workflow does this automatically on `v*` tags).
2. **Secondary: PyPI/pipx.** Publish the existing `pyproject.toml` package
   (`python -m build`, `twine upload`) so technical users can
   `pipx install flatpak-batch-installer`. Zero maintenance beyond releases.
3. **Native RPM: community follow-up.** The same metadata (desktop file,
   metainfo, icons) serves an RPM spec; the `.deb` script documents the
   file layout to mirror. Leave to contributors on RPM-family distros.
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

## App ID placeholder

The reverse-DNS ID `io.github.flatpak-batch-installer` is functional
everywhere (desktop file, icons, metainfo, AppImage) but claims no real
publisher identity. Before any Flathub submission, replace it with the
real ID (e.g. `io.github.<user>.FlatpakBatchInstaller`) in:

- `assets/make_assets.py` (`APP_ID`, regenerates icon filenames)
- `packaging/desktop/*.desktop` + `install-user.sh` + `Makefile`
- `packaging/metainfo/*.metainfo.xml`
- `packaging/flatpak/*.yml`
- Regenerate assets (`make assets`) after the rename.

## Building each artifact

```bash
make assets                    # regenerate icon.png, hicolor set, banner
bash packaging/appimage/build-appimage.sh   # AppImage (needs squashfs-tools)
make deb                       # .deb for Debian family (needs dpkg-deb)
python3 -m build               # sdist + wheel (needs `build` package)
flatpak-builder --force-clean build-dir packaging/flatpak/*.yml   # manifest check
make install-user              # desktop file + icon + shim, no root
```
