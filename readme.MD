# MP3 Batch Tagger

A simple and powerful Python script to batch-apply professional MP3 metadata (ID3 tags) using separate JSON files for **author**, **album**, and **song**-specific information.

Perfect for producers exporting from FL Studio (or any DAW) who want full control over album name, album artist, track numbers, total tracks, copyright, and embedded album artwork — things FL Studio doesn't support natively.

## Features

- Supports a single MP3 file **or** an entire folder of MP3s
- Separate JSON files for:
  - Author info (artist name, album artist, copyright, etc.)
  - Album info (album title, genre, year, total tracks, artwork path)
  - Song info (title, track number, genre, etc.)
- Automatically embeds album artwork (JPEG or PNG)
- Handles track numbering intelligently (`"1/12"`, `"2/12"`, etc.)
- Respects your rules for resolving album artwork paths
- Lightweight and fast

## Project Structure
mp3-tagger/
├── mp3_tagger.py          # Main script
├── requirements.txt       # Python dependencies
├── examples
  ├── author.json            # Author-specific tags
  ├── album.json             # Album-level tags (shared)
  └── song.json              # Song-level tags (per track or shared)
└── README.md              # this file

## Setup

### 1. Create a Python Virtual Environment (Recommended)

It is **highly recommended** to use a virtual environment to keep dependencies isolated.

In the project's root folder, run the following commands:

```bash
# Windows
python -m venv venv

# macOS / Linux
python3 -m venv venv
```

### 2. Activate the virtual environment:

# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

After activation, your terminal prompt should show (venv).

### 3. Install Dependencies
With the virtual environment activated:
Bashpip install -r requirements.txt

### 4. Usage
Basic Command
```bash
python mp3_tagger.py --input <path_to_mp3_or_folder> \
                     --albumtags <path_to_album.json> \
                     --tags <path_to_song.json> \
                     --author <path_to_author.json> \
                     [--albumart <path_to_art_folder>]
```

#### Examples
Tag a single MP3 file:
```bash
python mp3_tagger.py --input "My Track.mp3" \
                     --albumtags "album.json" \
                     --tags "song.json" \
                     --author "author.json"
```

Tag an entire album folder:
```bash
python mp3_tagger.py --input "./My Album" \
                     --albumtags "./album.json" \
                     --tags "./song.json" \
                     --author "./author.json" \
                     --albumart "./art"
```

#### Album Artwork Path Rules

If --albumart is provided → relative paths in album.json are resolved against that folder.
If --albumart is not provided → relative paths are resolved relative to the album.json file.

#### Notes

The script tries to auto-detect track numbers from filenames (e.g. 01 - Title.mp3 → track 1).
Always test on a copy of your files first.
Works with MP3 files only.

## Requirements

Python 3.8 or higher
See requirements.txt (only mutagen)

## License
Free to use and modify for personal and commercial projects.