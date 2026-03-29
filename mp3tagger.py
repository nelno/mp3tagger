#!/usr/bin/env python3
"""
MP3 Tagger for Album / Author / Song-specific metadata
Supports single MP3 or a directory of MP3s.
Enhanced albumtags auto-detection with case-insensitive album name matching.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from mutagen.easyid3 import EasyID3

# Versioning constants
VERSION_HIGH = 1
VERSION_LOW = 6

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file. Returns empty dict if file doesn't exist or fails."""
    if not file_path or not os.path.isfile(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        print(f"Warning: {file_path} is not a valid JSON object", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Warning: Could not load {file_path}: {e}", file=sys.stderr)
        return {}


def sanitize_filename(name: str) -> str:
    """Convert album name to safe filename part."""
    if not name:
        return ""
    # Remove unsafe characters and replace spaces with underscores
    return re.sub(r'[^a-zA-Z0-9\s\-_]', '', name).strip().replace(' ', '_')


def find_albumtags_file(mp3_path: str, song_tags: Dict[str, Any]) -> Optional[str]:
    """Advanced auto-detection for albumtags.json with case-insensitive album name support."""
    mp3_path = Path(mp3_path)
    mp3_folder = mp3_path.parent
    parent_folder = mp3_folder.parent
    parent_name = mp3_folder.name

    # Get album name from song tags if available
    album_name = song_tags.get("album") or song_tags.get("albumtitle")

    candidates = []

    # Priority 1 & 2: albumtags_<album name>.json (case-insensitive variations)
    if album_name:
        base_name = sanitize_filename(album_name)
        if base_name:
            album_variations = [
                base_name,
                base_name.lower(),
                base_name.title(),
                base_name.upper(),
            ]
            for var in set(album_variations):  # remove duplicates
                candidates.extend([
                    mp3_folder / f"albumtags_{var}.json",      # MP3 folder
                    parent_folder / f"albumtags_{var}.json",   # Parent folder
                ])

    # Priority 3: albumtags_<parent folder name>.json in parent folder
    candidates.append(parent_folder / f"albumtags_{parent_name}.json")

    # Priority 4: albumtags.json in parent folder
    candidates.append(parent_folder / "albumtags.json")

    # Priority 5: albumtags.json in MP3 folder
    candidates.append(mp3_folder / "albumtags.json")

    # Check candidates (this part is case-sensitive on filesystem, but we generated variations)
    for candidate in candidates:
        if candidate.is_file():
            print(f"Found album tags file: {candidate.name}")
            return str(candidate)

    # Extra safety: case-insensitive search in both folders for any albumtags_*.json
    # This catches cases where album name cleaning didn't perfectly match
    for folder in [mp3_folder, parent_folder]:
        try:
            for file in folder.iterdir():
                if file.is_file() and file.name.lower().startswith("albumtags_") and file.suffix.lower() == ".json":
                    # Try to match against our album name (case-insensitive)
                    if album_name and album_name.lower() in file.name.lower():
                        print(f"Found album tags file (case-insensitive match): {file.name}")
                        return str(file)
        except Exception:
            pass

    return None


def find_tags_file(mp3_path: str) -> Optional[str]:
    """Auto-detect song-level tags JSON file (per-song or folder-wide)."""
    mp3_path = Path(mp3_path)
    folder = mp3_path.parent
    stem = mp3_path.stem

    candidates = [
        folder / f"{stem}.json",
        folder / f"mp3tags_{stem}.json",
        folder / "mp3tags.json"
    ]

    for candidate in candidates:
        if candidate.is_file():
            print(f"Found song tags file: {candidate.name}")
            return str(candidate)
    return None


def get_album_art_path(album_tags: Dict, albumart_dir: Optional[str], tags_file_dir: str) -> Optional[str]:
    """Resolve album artwork path."""
    if not album_tags.get("albumart"):
        return None

    art_rel = album_tags["albumart"]
    base = Path(albumart_dir) if albumart_dir else Path(tags_file_dir)
    art_path = base / art_rel

    if art_path.is_file():
        return str(art_path)
    else:
        print(f"Warning: Album art not found at {art_path}", file=sys.stderr)
        return None


def set_tags_on_file(mp3_path: str, 
                     author_tags: Dict, 
                     album_tags: Dict, 
                     song_tags: Dict, 
                     albumart_path: Optional[str],
                     total_tracks: Optional[int]):
    """Apply all tags to a single MP3 file."""
    try:
        try:
            audio = MP3(mp3_path, ID3=EasyID3)
        except error:
            audio = MP3(mp3_path)
            audio.add_tags()

        # Author tags
        if author_tags.get("artist"):
            audio["artist"] = author_tags["artist"]
        if author_tags.get("albumartist"):
            audio["albumartist"] = author_tags.get("albumartist") or author_tags.get("artist")
        if author_tags.get("copyright"):
            audio["copyright"] = author_tags["copyright"]

        # Album tags
        if album_tags.get("album"):
            audio["album"] = album_tags["album"]
        if album_tags.get("albumartist"):
            audio["albumartist"] = album_tags["albumartist"]
        if album_tags.get("date") or album_tags.get("year"):
            audio["date"] = album_tags.get("date") or album_tags.get("year")
        if album_tags.get("genre"):
            audio["genre"] = album_tags["genre"]

        # Total tracks
        if total_tracks:
            track_num = song_tags.get("tracknumber") or "1"
            audio["tracknumber"] = f"{track_num}/{total_tracks}"

        # Song-specific tags (override)
        for key, value in song_tags.items():
            if value:
                if key == "tracknumber" and total_tracks:
                    audio["tracknumber"] = f"{value}/{total_tracks}"
                else:
                    audio[key] = str(value)

        # Album artwork
        if albumart_path and os.path.isfile(albumart_path):
            with open(albumart_path, "rb") as img:
                img_data = img.read()
            
            ext = Path(albumart_path).suffix.lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

            if hasattr(audio, 'tags') and audio.tags:
                audio.tags.delall("APIC")

            audio.tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc="Cover",
                    data=img_data
                )
            )

        audio.save()
        return True

    except Exception as e:
        print(f"✗ Error tagging {Path(mp3_path).name}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="MP3 Batch Tagger")
    parser.add_argument("--input", required=True, help="Single .mp3 file or directory containing .mp3 files")
    parser.add_argument("--albumart", help="Directory containing album artwork")
    parser.add_argument("--albumtags", help="Path to album-level JSON tags file (optional - auto-detected if omitted)")
    parser.add_argument("--tags", help="Path to song-level JSON tags file (optional - auto-detected if omitted)")
    parser.add_argument("--author", required=True, help="Path to author JSON file")
    parser.add_argument("--verbose", action="store_true", help="Show messages for files without tags file")

    args = parser.parse_args()

    author_tags = load_json_file(args.author)
    albumart_dir = args.albumart

    # Find MP3 files
    input_path = Path(args.input)
    if input_path.is_file() and str(input_path).lower().endswith(".mp3"):
        mp3_files = [str(input_path)]
    elif input_path.is_dir():
        mp3_files = [str(f) for f in input_path.rglob("*.mp3") if f.is_file()]
        if not mp3_files:
            print("No .mp3 files found.", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: --input must be a valid .mp3 file or directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(mp3_files)} MP3 file(s) to tag.\n")

    success_count = 0
    skipped_count = 0

    for mp3_file in mp3_files:
        mp3_name = Path(mp3_file).name
        song_tags = {}
        album_tags = {}
        album_tags_dir = str(Path(mp3_file).parent)
        tags_used = False

        # === 1. Load song-level tags ===
        if args.tags:
            song_tags = load_json_file(args.tags)
            print(f"Using provided song tags file: {Path(args.tags).name}")
            tags_used = True
        else:
            tags_path = find_tags_file(mp3_file)
            if tags_path:
                song_tags = load_json_file(tags_path)
                tags_used = True
            elif args.verbose:
                print(f"No song tags file found for {mp3_name}")

        # === 2. Load album-level tags (with case-insensitive support) ===
        if args.albumtags:
            # User explicitly provided --albumtags
            album_tags = load_json_file(args.albumtags)
            album_tags_dir = str(Path(args.albumtags).parent)
            print(f"Using provided album tags file: {Path(args.albumtags).name}")
        else:
            # Auto-detect using enhanced priority + case-insensitive album name
            albumtags_path = find_albumtags_file(mp3_file, song_tags)
            if albumtags_path:
                album_tags = load_json_file(albumtags_path)
                album_tags_dir = str(Path(albumtags_path).parent)
            elif args.verbose:
                print(f"No albumtags file found for {mp3_name}")

        # Auto-detect track number from filename if missing
        if "tracknumber" not in song_tags:
            filename = Path(mp3_file).stem
            match = re.search(r'^0*(\d+)', filename)
            if match:
                song_tags["tracknumber"] = match.group(1)

        # Prepare album art and total tracks
        album_art_path = get_album_art_path(album_tags, albumart_dir, album_tags_dir)
        total_tracks = (album_tags.get("totaltracks") or 
                       album_tags.get("tracktotal") or 
                       album_tags.get("number_of_tracks"))

        # === Tag the file ===
        if tags_used:
            if set_tags_on_file(
                mp3_path=mp3_file,
                author_tags=author_tags,
                album_tags=album_tags,
                song_tags=song_tags,
                albumart_path=album_art_path,
                total_tracks=total_tracks
            ):
                print(f"✓ Tagged: {mp3_name}")
                success_count += 1
        else:
            print(f"– Skipped: {mp3_name} (no song tags file found)")
            skipped_count += 1

    print(f"\nTagging complete! Successfully tagged {success_count} file(s).")
    if skipped_count:
        print(f"Skipped {skipped_count} file(s) due to missing song tags files.")


if __name__ == "__main__":
    print(f"mp3tagger v{VERSION_HIGH}.{VERSION_LOW}")
    main()