# Правки 4 — рабочий пакет транскрипции

Статус: первичная OpenAI-транскрипция готова.

Исходные видео найдены:

- `/Users/iprofi/проекты cursor/transcribe/НА правки 4_1.mov`
- `/Users/iprofi/проекты cursor/transcribe/НА правки 4_2.mov`
- `/Users/iprofi/проекты cursor/transcribe/НА правки 4_3.mov`

Готовые файлы:

- `audio/na_pravki_4_1.mp3`
- `audio/na_pravki_4_2.mp3`
- `audio/na_pravki_4_3.mp3`
- `audio/chunks/na_pravki_4_3_chunk_*.mp3`
- `transcripts/transcript_full.md` — читаемый транскрипт с глобальными и локальными таймкодами.
- `transcripts/transcript_full.txt`
- `transcripts/transcript_full.srt`
- `transcripts/transcript_full.vtt`
- `transcripts/transcript_segments.json` — машинно-читаемые сегменты.
- `transcripts/metadata.json`

Параметры транскрипции:

- Модель: `gpt-4o-transcribe-diarize`
- Формат: `diarized_json`
- Общая длительность: `43:36`
- Сегментов: `659`
- `НА правки 4_3` разбит на 3 аудио-чанка из-за лимита модели `1400` секунд на один файл.

Следующий этап: по транскрипту выделить правки и нарезать много кадров из видео с привязкой к таймкодам.

Токены и секреты в эту папку не сохранять.
