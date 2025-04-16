#!/bin/bash

base_dir="/mnt/d/Musique"

green="\033[92m"
white="\033[97m"
nocolor="\033[0m"

echo && echo -e "${green}Начало обработки${nocolor}" && echo

# Проходим по всем подпапкам
find "$base_dir" -mindepth 1 -maxdepth 1 -type d | while read -r album_dir; do
  echo "📂 Папка: $album_dir"

  # Проходим по mp3-файлам внутри папки
  find "$album_dir" -type f -name "*.mp3" | while read -r file; do
    echo && echo "🎵 Обработка: $(basename "$file")"

    # Получаем значение поля album
    album_field=$(eyeD3 "$file" | grep "album:" | sed -E 's/.*album:[[:space:]]*//')
    echo -e "❕ Текущее значение: $album_field"

    # Применяем регулярку: Исполнитель — Альбом (Год)
    if [[ $album_field =~ ^(.+)\ —\ (.+)\ \(((19|20)[0-9]{2})\)$ ]]; then
      artist="${BASH_REMATCH[1]}"
      album="${BASH_REMATCH[2]}"
      year="${BASH_REMATCH[3]}"

      echo "💬 Исправляем: Альбом = '$album', Год = '$year'"

      # Применяем исправления
      # eyeD3 --album "$album" "$file" > /dev/null
      # eyeD3 --release-year "$year" "$file" > /dev/null #TRDC
      # eyeD3 --remove-all-comments "$file" > /dev/null
      id3v2 --album "$album" "$file"
      id3v2 --year "$year" "$file" #TYER
      id3v2 --remove-frame "COMM" "" "$file" > /dev/null

      # Проверяем
      fixed_album=$(eyeD3 "$file" | grep "album:" | sed -E 's/.*album:[[:space:]]*//')
      fixed_year=$(eyeD3 "$file" | grep "recording date:" | sed -E 's/.*recording date:[[:space:]]*([0-9]{4}).*/\1/')
      echo "✅ Исправлено: Альбом = '$fixed_album', Год = '$fixed_year'"
    else
      echo "⚠ Пропущено: шаблон не распознан: '$album_field'"
    fi
  done
done

echo && echo -e "${green}Конец обработки${nocolor}" && echo
