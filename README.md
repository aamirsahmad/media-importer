# Media Import Tool for Sony A7IV

Automatically imports and organizes photos and videos from Sony A7IV SD card by date.

## Quick Start

```bash
# Setup (one time)
make setup

# Use
make dry-run DEST=~/Pictures/Camera
make run DEST=~/Pictures/Camera
```

## Features

- Auto-detects SD card (photos from DCIM, videos from PRIVATE/M4ROOT/CLIP)
- Organizes by date: `YEAR/MONTH/DAY/pictures/` and `YEAR/MONTH/DAY/videos/`
- Duplicate detection via MD5 hash
- Progress bar
- Cross-platform (macOS and Linux)

## Manual Source

If auto-detection fails:

```bash
make run DEST=~/Pictures/Camera SOURCE=/Volumes/SD/DCIM VIDEO_SOURCE=/Volumes/SD/PRIVATE/M4ROOT/CLIP
```

## Make Commands

```bash
make setup      # Initial setup
make install    # Update dependencies
make run        # Import media (requires DEST=path)
make dry-run    # Preview without copying
make clean      # Remove venv
make help       # Show help

# Development
make install-dev  # Install development dependencies (linting tools)
make lint         # Run linters (flake8, pylint)
make format       # Format code (black, isort)
make check        # Check formatting and run linters
```

## Direct Python Usage

```bash
source venv/bin/activate
python media_importer.py ~/Pictures/Camera
python media_importer.py --dry-run ~/Pictures/Camera
python media_importer.py --source /path/to/DCIM --video-source /path/to/CLIP ~/Pictures/Camera
```

## File Formats

- Photos: ARW, JPG, JPEG, DNG, TIF
- Videos: MP4, MOV, MTS, M2TS

## Why Videos in Different Location?

Sony uses AVCHD/XAVC standard: photos go in DCIM, videos in PRIVATE/M4ROOT/CLIP.

## License

MIT License - free to use, modify, and distribute.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Install dev dependencies: `make install-dev`
5. Format your code: `make format`
6. Run linters: `make lint`
7. Test your changes on both macOS and Linux if possible
8. Commit your changes (`git commit -m 'Add amazing feature'`)
9. Push to the branch (`git push origin feature/amazing-feature`)
10. Open a Pull Request

### Reporting Issues

Please use GitHub Issues to report bugs or request features. Include:
- Operating system (macOS/Linux)
- Python version
- Steps to reproduce
- Expected vs actual behavior

### Code Style

- Follow PEP 8 guidelines
- Add docstrings to new functions
- Keep code readable and maintainable


