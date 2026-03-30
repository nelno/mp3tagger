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


def get_album_art_path(album_tags: Dict, albumart_dir: Optional[str], tags_file_dir: str, verbose: bool = False) -> Optional[str]:
    """Resolve album artwork path. Supports extension-less names (tries jpg/jpeg/png)."""
    if not album_tags.get("albumart"):
        return None

    art_rel = album_tags["albumart"].strip()
    base = Path(albumart_dir) if albumart_dir else Path(tags_file_dir)

    # If it already has an extension, use it directly
    if Path(art_rel).suffix:
        art_path = base / art_rel
        if art_path.is_file():
            if verbose:
                print(f"Found album art: {art_path.name}")
            return str(art_path)
        else:
            print(f"Warning: Album art not found at {art_path}", file=sys.stderr)
            return None

    # No extension → try .jpg, .jpeg, .png (in that order)
    for ext in [".jpg", ".jpeg", ".png"]:
        art_path = base / f"{art_rel}{ext}"
        if art_path.is_file():
            if verbose:
                print(f"Found album art: {art_path.name}")
            return str(art_path)

    print(f"Warning: Album art not found for '{art_rel}' (tried .jpg, .jpeg, .png)", file=sys.stderr)
    return None


def find_albumtags_file(mp3_path: str, song_tags: Dict[str, Any], verbose: bool = False) -> Optional[str]:
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
            if verbose:
                print(f"Found album tags file: {cand.name}")
            return str(cand)

    # Broader case-insensitive fallback
    if album_name:
        album_lower = album_name.lower()
        for folder in [mp3_folder, parent_folder]:
            result = find_files_case_insensitive(folder, [f"albumtags_{album_lower}*.json", "albumtags_*.json"])
            if result:
                if verbose:
                    print(f"Found album tags file (case-insensitive): {result.name}")
                return str(result)

    for folder in [parent_folder, mp3_folder]:
        result = find_files_case_insensitive(folder, ["albumtags.json", "albumtags_*.json"])
        if result:
            if verbose:
                print(f"Found album tags file (case-insensitive): {result.name}")
            return str(result)

    return None


def find_tags_file(mp3_path: str, verbose: bool = False) -> Optional[str]:
    """Auto-detect song-level tags file case-insensitively."""
    mp3_path = Path(mp3_path)
    folder = mp3_path.parent
    stem = mp3_path.stem

    patterns = [f"{stem}.json", f"mp3tags_{stem}.json", "mp3tags.json"]
    result = find_files_case_insensitive(folder, patterns)
    if result:
        if verbose:
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

        # Build the intended new tags (text tags only)
        new_tags: Dict[str, str] = {}

        if author_tags.get("artist"):
            new_tags["artist"] = author_tags["artist"]
        if author_tags.get("albumartist"):
            new_tags["albumartist"] = author_tags.get("albumartist") or author_tags.get("artist")
        if author_tags.get("copyright"):
            new_tags["copyright"] = author_tags["copyright"]

        if album_tags.get("album"):
            new_tags["album"] = album_tags["album"]
        if album_tags.get("albumartist"):
            new_tags["albumartist"] = album_tags["albumartist"]
        if album_tags.get("date") or album_tags.get("year"):
            new_tags["date"] = album_tags.get("date") or album_tags.get("year")
        if album_tags.get("genre"):
            new_tags["genre"] = album_tags["genre"]

        if total_tracks:
            track_num = song_tags.get("tracknumber") or "1"
            new_tags["tracknumber"] = f"{track_num}/{total_tracks}"

        for key, value in song_tags.items():
            if value:
                if key == "tracknumber" and total_tracks:
                    new_tags["tracknumber"] = f"{value}/{total_tracks}"
                else:
                    new_tags[key] = str(value)

        # Get current text tags for comparison (ignore album art)
        current_tags = {}
        for key in new_tags.keys():
            try:
                val = audio.get(key)
                if val:
                    current_tags[key] = str(val[0]) if isinstance(val, list) else str(val)
            except Exception:
                pass

        # === Album Artwork Change Detection ===
        art_changed = False
        new_art_data = None

        if albumart_path and os.path.isfile(albumart_path):
            with open(albumart_path, "rb") as img:
                new_art_data = img.read()

            # Load full ID3 to check existing APIC
            full_tags = MP3(mp3_path).tags or ID3()
            existing_apics = full_tags.getall("APIC")

            # Look for cover (type 3) or any APIC
            current_art_data = None
            for apic in existing_apics:
                if apic.type == 3 or not current_art_data:  # prefer COVER_FRONT
                    current_art_data = apic.data
                    break

            if current_art_data != new_art_data:
                art_changed = True

        # Only proceed with save if text tags or artwork differ
        if current_tags == new_tags and not art_changed:
            print(f"No changes detected.")
            return True, False   # (success, was_updated)

        # Apply text tags
        for key, value in new_tags.items():
            audio[key] = value

        # Apply album artwork if we have new data
        if new_art_data:
            ext = Path(albumart_path).suffix.lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

            full_tags = MP3(mp3_path).tags
            if full_tags is None:
                full_tags = ID3()
                audio.tags = full_tags

            full_tags.delall("APIC")

            full_tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc="Cover",
                    data=new_art_data
                )
            )

            if hasattr(audio, 'tags'):
                audio.tags = full_tags

        audio.save()
        return True, True   # (success, was_updated)

    except Exception as e:
        print(f"✗ Error tagging {Path(mp3_path).name}: {e}", file=sys.stderr)
        return False, False


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

    processed_count = 0
    updated_count = 0
    nochange_count = 0
    skipped_tags_count = 0
    error_count = 0

    for mp3_file in mp3_files:
        mp3_name = Path(mp3_file).name
        print(f"Processing {mp3_name}...")

        song_tags = {}
        album_tags = {}
        album_tags_dir = str(Path(mp3_file).parent)
        tags_used = False

        if args.tags:
            song_tags = load_json_file(args.tags)
            if args.verbose:
                print(f"Using provided song tags file: {Path(args.tags).name}")
            tags_used = True
        else:
            tags_path = find_tags_file(mp3_file, args.verbose)
            if tags_path:
                song_tags = load_json_file(tags_path)
                if args.verbose:
                    print(f"Found song tags file: {Path(tags_path).name}")
                tags_used = True
            elif args.verbose:
                print(f"No song tags file found for {mp3_name}")

        if args.albumtags:
            album_tags = load_json_file(args.albumtags)
            album_tags_dir = str(Path(args.albumtags).parent)
            if args.verbose:
                print(f"Using provided album tags file: {Path(args.albumtags).name}")
        else:
            albumtags_path = find_albumtags_file(mp3_file, song_tags, args.verbose)
            if albumtags_path:
                album_tags = load_json_file(albumtags_path)
                album_tags_dir = str(Path(albumtags_path).parent)
                if args.verbose:
                    print(f"Found album tags file: {Path(albumtags_path).name}")
            elif args.verbose:
                print(f"No albumtags file found for {mp3_name}")

        album_art_path = get_album_art_path(album_tags, albumart_dir, album_tags_dir, args.verbose)
        total_tracks = (album_tags.get("totaltracks") or 
                       album_tags.get("tracktotal") or 
                       album_tags.get("number_of_tracks"))

        if tags_used:
            processed_count += 1
            success, was_updated = set_tags_on_file(
                mp3_path=mp3_file,
                author_tags=author_tags,
                album_tags=album_tags,
                song_tags=song_tags,
                albumart_path=album_art_path,
                total_tracks=total_tracks
            )
            if success:
                if was_updated:
                    print(f"✓ Tagged: {mp3_name}")
                    updated_count += 1
                else:
                    nochange_count += 1
            else:
                error_count += 1
        else:
            print(f"– Skipped: {mp3_name} (no song tags file found)")
            skipped_tags_count += 1

    print(f"\nTagging complete!")
    print(f"Processed: {processed_count} MP3(s)")
    print(f"Updated: {updated_count} MP3(s)")
    print(f"Skipped (no changes): {nochange_count} MP3(s)")
    print(f"Skipped (no song tags): {skipped_tags_count} MP3(s)")
    if error_count:
        print(f"Skipped due to errors: {error_count} MP3(s)")


if __name__ == "__main__":
    print(f"mp3tagger v{VERSION_HIGH}.{VERSION_LOW}")
    main()