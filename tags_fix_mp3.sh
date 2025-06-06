#!/bin/bash

base_dir="/mnt/d/Musique"

green="\033[92m"
white="\033[97m"
nocolor="\033[0m"

echo && echo -e "${green}Начало обработки${nocolor}" && echo

# Ассоциативный массив для хранения общей длительности по артисту
declare -A artist_durations

# Проходим по всем подпапкам
for album_dir in "$base_dir"/*/; do
  album_dir="${album_dir%/}" # убираем слэш на конце
  album_name=$(basename "$album_dir")
  # Пропускаем папки, которые уже начинаются с формата ДЛИТЕЛЬНОСТЬ ИМЯ
  if [[ $album_name =~ ^[0-9]{3,4}\  ]]; then
    echo "⏭ Пропущено (уже префикс): $album_name"
    continue
  fi

  echo && echo "📂 Папка: $album_dir"

  total_seconds=0
  first_artist=""

  # Проходим по mp3-файлам внутри папки
  mapfile -t mp3_files < <(find "$album_dir" -type f -name "*.mp3")
  for file in "${mp3_files[@]}"; do
    echo && echo "🎵 Обработка: $(basename "$file")"

    # Получаем значение поля album
    album_field=$(eyeD3 "$file" | grep "album:" | sed -E 's/.*album:[[:space:]]*//')
    echo -e "❕ Текущее значение: $album_field"

    # Применяем регулярку: Исполнитель — Альбом (Год) или Исполнитель - Альбом (Год)
    # if [[ $album_field =~ ^(.+)\ —\ (.+)\ \(((19|20)[0-9]{2})\)$ ]]; then
    if [[ $album_field =~ ^(.+)[[:space:]]*[-—][[:space:]]*(.+)\ \(((19|20)[0-9]{2})\)$ ]]; then
      artist="${BASH_REMATCH[1]}"
      album="${BASH_REMATCH[2]}"
      year="${BASH_REMATCH[3]}"

      # Приводим имя артиста к нижнему регистру для корректного группирования
      artist_group=$(echo "$artist" | tr '[:upper:]' '[:lower:]')
      # Сохраняем первого исполнителя
      [[ -z "$first_artist" ]] && first_artist="$artist_group"

      echo "💬 Исправляем: Альбом = '$album', Год = '$year'"

      # Применяем исправления
      # eyeD3 --album "$album" "$file" > /dev/null
      # eyeD3 --release-year "$year" "$file" > /dev/null #TRDC
      # eyeD3 --remove-all-comments "$file" > /dev/null
      id3v2 --album "$album" "$file"
      id3v2 --year "$year" "$file" #TYER
      id3v2 --remove-frame "COMM" "$file" > /dev/null #comments
      id3v2 --remove-frame "TPE2" "$file" > /dev/null #album artist
      id3v2 --remove-frame "TEXT" "$file" > /dev/null #lyricist
      id3v2 --remove-frame "USLT" "$file" > /dev/null #texts

      # Проверяем
      fixed_album=$(eyeD3 "$file" | grep "album:" | sed -E 's/.*album:[[:space:]]*//')
      fixed_year=$(eyeD3 "$file" | grep "recording date:" | sed -E 's/.*recording date:[[:space:]]*([0-9]{4}).*/\1/')
      echo "✅ Исправлено: Альбом = '$fixed_album', Год = '$fixed_year'"

      # Считаем длительность файла
      duration=$(eyeD3 "$file" | grep "Time:" | grep -oP "\d+:\d+")
      if [[ $duration =~ ([0-9]+):([0-9]+) ]]; then
        minutes=${BASH_REMATCH[1]}
        seconds=${BASH_REMATCH[2]}
        file_seconds=$((10#$minutes * 60 + 10#$seconds))
        total_seconds=$((10#$total_seconds + 10#$file_seconds)) # не нужно мб
        
        # Добавляем длительность в artist_durations
        artist_durations["$artist_group"]=$(( ${artist_durations["$artist_group"]:-0} + 10#$file_seconds ))
      fi

    else
      echo "⚠ Пропущено: шаблон не распознан: '$album_field'"
    fi

  done

  # После обработки всех файлов в папке
  if [[ $total_seconds -gt 0 ]]; then
    # total_minutes=$((total_seconds / 60))
    # total_minutes=$((artist_durations["$artist_group"] / 60))
    total_minutes=$((artist_durations["$first_artist"] / 60))
    hours=$((total_minutes / 60))
    minutes=$((total_minutes % 60))

    # Формат ЧАСМИНУТАМИНУТА
    duration_formatted="$(printf "%d%02d" "$hours" "$minutes")"

    # Новое имя папки
    album_name=$(basename "$album_dir")
    parent_dir=$(dirname "$album_dir")
    new_album_dir="$parent_dir/${duration_formatted} $album_name"

    echo "🚀 Переименовываем '$album_name' -> '$(basename "$new_album_dir")'"
    mv "$album_dir" "$new_album_dir"
  fi

done

# Второй проход — обновляем длительность в именах папок

# Поиск всех переименованных папок с длительностью
declare -A max_durations

# Проходим по всем подпапкам снова и собираем максимальную длительность для каждого артиста
for album_dir in "$base_dir"/*/; do
  album_dir="${album_dir%/}" # убираем слэш на конце
  album_name=$(basename "$album_dir")

  # Проверяем, что папка имеет формат "длительность исполнитель"
  # if [[ $album_name =~ ^([0-9]{3,4})\ (.+) ]]; then
  # Проверяем, что папка имеет формат "длительность исполнитель - альбом (год)" или "длительность исполнитель — альбом"
  # if [[ $album_name =~ ^([0-9]{3,4})[\ -]([^—]+)[\ -](.+)$ ]]; then
  if [[ $album_name =~ ^([0-9]{3,4})[\ -]([^—]+)[\ -]([^ ]+.*)$ ]]; then
    duration=${BASH_REMATCH[1]}
    artist_name="${BASH_REMATCH[2]}"
    album_name="${BASH_REMATCH[3]}" #needs debugging
    year="${BASH_REMATCH[4]}" #needs debugging
    # echo "1. duration: $duration"
    # echo "1. artist_name: $artist_name"
    # echo "1. album name: $album_name"
    # echo "1. year: $year"

    # Приводим имя артиста к нижнему регистру для корректного группирования
    artist_group=$(echo "$artist_name" | tr '[:upper:]' '[:lower:]')

    # Сохраняем максимальную длительность
    [[ -z "${max_durations[$artist_group]}" || $duration -gt ${max_durations[$artist_group]} ]] && max_durations[$artist_group]=$duration
    echo "1. max_durations [$artist_group]: ${max_durations["$artist_group"]}"
  fi
done

# Обновляем названия папок с наибольшей длительностью для каждого исполнителя
for album_dir in "$base_dir"/*/; do
  album_dir="${album_dir%/}"
  album_name=$(basename "$album_dir")

  # if [[ $album_name =~ ^([0-9]{3,4})\ (.+) ]]; then
  # if [[ $album_name =~ ^([0-9]{3,4})[\ -]([^—]+)[\ -](.+)$ ]]; then
  if [[ $album_name =~ ^([0-9]{3,4})[\ -]([^—]+)[\ -]([^ ]+.*)$ ]]; then
    duration=${BASH_REMATCH[1]}
    artist_name="${BASH_REMATCH[2]}"
    album_name="${BASH_REMATCH[3]}" #needs debugging
    year="${BASH_REMATCH[4]}" #needs debugging
    #debug: folder names with - instead of — are not correctly parsed
    artist_group=$(echo "$artist_name" | tr '[:upper:]' '[:lower:]')

    # Если длительность меньше максимальной, обновляем имя папки
    if [[ 10#$duration -lt ${max_durations[$artist_group]} ]]; then
      echo "2. duration: $duration"
      echo "2. artist name: $artist_name"
      echo "2. album name: $album_name" #needs debugging
      echo "2. year: $year" #needs debugging
      new_album_name="${max_durations[$artist_group]} $artist_name $album_name ($year)"
      parent_dir=$(dirname "$album_dir")
      new_album_dir="$parent_dir/$new_album_name"

      echo "🔄 Обновление длительности для '$album_name' -> '$new_album_name'"
      mv "$album_dir" "$new_album_dir"
    fi
  fi
done

# Выводим итоговую сумму длительности по артистам
echo && echo -e "${green}Итоговая длительность по артистам:${nocolor}"
for artist in "${!artist_durations[@]}"; do
  seconds=${artist_durations["$artist"]}
  minutes=$((seconds / 60))
  hours=$((minutes / 60))
  remain_minutes=$((minutes % 60))

  formatted_duration="$(printf "%d:%02d" "$hours" "$remain_minutes")"

  echo "🎤 $artist — $formatted_duration"
done

echo && echo -e "${green}Конец обработки${nocolor}" && echo
