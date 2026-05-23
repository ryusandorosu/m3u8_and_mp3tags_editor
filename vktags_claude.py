#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_mp3_tags.py
───────────────
Редактирует теги MP3-файлов и переименовывает папки по суммарной длительности.

Что делает:
  1. Находит в поле "album" шаблон "Исполнитель — Альбом (Год[, Издатель])"
     и разносит данные по правильным полям (TALB, TDRC/TYER).
  2. Если поле album пустое — берёт данные из имени папки.
  3. Если поле album уже корректно (нет исполнителя и года) — не трогает.
  4. После обработки тегов переименовывает папки, добавляя префикс ЧЧММ.
     Если у одного исполнителя несколько папок — длительность суммируется,
     и все его папки получают одинаковый (общий) префикс.

Требования:
  pip install mutagen
"""

import re
import sys
from pathlib import Path
from typing import Optional

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TALB, TDRC, TYER, ID3NoHeaderError
except ImportError:
    print("Установите зависимость:  pip install mutagen")
    sys.exit(1)

# ────────────────────────────────────────────────────────────────
# Настройки
# ────────────────────────────────────────────────────────────────

BASE_DIR = "/mnt/d/Musique vk"

# True → только показывать, что будет сделано; файлы/папки не трогать
DRY_RUN = False

# ────────────────────────────────────────────────────────────────
# Цвета (ANSI)
# ────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

# ────────────────────────────────────────────────────────────────
# Regex
# ────────────────────────────────────────────────────────────────

# «Широкие» тире: em-dash, en-dash, figure dash
_EM_EN = r'(?:—|–|‒)'
# Любые тире, включая дефис
_ANY   = r'(?:—|–|‒|-)'

# Шаблон "A — B (YYYY[, publisher])"
_PAREN = r'^(.+?)\s*{d}\s*(.+?)\s*\(((19|20)\d{{2}})(?:,.*?)?\)\s*$'

# Для тега альбома: сначала широкое тире, потом дефис
_TAG_EM_RE  = re.compile(_PAREN.format(d=_EM_EN), re.UNICODE)
_TAG_HYP_RE = re.compile(_PAREN.format(d=r'-'),   re.UNICODE)

# Для имени папки: то же самое
_DIR_EM_RE  = re.compile(_PAREN.format(d=_EM_EN), re.UNICODE)
_DIR_HYP_RE = re.compile(_PAREN.format(d=r'-'),   re.UNICODE)

# Для имени папки без скобок: "Artist - Album - Year"
_DIR_DASH_YEAR_RE = re.compile(
    r'^(.+?)\s*' + _ANY + r'\s*(.+?)\s*' + _ANY + r'\s*((19|20)\d{2})\s*$',
    re.UNICODE,
)

# Папка уже переименована (начинается с цифр + пробел)
_PREFIXED_RE = re.compile(r'^\d{3,4}\s')

# ────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ────────────────────────────────────────────────────────────────

def norm_artist(name: str) -> str:
    """Нормализуем имя исполнителя для группировки."""
    return name.strip().lower()


def parse_album_tag(value: str) -> Optional[tuple[str, str, str]]:
    """
    Разбираем значение тега album.
    Если формат "Исполнитель — Альбом (Год)" → возвращаем (artist, album, year).
    Иначе → None (тег уже корректен или не распознан).
    """
    v = value.strip()
    for pat in (_TAG_EM_RE, _TAG_HYP_RE):
        m = pat.match(v)
        if m:
            return m.group(1).strip(), m.group(2).strip(), m.group(3)
    return None


def parse_folder_name(name: str) -> Optional[tuple[str, str, str]]:
    """
    Разбираем имя папки.
    Поддерживаемые форматы:
      • Artist — Album (Year)
      • Artist — Album (Year, Publisher)
      • Artist - Album - Year
    Возвращаем (artist, album, year) или None.
    """
    name = name.strip()
    # Вариант с годом в скобках (сначала широкие тире, затем дефис)
    for pat in (_DIR_EM_RE, _DIR_HYP_RE):
        m = pat.match(name)
        if m:
            return m.group(1).strip(), m.group(2).strip(), m.group(3)
    # Вариант "Исполнитель - Альбом - Год"
    m = _DIR_DASH_YEAR_RE.match(name)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3)
    return None


def mp3_duration(path: Path) -> int:
    """Длительность MP3-файла в секундах."""
    try:
        return int(MP3(str(path)).info.length)
    except Exception:
        return 0


def fmt_hhmm(total_seconds: int) -> str:
    """
    Формат ЧЧММ: 5400 с → '130' (1 ч 30 мин), 300 с → '005' (5 мин).
    """
    total_minutes = total_seconds // 60
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h}{m:02d}"


def write_tags(path: Path, album: str, year: str) -> bool:
    """
    Записываем поля TALB и TDRC/TYER в MP3-файл.
    Возвращает True при успехе.
    """
    if DRY_RUN:
        return True
    try:
        try:
            tags = ID3(str(path))
        except ID3NoHeaderError:
            tags = ID3()

        tags["TALB"] = TALB(encoding=3, text=album)  # UTF-8
        tags["TDRC"] = TDRC(encoding=3, text=year)   # ID3v2.4 recording time
        tags["TYER"] = TYER(encoding=3, text=year)   # ID3v2.3 year (для совместимости)

        tags.save(str(path), v2_version=3)
        return True
    except Exception as exc:
        print(f"    {RED}❌ Ошибка записи тегов: {exc}{RESET}")
        return False


# ────────────────────────────────────────────────────────────────
# Основная логика
# ────────────────────────────────────────────────────────────────

def main() -> None:
    base = Path(BASE_DIR)
    if not base.is_dir():
        print(f"{RED}Директория не найдена: {BASE_DIR}{RESET}")
        sys.exit(1)

    if DRY_RUN:
        print(f"\n{YELLOW}⚠  DRY RUN — изменения не применяются{RESET}")

    print(f"\n{GREEN}{'═' * 50}")
    print(f"  Начало обработки тегов")
    print(f"{'═' * 50}{RESET}\n")

    # folder (str) → artist_key
    folder_artist: dict[str, str] = {}
    # artist_key → суммарные секунды
    artist_secs: dict[str, int] = {}
    # статистика
    stats = {"fixed": 0, "from_folder": 0, "skipped": 0, "errors": 0}

    # ── Первый проход: теги ─────────────────────────────────────
    for album_dir in sorted(base.iterdir()):
        if not album_dir.is_dir():
            continue

        folder_name = album_dir.name

        if _PREFIXED_RE.match(folder_name):
            print(f"⏭  Пропускаем (уже с префиксом): {folder_name}")
            continue

        print(f"\n{CYAN}📂 {folder_name}{RESET}")

        folder_info    = parse_folder_name(folder_name)
        folder_dur_sec = 0
        folder_ak      = None  # artist key для этой папки

        mp3_files = sorted(album_dir.rglob("*.mp3"))
        if not mp3_files:
            print("   ⚠  MP3-файлы не найдены, пропускаем")
            continue

        for mp3 in mp3_files:
            print(f"\n   🎵 {mp3.name}")

            try:
                try:
                    tags = ID3(str(mp3))
                except ID3NoHeaderError:
                    tags = ID3()

                album_val = str(tags.get("TALB", "")).strip()
                tpe1_val  = str(tags.get("TPE1", "")).strip()

                print(f"      ❕ album: {album_val!r}")

                parsed = parse_album_tag(album_val) if album_val else None

                if parsed:
                    # ── Тег содержит «Исполнитель — Альбом (Год)» → чиним ──
                    tag_artist, tag_album, tag_year = parsed
                    action_artist = tpe1_val if tpe1_val else tag_artist
                    print(f"      💬 → album={tag_album!r}  year={tag_year!r}")
                    ok = write_tags(mp3, tag_album, tag_year)
                    if ok:
                        stats["fixed"] += 1
                    else:
                        stats["errors"] += 1
                    if not folder_ak:
                        folder_ak = norm_artist(action_artist)

                elif not album_val and folder_info:
                    # ── Тег пустой — берём из имени папки ──────────────────
                    f_artist, f_album, f_year = folder_info
                    action_artist = tpe1_val if tpe1_val else f_artist
                    print(f"      📁 из папки → album={f_album!r}  year={f_year!r}")
                    ok = write_tags(mp3, f_album, f_year)
                    if ok:
                        stats["from_folder"] += 1
                    else:
                        stats["errors"] += 1
                    if not folder_ak:
                        folder_ak = norm_artist(action_artist)

                else:
                    # ── Тег уже корректен или нет данных ───────────────────
                    if album_val:
                        print(f"      ✅ Тег корректен, не трогаем")
                    else:
                        print(f"      ⚠  Пустой тег, имя папки не распознано — пропускаем")
                    stats["skipped"] += 1

                    if not folder_ak:
                        if tpe1_val:
                            folder_ak = norm_artist(tpe1_val)
                        elif folder_info:
                            folder_ak = norm_artist(folder_info[0])
                        else:
                            folder_ak = norm_artist(folder_name)

            except Exception as exc:
                print(f"      {RED}❌ {exc}{RESET}")
                stats["errors"] += 1

            folder_dur_sec += mp3_duration(mp3)

        # Сохраняем суммарную длительность по исполнителю
        if folder_ak:
            folder_artist[str(album_dir)] = folder_ak
            artist_secs[folder_ak] = artist_secs.get(folder_ak, 0) + folder_dur_sec
            mins = folder_dur_sec // 60
            print(f"\n   ⏱  Папка: {mins // 60}:{mins % 60:02d}")
        else:
            print(f"\n   ⚠  Не удалось определить исполнителя для папки")

    # ── Второй проход: переименование папок ────────────────────
    print(f"\n{GREEN}{'═' * 50}")
    print(f"  Переименование папок")
    print(f"{'═' * 50}{RESET}\n")

    renamed = 0
    for album_dir in sorted(base.iterdir()):
        if not album_dir.is_dir():
            continue

        folder_name = album_dir.name
        if _PREFIXED_RE.match(folder_name):
            continue

        folder_str = str(album_dir)
        if folder_str not in folder_artist:
            print(f"⚠  Нет данных для переименования: {folder_name}")
            continue

        ak         = folder_artist[folder_str]
        total_secs = artist_secs.get(ak, 0)
        prefix     = fmt_hhmm(total_secs)
        new_name   = f"{prefix} {folder_name}"
        new_path   = album_dir.parent / new_name

        flag = "(DRY) " if DRY_RUN else ""
        print(f"  {flag}🚀 {folder_name!r}")
        print(f"       → {new_name!r}\n")

        if not DRY_RUN:
            try:
                album_dir.rename(new_path)
                renamed += 1
            except Exception as exc:
                print(f"  {RED}❌ Ошибка переименования: {exc}{RESET}\n")

    # ── Сводка ──────────────────────────────────────────────────
    print(f"\n{GREEN}{'═' * 50}")
    print(f"  Длительность по исполнителям")
    print(f"{'═' * 50}{RESET}")
    for ak, secs in sorted(artist_secs.items(), key=lambda x: (-x[1], x[0])):
        m = secs // 60
        print(f"  🎤  {ak}  —  {m // 60}:{m % 60:02d}")

    print(f"\n{GREEN}{'═' * 50}")
    print(f"  Итог")
    print(f"{'═' * 50}{RESET}")
    print(f"  ✏  Тегов исправлено из тега:    {stats['fixed']}")
    print(f"  📁 Тегов взято из папки:        {stats['from_folder']}")
    print(f"  ⏭  Пропущено (уже корректны):   {stats['skipped']}")
    print(f"  ❌ Ошибок:                       {stats['errors']}")
    print(f"  📂 Папок переименовано:          {renamed}")
    print(f"\n{GREEN}Конец обработки{RESET}\n")


if __name__ == "__main__":
    main()
