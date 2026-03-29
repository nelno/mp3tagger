#!/usr/bin/env python3
"""
MP3 Tagger for Album / Author / Song-specific metadata
Supports single MP3 or a directory of MP3s.
Per-song tags file detection in recursive mode (<song file name>.json or mp3tags_<song file name>.json)
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


def find_song_tags_file(mp3_path: str) -> Optional[str]:
    """Auto-detect song-specific tags JSON file."""
    mp3_path = Path(mp3_path)
    folder = mp3_path.parent
    stem = mp3_path.stem

    # Possible tag file names
    candidates = [
        folder / f"{stem}.json",
        folder / f"mp3tags_{stem}.json"
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

    if albumart_dir:
        base = Path(albumart_dir)
    else:
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

        # Song-specific tags (override previous)
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

            if audio.tags:
                audio.tags.delall("APIC")

            audio.tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Cover front
                    desc="Cover",
                    data=img_data
                )
            )

        audio.save()
        print(f"✓ Tagged: {Path(mp3_path).name}")

    except Exception as e:
        print(f"✗ Error tagging {Path(mp3_path).name}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="MP3 Batch Tagger with smart per-song JSON detection")
    parser.add_argument("--input", required=True, help="Single .mp3 file or directory containing .mp3 files")
    parser.add_argument("--albumart", help="Directory containing album artwork (absolute)")
    parser.add_argument("--albumtags", required=True, help="Path to album-level JSON tags file")
    parser.add_argument("--tags", help="Path to song-level JSON tags file (optional - auto-detected if omitted)")
    parser.add_argument("--author", required=True, help="Path to author JSON file")

    args = parser.parse_args()

    # Load fixed JSON files
    author_tags = load_json_file(args.author)
    album_tags = load_json_file(args.albumtags)

    albumart_dir = args.albumart
    album_tags_dir = str(Path(args.albumtags).parent)

    # Resolve album art once
    album_art_path = get_album_art_path(album_tags, albumart_dir, album_tags_dir)
    total_tracks = album_tags.get("totaltracks") or album_tags.get("tracktotal") or album_tags.get("number_of_tracks")

    # Determine input files
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

    print(f"Found {len(mp3_files)} MP3 file(s) to tag.\n")

    # Process each file
    for mp3_file in mp3_files:
        # Determine song tags file
        if args.tags:
            song_tags = load_json_file(args.tags)
            print(f"Using provided song tags file: {Path(args.tags).name}")
        else:
            song_tags_path = find_song_tags_file(mp3_file)
            song_tags = load_json_file(song_tags_path) if song_tags_path else {}

        # Auto-detect track number from filename if not in JSON
        if "tracknumber" not in song_tags:
            filename = Path(mp3_file).stem
            match = re.search(r'^0*(\d+)', filename)
            if match:
                song_tags["tracknumber"] = match.group(1)

        set_tags_on_file(
            mp3_path=mp3_file,
            author_tags=author_tags,
            album_tags=album_tags,
            song_tags=song_tags,
            albumart_path=album_art_path,
            total_tracks=total_tracks
        )

    print("\nTagging complete!")


if __name__ == "__main__":
    main()