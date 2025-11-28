.PHONY: help install setup clean run dry-run lint format check

# Default target
help:
	@echo "Sony A7IV Media Import Tool - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make setup      - Create virtual environment and install dependencies"
	@echo "  make install    - Install/update dependencies only (venv must exist)"
	@echo "  make clean      - Remove virtual environment"
	@echo "  make run        - Run the import tool (auto-detect SD card)"
	@echo "  make dry-run    - Run in dry-run mode to preview what would be copied"
	@echo "  make lint       - Run all linters (flake8, pylint)"
	@echo "  make format     - Format code with black and isort"
	@echo "  make check      - Run linters and check formatting"
	@echo ""
	@echo "Usage examples:"
	@echo "  make setup"
	@echo "  make run DEST=~/Pictures/Camera"
	@echo "  make dry-run DEST=~/Pictures/Camera"
	@echo "  make run DEST=~/Pictures/Camera SOURCE=/Volumes/SD_CARD/DCIM"

# Create virtual environment and install dependencies
setup:
	@echo "Creating virtual environment..."
	python -m venv venv
	@echo "Installing dependencies..."
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	@echo ""
	@echo "Setup complete! Virtual environment created in ./venv"
	@echo ""
	@echo "To use the tool:"
	@echo "  make run DEST=~/Pictures/Camera"
	@echo "  make dry-run DEST=~/Pictures/Camera"

# Install/update dependencies (assumes venv exists)
install:
	@if [ ! -d "venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Updating dependencies..."
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	@echo "Dependencies updated!"

# Install development dependencies
install-dev:
	@if [ ! -d "venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Installing development dependencies..."
	./venv/bin/pip install -r requirements-dev.txt
	@echo "Development dependencies installed!"

# Remove virtual environment
clean:
	@echo "Removing virtual environment..."
	rm -rf venv
	@echo "Virtual environment removed."

# Run the import tool
# Usage: make run DEST=~/Pictures/Camera
# Optional: make run DEST=~/Pictures/Camera SOURCE=/Volumes/SD/DCIM VIDEO_SOURCE=/Volumes/SD/PRIVATE/M4ROOT/CLIP
run:
	@if [ ! -d "venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ -z "$(DEST)" ]; then \
		echo "Error: DEST not specified."; \
		echo "Usage: make run DEST=~/Pictures/Camera"; \
		exit 1; \
	fi
	@if [ -n "$(SOURCE)" ] && [ -n "$(VIDEO_SOURCE)" ]; then \
		./venv/bin/python media_importer.py --source $(SOURCE) --video-source $(VIDEO_SOURCE) $(DEST); \
	elif [ -n "$(SOURCE)" ]; then \
		./venv/bin/python media_importer.py --source $(SOURCE) $(DEST); \
	else \
		./venv/bin/python media_importer.py $(DEST); \
	fi

# Run in dry-run mode
# Usage: make dry-run DEST=~/Pictures/Camera
dry-run:
	@if [ ! -d "venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ -z "$(DEST)" ]; then \
		echo "Error: DEST not specified."; \
		echo "Usage: make dry-run DEST=~/Pictures/Camera"; \
		exit 1; \
	fi
	@if [ -n "$(SOURCE)" ] && [ -n "$(VIDEO_SOURCE)" ]; then \
		./venv/bin/python media_importer.py --dry-run --source $(SOURCE) --video-source $(VIDEO_SOURCE) $(DEST); \
	elif [ -n "$(SOURCE)" ]; then \
		./venv/bin/python media_importer.py --dry-run --source $(SOURCE) $(DEST); \
	else \
		./venv/bin/python media_importer.py --dry-run $(DEST); \
	fi

# Lint code with flake8 and pylint
lint:
	@if [ ! -d "venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Running flake8..."
	./venv/bin/python -m flake8 media_importer.py || true
	@echo ""
	@echo "Running pylint..."
	./venv/bin/python -m pylint media_importer.py || true

# Format code with black and isort
format:
	@if [ ! -d "venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Formatting with black..."
	./venv/bin/python -m black media_importer.py
	@echo "Sorting imports with isort..."
	./venv/bin/python -m isort media_importer.py
	@echo "Code formatted!"

# Check code without modifying (for CI)
check:
	@if [ ! -d "venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Checking formatting with black..."
	./venv/bin/python -m black --check media_importer.py
	@echo "Checking import sorting with isort..."
	./venv/bin/python -m isort --check-only media_importer.py
	@echo "Running flake8..."
	./venv/bin/python -m flake8 media_importer.py
	@echo "All checks passed!"

