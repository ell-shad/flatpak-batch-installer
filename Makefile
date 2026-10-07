.PHONY: run test lint clean

run:
	python3 flathub-gui.py

test:
	python3 -m unittest discover -s tests -v

lint:
	python3 -m compileall -q flathub_gui flathub-gui.py flatpak-gui.py tests

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf build dist *.egg-info
