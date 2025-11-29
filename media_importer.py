#!/usr/bin/env python3
"""
Media Import Tool for Sony A7IV
Automatically organizes photos and videos by date (YEAR/MONTH/DAY/pictures|videos) from SD card.
Works on macOS and Linux.
"""

import sys

if sys.version_info < (3, 14):
    print("Error: Python 3.14 or higher is required.")
    print(
        f"You are using Python "
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    sys.exit(1)

# pylint: disable=wrong-import-position
import argparse
import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# pylint: enable=wrong-import-position

try:
    import exifread
except ImportError:
    print("Error: exifread not installed.")
    print("Run: make setup")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("Error: tqdm not installed.")
    print("Run: make install-dev")
    sys.exit(1)

try:
    from colorama import Fore, Style
    from colorama import init as colorama_init

    colorama_init(autoreset=True)  # Auto-reset colors after each print
except ImportError:
    # Fallback if colorama not installed - no colors
    class Fore:  # pylint: disable=too-few-public-methods
        RED = GREEN = YELLOW = CYAN = BLUE = MAGENTA = ""

    class Style:  # pylint: disable=too-few-public-methods
        RESET_ALL = BRIGHT = ""


class MediaImporter:
    """Handles importing and organizing photos and videos from SD card."""

    def __init__(
        self,
        source: Path,
        destination: Path,
        dry_run: bool = False,
        video_source: Optional[Path] = None,
    ):
        self.source = source
        self.video_source = video_source  # Optional separate video source
        self.destination = destination
        self.dry_run = dry_run
        self.stats = {"copied": 0, "skipped": 0, "errors": 0, "total_size": 0}

        # Setup logging
        log_level = logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

        # Add custom color formatter for logging
        self._setup_colored_logging()

    def _setup_colored_logging(self):
        """Setup colored logging output."""

        # Create custom formatter with colors
        class ColoredFormatter(logging.Formatter):
            COLORS = {
                "DEBUG": Fore.CYAN,
                "INFO": Fore.BLUE,
                "WARNING": Fore.YELLOW,
                "ERROR": Fore.RED,
                "CRITICAL": Fore.RED + Style.BRIGHT,
            }

            def format(self, record):
                levelname = record.levelname
                if levelname in self.COLORS:
                    record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
                return super().format(record)

        # Apply colored formatter to all handlers
        colored_formatter = ColoredFormatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        for handler in logging.root.handlers:
            handler.setFormatter(colored_formatter)

    def find_sd_card_paths(self) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Automatically find DCIM and video folders on mounted SD card.
        Works on macOS and Linux.

        Returns (dcim_path, video_path) tuple.
        """
        self.logger.info("Searching for SD card...")

        search_paths = []

        if sys.platform == "darwin":  # macOS
            volumes = Path("/Volumes")
            if volumes.exists():
                search_paths.extend(volumes.iterdir())

        elif sys.platform.startswith("linux"):  # Linux
            # Try common mount points
            username = os.getenv("USER")
            media_paths = [
                Path(f"/media/{username}"),
                Path("/media"),
                Path("/mnt"),
                Path(f"/run/media/{username}"),
            ]
            for media_path in media_paths:
                if media_path.exists():
                    try:
                        search_paths.extend(media_path.iterdir())
                    except PermissionError:
                        continue

        # Search for DCIM and video folders on same card
        dcim_path = None
        video_path = None

        for path in search_paths:
            if path.is_dir():
                # Check for DCIM folder (photos)
                potential_dcim = path / "DCIM"
                if potential_dcim.exists() and not dcim_path:
                    dcim_path = potential_dcim
                    self.logger.info(
                        "%sFound DCIM folder: %s%s", Fore.GREEN, dcim_path, Style.RESET_ALL
                    )

                # Check for PRIVATE/M4ROOT/CLIP (videos - Sony AVCHD/XAVC structure)
                potential_video = path / "PRIVATE" / "M4ROOT" / "CLIP"
                if potential_video.exists() and not video_path:
                    video_path = potential_video
                    self.logger.info(
                        "%sFound video folder: %s%s", Fore.GREEN, video_path, Style.RESET_ALL
                    )

                # If we found both on same card, return them
                if dcim_path and video_path:
                    break

        return dcim_path, video_path

    def get_media_date(self, file_path: Path) -> Optional[datetime]:
        """
        Extract the date when media (photo/video) was created.
        For photos: reads EXIF DateTimeOriginal.
        For videos: uses file modification date.
        Falls back to file modification date if EXIF not available.
        """
        # For video files, skip EXIF reading and use file date directly
        # Videos don't typically have EXIF DateTimeOriginal like photos
        if self.is_video_file(file_path):
            try:
                timestamp = file_path.stat().st_mtime
                return datetime.fromtimestamp(timestamp)
            except OSError as e:
                self.logger.error("Could not get date for %s: %s", file_path.name, e)
                return None

        # For photos, try to read EXIF data
        try:
            with open(file_path, "rb") as f:
                tags = exifread.process_file(f, stop_tag="DateTimeOriginal", details=False)

                # Try different EXIF date tags in order of preference
                for tag_name in [
                    "EXIF DateTimeOriginal",
                    "EXIF DateTimeDigitized",
                    "Image DateTime",
                ]:
                    if tag_name in tags:
                        date_str = str(tags[tag_name])
                        # EXIF format: "2025:11:28 14:30:45"
                        try:
                            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            continue
        except OSError as e:
            self.logger.debug("Could not read EXIF from %s: %s", file_path.name, e)

        # Fallback to file modification time
        try:
            timestamp = file_path.stat().st_mtime
            return datetime.fromtimestamp(timestamp)
        except OSError as e:
            self.logger.error("Could not get date for %s: %s", file_path.name, e)
            return None

    def get_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Calculate MD5 hash of file for duplicate detection."""
        md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    md5.update(chunk)
            return md5.hexdigest()
        except OSError as e:
            self.logger.error("Could not hash %s: %s", file_path.name, e)
            return ""

    def is_photo_file(self, file_path: Path) -> bool:
        """Check if file is a photo we want to import (not video)."""
        photo_extensions = {
            # Sony A7IV formats
            ".arw",
            ".ARW",  # RAW
            ".jpg",
            ".jpeg",
            ".JPG",
            ".JPEG",  # JPEG
            # Also support other common formats
            ".dng",
            ".DNG",
            ".tif",
            ".tiff",
            ".TIF",
            ".TIFF",
        }
        return file_path.suffix in photo_extensions

    def is_video_file(self, file_path: Path) -> bool:
        """Check if file is a video we want to import."""
        video_extensions = {
            ".mp4",
            ".MP4",
            ".mov",
            ".MOV",
            ".mts",
            ".MTS",  # AVCHD format
            ".m2ts",
            ".M2TS",  # AVCHD HD format
        }
        return file_path.suffix in video_extensions

    def find_all_media(self) -> List[Tuple[Path, str]]:
        """
        Recursively find all media files (photos and videos) in source directories.
        Returns list of (file_path, file_type) tuples where file_type is 'photo' or 'video'.
        """
        files = []

        # Extensions to skip (metadata files from AVCHD structure)
        skip_extensions = {".xml", ".XML", ".bup", ".BUP", ".ifo", ".IFO"}

        try:
            self.logger.info("Scanning for photos in: %s", self.source)
            for item in self.source.rglob("*"):
                if item.is_file() and item.suffix not in skip_extensions:
                    if self.is_photo_file(item):
                        files.append((item, "photo"))
        except OSError as e:
            self.logger.error("Error scanning photo directory: %s", e)

        if self.video_source and self.video_source.exists():
            try:
                self.logger.info("Scanning for videos in: %s", self.video_source)
                for item in self.video_source.rglob("*"):
                    if item.is_file() and item.suffix not in skip_extensions:
                        if self.is_video_file(item):
                            files.append((item, "video"))
            except OSError as e:
                self.logger.error("Error scanning video directory: %s", e)

        return sorted(files, key=lambda x: x[0])

    # pylint: disable=too-many-locals
    def organize_media(self, media_path: Path, file_type: str = "photo") -> bool:
        """
        Copy media file to destination organized by date.
        Returns True if copied, False if skipped.

        Args:
            media_path: Path to the file to copy
            file_type: Either 'photo' or 'video'
        """
        media_date = self.get_media_date(media_path)
        if not media_date:
            self.logger.warning("Skipping %s - could not determine date", media_path.name)
            self.stats["skipped"] += 1
            return False

        # Create destination path: YEAR/MONTH/DAY/pictures or YEAR/MONTH/DAY/videos
        year = media_date.strftime("%Y")
        month = media_date.strftime("%m")
        day = media_date.strftime("%d")
        subfolder = "videos" if file_type == "video" else "pictures"

        dest_dir = self.destination / year / month / day / subfolder
        dest_file = dest_dir / media_path.name

        # Check if file already exists
        if dest_file.exists():
            # Compare file sizes first (quick check)
            if dest_file.stat().st_size == media_path.stat().st_size:
                self.logger.debug("Skipping %s - already exists with same size", media_path.name)
                self.stats["skipped"] += 1
                return False

            # If sizes differ, check hash
            source_hash = self.get_file_hash(media_path)
            dest_hash = self.get_file_hash(dest_file)
            if source_hash == dest_hash:
                self.logger.debug("Skipping %s - duplicate detected", media_path.name)
                self.stats["skipped"] += 1
                return False

            # File exists but is different - add suffix
            counter = 1
            stem = media_path.stem
            suffix = media_path.suffix
            while dest_file.exists():
                dest_file = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        if self.dry_run:
            rel_path = dest_file.relative_to(self.destination)
            self.logger.info("[DRY RUN] Would copy: %s -> %s", media_path.name, rel_path)
        else:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)

                shutil.copy2(media_path, dest_file)

                file_size = media_path.stat().st_size
                self.stats["total_size"] += file_size

            except OSError as e:
                tqdm.write(f"{Fore.RED}ERROR: {media_path.name} - {e}{Style.RESET_ALL}")
                self.logger.error("Error copying %s: %s", media_path.name, e)
                self.stats["errors"] += 1
                return False

        self.stats["copied"] += 1
        return True

    def import_media(self):
        """Main import process for photos and videos."""
        self.logger.info("Photo source: %s", self.source)
        if self.video_source:
            self.logger.info("Video source: %s", self.video_source)
        self.logger.info("Destination: %s", self.destination)

        if self.dry_run:
            self.logger.info("DRY RUN MODE - No files will be copied")

        # Validate source
        if not self.source.exists():
            self.logger.error("Source directory does not exist: %s", self.source)
            return False

        # Find all media files (photos and videos)
        self.logger.info("Scanning for photos and videos...")
        files = self.find_all_media()

        if not files:
            self.logger.warning("No photos or videos found!")
            return False

        photo_count = sum(1 for _, ftype in files if ftype == "photo")
        video_count = sum(1 for _, ftype in files if ftype == "video")

        self.logger.info(
            "Found %d photo(s) and %d video(s) to process",
            photo_count,
            video_count,
        )

        # Process each media file with progress bar
        with tqdm(
            total=len(files),
            desc="Importing media",
            unit="file",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=self.dry_run,  # Disable progress bar in dry-run to avoid clutter
        ) as pbar:
            for file_path, file_type in files:
                type_label = "📷" if file_type == "photo" else "🎬"
                file_desc = f"{type_label} {file_path.name}"
                pbar.set_description(f"Processing: {file_desc[:50]}")  # Truncate long names

                self.organize_media(file_path, file_type)
                pbar.update(1)

        # Print summary
        self.print_summary()
        return True

    def print_summary(self):
        """Print import statistics."""
        self.logger.info("\n%s", "=" * 60)
        self.logger.info("%sIMPORT SUMMARY%s", Style.BRIGHT, Style.RESET_ALL)
        self.logger.info("=" * 60)

        if self.stats["copied"] > 0:
            self.logger.info(
                "%sFiles copied: %d%s", Fore.GREEN, self.stats["copied"], Style.RESET_ALL
            )
        else:
            self.logger.info("Files copied: %d", self.stats["copied"])

        if self.stats["skipped"] > 0:
            self.logger.info(
                "%sFiles skipped: %d%s", Fore.YELLOW, self.stats["skipped"], Style.RESET_ALL
            )
        else:
            self.logger.info("Files skipped: %d", self.stats["skipped"])

        if self.stats["errors"] > 0:
            self.logger.info("%sErrors: %d%s", Fore.RED, self.stats["errors"], Style.RESET_ALL)
        else:
            self.logger.info("%sErrors: %d%s", Fore.GREEN, self.stats["errors"], Style.RESET_ALL)

        if not self.dry_run and self.stats["total_size"] > 0:
            size_mb = self.stats["total_size"] / (1024 * 1024)
            size_gb = size_mb / 1024
            if size_gb >= 1:
                self.logger.info(
                    "%sTotal size copied: %.2f GB%s", Fore.CYAN, size_gb, Style.RESET_ALL
                )
            else:
                self.logger.info(
                    "%sTotal size copied: %.2f MB%s", Fore.CYAN, size_mb, Style.RESET_ALL
                )

        self.logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Import and organize photos and videos from Sony A7IV SD card by date",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect SD card and import to ~/Pictures/Camera
  %(prog)s ~/Pictures/Camera

  # Specify sources manually
  %(prog)s --source /Volumes/SD_CARD/DCIM --video-source /Volumes/SD_CARD/PRIVATE/M4ROOT/CLIP ~/Pictures/Camera

  # Dry run to see what would be copied
  %(prog)s --dry-run ~/Pictures/Camera
        """,
    )

    parser.add_argument(
        "destination", type=Path, help="Destination directory for organized photos and videos"
    )

    parser.add_argument(
        "--source",
        "-s",
        type=Path,
        help="Source directory for photos (DCIM folder). If not provided, will auto-detect SD card",
    )

    parser.add_argument(
        "--video-source",
        type=Path,
        help="Source directory for videos (PRIVATE/M4ROOT/CLIP). If not provided, will auto-detect",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be copied without actually copying",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.source:
        source = args.source
        video_source = args.video_source
    else:
        importer = MediaImporter(Path("."), args.destination, args.dry_run)
        source, video_source = importer.find_sd_card_paths()
        if not source:
            print(f"{Fore.RED}Error: Could not find SD card DCIM folder.{Style.RESET_ALL}")
            print("Please specify source manually with --source")
            print("\nCommon locations:")
            print(f"  {Fore.CYAN}Photos: /Volumes/YOUR_SD_CARD/DCIM{Style.RESET_ALL}")
            print(
                f"  {Fore.CYAN}Videos: /Volumes/YOUR_SD_CARD/PRIVATE/M4ROOT/CLIP{Style.RESET_ALL}"
            )
            print(f"  {Fore.CYAN}Linux:  /media/$USER/YOUR_SD_CARD/...{Style.RESET_ALL}")
            sys.exit(1)

    importer = MediaImporter(source, args.destination, args.dry_run, video_source)
    success = importer.import_media()

    if success:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}✓ Import completed successfully!{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}{Style.BRIGHT}✗ Import failed!{Style.RESET_ALL}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
