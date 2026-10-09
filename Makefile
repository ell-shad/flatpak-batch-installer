.PHONY: run test lint clean assets appimage dist install-user uninstall-user

run:
	python3 flathub-gui.py

test:
	python3 -m unittest discover -s tests -v

lint:
	python3 -m compileall -q flathub_gui flathub-gui.py flatpak-gui.py tests

assets:
	python3 assets/make_assets.py

appimage:
	bash packaging/appimage/build-appimage.sh

dist:
	python3 -m build

install-user:
	bash packaging/desktop/install-user.sh

uninstall-user:
	rm -f ~/.local/share/applications/io.github.flathub-catalog-installer.desktop
	rm -f ~/.local/share/icons/hicolor/256x256/apps/io.github.flathub-catalog-installer.png
	rm -f ~/.local/bin/flathub-catalog-installer
	update-desktop-database ~/.local/share/applications 2>/dev/null || true

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf build dist *.egg-info appimage-build *.AppImage
