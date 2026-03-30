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
- Auto-detects albumtags.json and mp3tags.json files if not specified
- Respects your rules for resolving album artwork paths
- Lightweight and fast
- Version 1.10

## Project Structure
mp3tagger/
├── mp3tagger.py          # Main script
├── requirements.txt       # Python dependencies
├── examples/
│   ├── author.json        # Author-specific tags
│   ├── albumtags.json     # Album-level tags (shared)
│   └── mp3tags.json       # Song-level tags (per track or shared)
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

```bash
# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

After activation, your terminal prompt should show (venv).

### 3. Install Dependencies
With the virtual environment activated:
```bash
pip install -r requirements.txt
```

## Usage
Basic Command
```bash
python mp3tagger.py --input <path_to_mp3_or_folder> \
                    --author <path_to_author.json> \
                    [--albumtags <path_to_albumtags.json>] \
                    [--tags <path_to_mp3tags.json>] \
                    [--albumart <path_to_art_folder>] \
                    [--verbose]
```

### Arguments
- `--input`: Required. Path to a single .mp3 file or directory containing .mp3 files
- `--author`: Required. Path to author JSON file
- `--albumtags`: Optional. Path to album-level JSON tags file. If omitted, auto-detected based on album name or folder structure
- `--tags`: Optional. Path to song-level JSON tags file. If omitted, auto-detected based on MP3 filename or folder
- `--albumart`: Optional. Directory containing album artwork files
- `--verbose`: Optional. Show detailed messages for files without tags files

### Examples
Tag a single MP3 file:
```bash
python mp3tagger.py --input "My Track.mp3" \
                    --author "author.json"
```

Tag an entire album folder (auto-detecting tags files):
```bash
python mp3tagger.py --input "./My Album" \
                    --author "./author.json" \
                    --albumart "./art" \
                    --verbose
```

Specify tags files explicitly:
```bash
python mp3tagger.py --input "./My Album" \
                    --albumtags "./albumtags.json" \
                    --tags "./mp3tags.json" \
                    --author "./author.json" \
                    --albumart "./art"
```

### Album Artwork Path Rules

If `--albumart` is provided → relative paths in albumtags.json are resolved against that folder.
If `--albumart` is not provided → relative paths are resolved relative to the albumtags.json file.

Supports JPEG and PNG files. If no extension is specified in albumtags.json, tries .jpg, .jpeg, .png in order.

### Auto-Detection
- **Album tags**: Looks for `albumtags.json`, `albumtags_<album_name>.json`, or variations in the MP3's folder and parent folder
- **Song tags**: Looks for `<filename>.json`, `mp3tags_<filename>.json`, or `mp3tags.json` in the MP3's folder
- Case-insensitive matching supported

### Notes

The script tries to auto-detect track numbers from filenames (e.g. `01 - Title.mp3` → track 1).
Always test on a copy of your files first.
Works with MP3 files only.
Only updates files when tags or artwork have changed.

## Requirements

Python 3.8 or higher
See requirements.txt (only mutagen)

## License
Free to use and modify for personal and commercial projects.