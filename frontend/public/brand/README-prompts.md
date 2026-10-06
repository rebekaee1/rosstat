# Промпты и происхождение кадров бренда

Растровые кадры бренда сгенерированы моделью изображений через OpenRouter скриптом `scripts/dev/generate-brand-image.py`
(ключ только из `api_key.txt` в корне рабочей папки, вне Git, не печатается). Для каждого нового кадра промпт хранится здесь.
Правило: растр кладётся только в разрешении не ниже 2x от размера показа (принцип владельца 9).

## Стеклянная F: `emblem-f-2x.webp`, `emblem-f-phone.webp` (круг 6, зона B, 06.10.2026)

- Модель: `google/gemini-3-pro-image`, соотношение сторон 1:1, размер 2K (выход 2048x2048; запрос 4K OpenRouter отклонил с 400).
  Использован кадр 2: `python3 scripts/dev/generate-brand-image.py "<промпт>" f2.png google/gemini-3-pro-image 1:1 2K`
  (пятый аргумент размера добавлен в скрипт в этом круге). Всего потрачено 2 кадра (первый, 1024 px, не использован), около 0,28 $.
- Промпт (по-английски, без текста на картинке):

```
A single large capital letter F, a luxurious sculpted crystal object, centered, shown straight-on with a slight three-quarter perspective. The letter is carved from perfectly clear, cold, transparent optical glass with precise faceted bevels, crisp thin white highlights along the edges and subtle cold blue-grey refractions inside. A very thin, delicate gold edge line runs only along the outer rim of the bevels (hairline gold, not thick, not a gold fill). Cool neutral palette: ice white, pale steel blue, graphite shadows; gold only as the hairline. Sharp, mature, high-end product render, floating, no glossy candy look, no cartoon, no bubbles, no sparkles or stars, no lens flare. The entire letter fits fully inside the frame with generous empty margin on all sides. Background: perfectly flat, uniform pure white (#FFFFFF), no gradient, no floor, no shadow on the background, no reflection on the ground. No text other than the single letter F, no logo, no watermark.
```

- Постобработка (PIL, SciPy, `cwebp`): фон найден заливкой от краёв (пиксели с минимумом каналов не ниже 247, связанные с краем),
  альфа сглажена (эрозия 1 px, гаусс 1,1 px), белая кайма по краю заменена ближайшим внутренним цветом, обрезка по рамке объекта.
  Результат 1149x1552 с альфой: `emblem-f-2x.webp` (родное разрешение, около 54 КБ); `emblem-f-phone.webp` — тот же кадр, 888x1200 (около 39 КБ).
- Показ: главная (внутри плиты планеты, высота до 760 px, и рядом с заголовком на телефоне), остальные страницы (фиксированный слой сцены),
  водяной знак подвала и карточки «Что внутри» на /about. Потолок высоты показа 760 px (2x = 1520 px меньше 1552).
- Требование «2400 px по длинной стороне» не выполнено: модель отдаёт максимум 2048 px на кадр, F занимает 1552 из них. Для показа выше 760 px нужен
  новый кадр (4K у модели через OpenRouter не принимается) либо векторная перерисовка.

## Прежние кадры

Тексты промптов `hero-desktop.webp`, `facets.webp`, `light-leak.webp`, `footer-*.webp`, `404-shards.webp`, `ribbon.webp` не сохранены
(см. `docs/design-system.md`, раздел 12); при перегенерации сохранять промпт здесь.
