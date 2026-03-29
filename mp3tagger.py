#!/usr/bin/env python3
"""
MP3 Tagger for Album / Author / Song-specific metadata
Supports single MP3 or a directory of MP3s.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from mutagen.easyid3 import EasyID3

# Versioning constants
VERSION_HIGH = 1
VERSION_LOW = 5

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"JSON file {file_path} must contain a single object (dict)")
        return data
    except Exception as e:
        print(f"Error loading JSON file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def get_album_art_path(album_tags: Dict, albumart_dir: Optional[str], tags_file_dir: str) -> Optional[str]:
    """Resolve album artwork path with the specified priority rules."""
    if not album_tags.get("albumart"):
        return None

    art_rel = album_tags["albumart"]

    # If --albumart parameter is provided, treat relative path as relative to it
    if albumart_dir:
        base = Path(albumart_dir)
    else:
        # Otherwise relative to the album tags JSON file
        base = Path(tags_file_dir)

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
        # Load or create tags (EasyID3 for common fields)
        try:
            audio = MP3(mp3_path, ID3=EasyID3)
        except error:
            audio = MP3(mp3_path)
            audio.add_tags()

        # Author tags (applied to every track)
        if author_tags.get("artist"):
            audio["artist"] = author_tags["artist"]
        if author_tags.get("albumartist"):
            audio["albumartist"] = author_tags["albumartist"]
        if author_tags.get("copyright"):
            audio["copyright"] = author_tags["copyright"]  # TXXX or COMM depending on version

        # Album tags (common to all tracks)
        if album_tags.get("album"):
            audio["album"] = album_tags["album"]
        if album_tags.get("albumartist"):
            audio["albumartist"] = album_tags["albumartist"]
        if album_tags.get("date") or album_tags.get("year"):
            audio["date"] = album_tags.get("date") or album_tags.get("year")
        if album_tags.get("genre"):
            audio["genre"] = album_tags["genre"]

        # Total tracks (format: "track/total")
        if total_tracks:
            current_track = song_tags.get("tracknumber") or "1"
            audio["tracknumber"] = f"{current_track}/{total_tracks}"

        # Song-specific tags (override anything above if present)
        for key, value in song_tags.items():
            if value:  # Only set non-empty values
                if key == "tracknumber" and total_tracks:
                    audio["tracknumber"] = f"{value}/{total_tracks}"
                else:
                    audio[key] = value

        # Album artwork (embedded)
        if albumart_path and os.path.isfile(albumart_path):
            with open(albumart_path, "rb") as img:
                img_data = img.read()
            
            # Determine MIME type
            ext = Path(albumart_path).suffix.lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

            # Remove any existing APIC frames first (clean)
            if audio.tags:
                audio.tags.delall("APIC")

            # Add new cover (type=3 = COVER_FRONT)
            audio.tags.add(
                APIC(
                    encoding=3,          # UTF-8
                    mime=mime,
                    type=3,              # Cover (front)
                    desc="Cover",
                    data=img_data
                )
            )

        audio.save()
        print(f"✓ Tagged: {os.path.basename(mp3_path)}")

    except Exception as e:
        print(f"✗ Error tagging {mp3_path}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Batch MP3 tagger with album/author/song JSON support")
    parser.add_argument("--input", required=True, help="Single .mp3 file or directory containing .mp3 files")
    parser.add_argument("--albumart", help="Directory containing album artwork (absolute path)")
    parser.add_argument("--albumtags", required=True, help="Path to album-level JSON tags file")
    parser.add_argument("--tags", required=True, help="Path to song-level JSON tags file (can be relative to input)")
    parser.add_argument("--author", required=True, help="Path to author JSON file")

    args = parser.parse_args()

    # Load the three JSON files
    author_tags = load_json_file(args.author)
    album_tags = load_json_file(args.albumtags)
    song_tags_template = load_json_file(args.tags)  # This is the base; per-track overrides can be added later if needed

    albumart_dir = args.albumart
    album_tags_dir = str(Path(args.albumtags).parent)

    # Resolve album art path once (same for whole album)
    album_art_path = get_album_art_path(album_tags, albumart_dir, album_tags_dir)
    total_tracks = album_tags.get("totaltracks") or album_tags.get("tracktotal") or album_tags.get("number_of_tracks")

    # Determine input type
    input_path = Path(args.input)
    mp3_files = []

    if input_path.is_file() and str(input_path).lower().endswith(".mp3"):
        mp3_files = [str(input_path)]
    elif input_path.is_dir():
        mp3_files = [str(f) for f in input_path.rglob("*.mp3") if f.is_file()]
        if not mp3_files:
            print("No .mp3 files found in the directory.", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: --input must be a valid .mp3 file or directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(mp3_files)} MP3 file(s) to tag.")

    # Process each file
    for mp3_file in mp3_files:
        # For song-specific tags: by default we use the provided --tags file for all tracks.
        # If you want per-track JSON files (e.g., 01.json, 02.json), you can extend this logic here.
        current_song_tags = song_tags_template.copy()

        # Optional: auto-detect track number from filename (common pattern: "01 - Title.mp3")
        filename = Path(mp3_file).stem
        # Simple heuristic - take first number if present
        import re
        match = re.search(r'^(\d+)', filename)
        if match and "tracknumber" not in current_song_tags:
            current_song_tags["tracknumber"] = match.group(1)

        set_tags_on_file(
            mp3_path=mp3_file,
            author_tags=author_tags,
            album_tags=album_tags,
            song_tags=current_song_tags,
            albumart_path=album_art_path,
            total_tracks=total_tracks
        )

    print("\nTagging complete!")


if __name__ == "__main__":
    print(f"Telegram HTML Parser v{VERSION_HIGH}.{VERSION_LOW}")
    main()