.PHONY: run test lint clean assets appimage deb dist install-user uninstall-user

run:
	python3 flatpak-gui.py

test:
	python3 -m unittest discover -s tests -v

lint:
	python3 -m compileall -q flatpak_batch_installer flatpak-gui.py flatpak-gui.py tests

assets:
	python3 assets/make_assets.py

appimage:
	bash packaging/appimage/build-appimage.sh

deb:
	bash packaging/debian/build-deb.sh

dist:
	python3 -m build

install-user:
	bash packaging/desktop/install-user.sh

uninstall-user:
	rm -f ~/.local/share/applications/io.github.flatpak-batch-installer.desktop
	rm -f ~/.local/share/icons/hicolor/256x256/apps/io.github.flatpak-batch-installer.png
	rm -f ~/.local/bin/flatpak-batch-installer
	update-desktop-database ~/.local/share/applications 2>/dev/null || true

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf build dist *.egg-info appimage-build deb-build *.AppImage *.deb
