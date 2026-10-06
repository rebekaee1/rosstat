#!/usr/bin/env python3
"""Генерация растрового кадра для бренда через OpenRouter (модель изображений).

Запуск (из корня репозитория):
    python3 scripts/dev/generate-brand-image.py "<описание по-английски, без текста на картинке>" out.png \
        [модель] [соотношение сторон, например 16:9] [размер: 1K, 2K или 4K]

Ключ читается из файла `api_key.txt` в корне рабочей папки проекта (ищется вверх по каталогам от скрипта; путь
можно задать переменной окружения FE_OPENROUTER_KEY_FILE). Файл ключа не входит в Git (.gitignore,
.git/info/exclude); скрипт никогда не печатает и не записывает ключ: сообщения об ошибках очищаются от токенов
`sk-or-...`.

Рядом с картинкой сохраняется `<имя>.prompt.txt` (модель, соотношение сторон, текст описания): без него кадр
нельзя воспроизвести. Картинка на выходе — исходник (PNG); в `frontend/public/brand/` кладётся webp после
обработки (cwebp или PIL) и только в разрешении не ниже 2x от размера показа.
Модель по умолчанию — google/gemini-3.1-flash-image (порядка 0,05–0,07 $ за кадр).
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import sys
import urllib.request

DEFAULT_MODEL = "google/gemini-3.1-flash-image"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def read_key() -> str:
    """Читает ключ из файла; путь можно печатать, содержимое никогда."""
    override = os.environ.get("FE_OPENROUTER_KEY_FILE")
    candidates = [pathlib.Path(override)] if override else []
    here = pathlib.Path(__file__).resolve()
    candidates += [parent / "api_key.txt" for parent in here.parents]
    for path in candidates:
        if path.is_file():
            return path.read_text().strip()
    raise SystemExit("Не найден api_key.txt (корень проекта) и не задан FE_OPENROUTER_KEY_FILE.")


def generate(prompt: str, out: pathlib.Path, model: str, ratio: str | None, size: str | None = None) -> None:
    """Просит у модели одно изображение, пишет PNG и sidecar с описанием."""
    body = {"model": model, "modalities": ["image", "text"], "messages": [{"role": "user", "content": prompt}]}
    config = {}
    if ratio:
        config["aspect_ratio"] = ratio
    if size:
        config["image_size"] = size
    if config:
        body["image_config"] = config
    key = read_key()
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            answer = json.load(response)
    except Exception as error:  # сообщение очищается от токенов
        raise SystemExit("ERROR " + re.sub(r"sk-or-[\w-]+", "KEY", str(error)))
    message = answer["choices"][0]["message"]
    images = message.get("images") or []
    if not images:
        raise SystemExit("NO IMAGE " + json.dumps(message, ensure_ascii=False)[:300])
    data = base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    out.with_suffix(".prompt.txt").write_text(f"model: {model}\nratio: {ratio or '-'}\nsize: {size or '-'}\n\n{prompt}\n")
    cost = answer.get("usage", {}).get("cost")
    print("OK", out, len(data), "bytes", "cost", cost)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    prompt, out = sys.argv[1], pathlib.Path(sys.argv[2])
    model = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MODEL
    ratio = sys.argv[4] if len(sys.argv) > 4 else None
    size = sys.argv[5] if len(sys.argv) > 5 else None
    generate(prompt, out, model, ratio, size)


if __name__ == "__main__":
    main()
