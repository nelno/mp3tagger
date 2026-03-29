#!/usr/bin/env python3
"""
MP3 Tagger for Album
Jonathan E. Wright
Supports single MP3 or a directory of MP3s.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error as ID3Error
from mutagen.easyid3 import EasyID3

# Versioning constants
VERSION_HIGH = 1
VERSION_LOW = 10

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
    """Convert name to safe filename part (for album name)."""
    if not name:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s\-_]', '', name).strip().replace(' ', '_')


def find_files_case_insensitive(directory: Path, patterns: List[str]) -> Optional[Path]:
    """Find a file in directory matching any pattern case-insensitively."""
    if not directory.is_dir():
        return None
    try:
        for file in directory.iterdir():
            if not file.is_file():
                continue
            fname_lower = file.name.lower()
            for pattern in patterns:
                pattern_lower = pattern.lower()
                if "*" in pattern:
                    base = pattern_lower.replace("*", "")
                    if base in fname_lower and fname_lower.endswith(".json"):
                        return file
                elif fname_lower == pattern_lower or fname_lower.endswith(pattern_lower):
                    return file
    except Exception:
        pass
    return None


def get_album_art_path(album_tags: Dict, albumart_dir: Optional[str], tags_file_dir: str) -> Optional[str]:
    """Resolve album artwork path. Supports extension-less names (tries jpg/jpeg/png)."""
    if not album_tags.get("albumart"):
        return None

    art_rel = album_tags["albumart"].strip()
    base = Path(albumart_dir) if albumart_dir else Path(tags_file_dir)

    # If it already has an extension, use it directly
    if Path(art_rel).suffix:
        art_path = base / art_rel
        if art_path.is_file():
            return str(art_path)
        else:
            print(f"Warning: Album art not found at {art_path}", file=sys.stderr)
            return None

    # No extension → try .jpg, .jpeg, .png (in that order)
    for ext in [".jpg", ".jpeg", ".png"]:
        art_path = base / f"{art_rel}{ext}"
        if art_path.is_file():
            print(f"Found album art: {art_path.name}")
            return str(art_path)

    print(f"Warning: Album art not found for '{art_rel}' (tried .jpg, .jpeg, .png)", file=sys.stderr)
    return None


def find_albumtags_file(mp3_path: str, song_tags: Dict[str, Any]) -> Optional[str]:
    """Advanced case-insensitive auto-detection for albumtags files."""
    mp3_path = Path(mp3_path)
    mp3_folder = mp3_path.parent
    parent_folder = mp3_folder.parent
    parent_name = mp3_folder.name

    album_name = song_tags.get("album") or song_tags.get("albumtitle")
    candidates: List[Path] = []

    if album_name:
        base_name = sanitize_filename(album_name)
        if base_name:
            variations = [base_name, base_name.lower(), base_name.title(), base_name.upper()]
            for var in set(variations):
                candidates.extend([
                    mp3_folder / f"albumtags_{var}.json",
                    parent_folder / f"albumtags_{var}.json",
                ])

    candidates.append(parent_folder / f"albumtags_{parent_name}.json")
    candidates.append(parent_folder / "albumtags.json")
    candidates.append(mp3_folder / "albumtags.json")

    for cand in candidates:
        if cand.is_file():
            print(f"Found album tags file: {cand.name}")
            return str(cand)

    # Broader case-insensitive fallback
    if album_name:
        album_lower = album_name.lower()
        for folder in [mp3_folder, parent_folder]:
            result = find_files_case_insensitive(folder, [f"albumtags_{album_lower}*.json", "albumtags_*.json"])
            if result:
                print(f"Found album tags file (case-insensitive): {result.name}")
                return str(result)

    for folder in [parent_folder, mp3_folder]:
        result = find_files_case_insensitive(folder, ["albumtags.json", "albumtags_*.json"])
        if result:
            print(f"Found album tags file (case-insensitive): {result.name}")
            return str(result)

    return None


def find_tags_file(mp3_path: str) -> Optional[str]:
    """Auto-detect song-level tags file case-insensitively."""
    mp3_path = Path(mp3_path)
    folder = mp3_path.parent
    stem = mp3_path.stem

    patterns = [f"{stem}.json", f"mp3tags_{stem}.json", "mp3tags.json"]
    result = find_files_case_insensitive(folder, patterns)
    if result:
        print(f"Found song tags file: {result.name}")
        return str(result)
    return None


def set_tags_on_file(mp3_path: str, 
                     author_tags: Dict, 
                     album_tags: Dict, 
                     song_tags: Dict, 
                     albumart_path: Optional[str],
                     total_tracks: Optional[int]):
    """Apply all tags to a single MP3 file."""
    try:
        # Load with EasyID3 for text tags
        try:
            audio = MP3(mp3_path, ID3=EasyID3)
        except ID3Error:
            audio = MP3(mp3_path)
            audio.add_tags()

        # Apply text tags (EasyID3)
        if author_tags.get("artist"):
            audio["artist"] = author_tags["artist"]
        if author_tags.get("albumartist"):
            audio["albumartist"] = author_tags.get("albumartist") or author_tags.get("artist")
        if author_tags.get("copyright"):
            audio["copyright"] = author_tags["copyright"]

        if album_tags.get("album"):
            audio["album"] = album_tags["album"]
        if album_tags.get("albumartist"):
            audio["albumartist"] = album_tags["albumartist"]
        if album_tags.get("date") or album_tags.get("year"):
            audio["date"] = album_tags.get("date") or album_tags.get("year")
        if album_tags.get("genre"):
            audio["genre"] = album_tags["genre"]

        if total_tracks:
            track_num = song_tags.get("tracknumber") or "1"
            audio["tracknumber"] = f"{track_num}/{total_tracks}"

        for key, value in song_tags.items():
            if value:
                if key == "tracknumber" and total_tracks:
                    audio["tracknumber"] = f"{value}/{total_tracks}"
                else:
                    audio[key] = str(value)

        # === Album Artwork Handling (Fixed) ===
        if albumart_path and os.path.isfile(albumart_path):
            with open(albumart_path, "rb") as img:
                img_data = img.read()
            
            ext = Path(albumart_path).suffix.lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

            # Switch to full ID3 to safely delete existing APIC frames
            full_tags = MP3(mp3_path).tags
            if full_tags is None:
                full_tags = ID3()
                audio.tags = full_tags  # ensure we have tags

            full_tags.delall("APIC")   # This is the fix — delall only works on full ID3

            full_tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc="Cover",
                    data=img_data
                )
            )

            # Copy the updated tags back if needed
            if hasattr(audio, 'tags'):
                audio.tags = full_tags

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
        print(f"Processing {mp3_name}...")

        song_tags = {}
        album_tags = {}
        album_tags_dir = str(Path(mp3_file).parent)
        tags_used = False

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

        if args.albumtags:
            album_tags = load_json_file(args.albumtags)
            album_tags_dir = str(Path(args.albumtags).parent)
            print(f"Using provided album tags file: {Path(args.albumtags).name}")
        else:
            albumtags_path = find_albumtags_file(mp3_file, song_tags)
            if albumtags_path:
                album_tags = load_json_file(albumtags_path)
                album_tags_dir = str(Path(albumtags_path).parent)
            elif args.verbose:
                print(f"No albumtags file found for {mp3_name}")

        if "tracknumber" not in song_tags:
            filename = Path(mp3_file).stem
            match = re.search(r'^0*(\d+)', filename)
            if match:
                song_tags["tracknumber"] = match.group(1)

        album_art_path = get_album_art_path(album_tags, albumart_dir, album_tags_dir)
        total_tracks = (album_tags.get("totaltracks") or 
                       album_tags.get("tracktotal") or 
                       album_tags.get("number_of_tracks"))

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