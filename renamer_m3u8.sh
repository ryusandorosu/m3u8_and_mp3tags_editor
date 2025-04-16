#!/bin/bash

# Указываем путь к директории, где находятся файлы .m3u8
DIRECTORY="/mnt/d/Downloads"

# Проверяем, что директория существует
if [[ ! -d "$DIRECTORY" ]]; then
  echo "Directory $DIRECTORY does not exist."
  exit 1
fi

# Обрабатываем каждый файл с расширением .m3u8 в указанной директории
for file in "$DIRECTORY"/*.m3u8; do
  # Проверяем, существует ли файл (на случай, если файлов нет)
  if [[ ! -f "$file" ]]; then
    echo "No .m3u8 files found in $DIRECTORY."
    exit 0
  fi

  # Создаем временный файл для хранения изменений
  temp_file=$(mktemp)

  # Редактируем файл: удаляем строки и выполняем замены
  sed -e '/#EXTM3U/d' \
      -e '/#EXTINF:/d' \
      -e 's|\\|/|g' \
      -e 's|D:/Music vk x4/|primary/Music/|g' \
      -e 's|D:/Music vk x4 ambcl/|primary/Music/Ambient, Classical, Drone/|g' \
      "$file" > "$temp_file"

  # Перемещаем временный файл на место оригинального
  mv "$temp_file" "$file"
  
  echo "Processed: $file"
done

echo "All .m3u8 files in $DIRECTORY have been updated."
