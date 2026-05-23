#!/usr/bin/env python3

from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TDRC
import re
import unicodedata

BASE_DIR = Path("/mnt/d/Musique vk")

DASHES = r"[—–-]"

# ----------------------------
# regex patterns
# ----------------------------

PATTERNS = [
    # Artist — Album (2025, Label)
    re.compile(
        rf"^(?P<artist>.+?)\s*{DASHES}\s*(?P<album>.+?)\s*\((?P<year>(19|20)\d{{2}})(?:,.*?)?\)$",
        re.UNICODE,
    ),

    # Artist - Album - 2025
    re.compile(
        rf"^(?P<artist>.+?)\s*{DASHES}\s*(?P<album>.+?)\s*{DASHES}\s*(?P<year>(19|20)\d{{2}})$",
        re.UNICODE,
    ),
]


def normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip())


def parse_album_string(text: str):
    text = normalize(text)

    for pattern in PATTERNS:
        m = pattern.match(text)
        if m:
            return {
                "artist": normalize(m.group("artist")),
                "album": normalize(m.group("album")),
                "year": m.group("year"),
            }

    return None


def album_field_needs_fix(album: str):
    """
    Проверяем содержит ли поле album:
    - исполнителя
    - год
    """

    if not album:
        return True

    if re.search(r"(19|20)\d{2}", album):
        return True

    if re.search(rf"\s*{DASHES}\s*", album):
        return True

    return False


def get_audio_duration_seconds(mp3_path: Path):
    try:
        audio = MP3(mp3_path)
        return int(audio.info.length)
    except Exception:
        return 0


def format_hhmm(seconds: int):
    total_minutes = seconds // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}{minutes:02d}"


# -------------------------------------------------------
# pass 1
# collect artist durations
# -------------------------------------------------------

artist_total_duration = {}
folder_artist_map = {}

for folder in BASE_DIR.iterdir():

    if not folder.is_dir():
        continue

    mp3_files = list(folder.rglob("*.mp3"))

    if not mp3_files:
        continue

    folder_name = folder.name

    folder_info = parse_album_string(folder_name)

    detected_artist = None

    total_seconds = 0

    for mp3_file in mp3_files:

        total_seconds += get_audio_duration_seconds(mp3_file)

        try:
            tags = EasyID3(mp3_file)
        except Exception:
            continue

        artist = tags.get("artist", [""])[0]
        album = tags.get("album", [""])[0]

        source_text = album if album.strip() else folder_name

        parsed = parse_album_string(source_text)

        if parsed:
            detected_artist = parsed["artist"]

    if detected_artist:
        key = detected_artist.casefold()

        artist_total_duration[key] = (
            artist_total_duration.get(key, 0)
            + total_seconds
        )

        folder_artist_map[folder] = detected_artist


# -------------------------------------------------------
# pass 2
# fix tags
# -------------------------------------------------------

for folder in BASE_DIR.iterdir():

    if not folder.is_dir():
        continue

    print(f"\n📂 {folder.name}")

    mp3_files = list(folder.rglob("*.mp3"))

    for mp3_file in mp3_files:

        print(f"🎵 {mp3_file.name}")

        try:
            tags = EasyID3(mp3_file)
        except Exception:
            print("   ⚠ no ID3")
            continue

        album = tags.get("album", [""])[0]

        if not album_field_needs_fix(album):
            print(f"   ✅ album already correct: {album}")
            continue

        source_text = album if album.strip() else folder.name

        parsed = parse_album_string(source_text)

        if not parsed:
            print("   ⚠ unable to parse")
            continue

        fixed_album = parsed["album"]
        fixed_year = parsed["year"]

        print(f"   ✔ album -> {fixed_album}")
        print(f"   ✔ year  -> {fixed_year}")

        tags["album"] = [fixed_album]
        tags.save(v2_version=3)

        id3 = ID3(mp3_file)
        id3.delall("TDRC")
        id3.add(TDRC(encoding=3, text=fixed_year))
        id3.save(v2_version=3)


# -------------------------------------------------------
# pass 3
# rename folders
# -------------------------------------------------------

for folder, artist in folder_artist_map.items():

    total_seconds = artist_total_duration.get(
        artist.casefold(),
        0,
    )

    hhmm = format_hhmm(total_seconds)

    original_name = folder.name

    # remove existing HHMM prefix if exists
    cleaned = re.sub(r"^\d{4}\s+", "", original_name)

    new_name = f"{hhmm} {cleaned}"

    if new_name == original_name:
        continue

    target = folder.parent / new_name

    print(f"\n📁 rename:")
    print(f"   {original_name}")
    print(f"   ->")
    print(f"   {new_name}")

    folder.rename(target)

print("\n✅ Done")
