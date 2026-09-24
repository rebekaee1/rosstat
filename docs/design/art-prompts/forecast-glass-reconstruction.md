# Forecast glass — реконструкция промпта

**Это реконструкция для будущих вариантов, не исходный промпт.** Текст,
которым было создано старое утверждённое изображение `forecast-glass`, не
сохранился. Автор генерации, точная версия модели, seed и параметры исходного
запуска здесь не устанавливаются. Ниже зафиксировано наблюдаемое направление
по существующему изображению; совпадение пикселей при повторной генерации не
обещается.

Дата реконструкции: 2026-09-24.

Референс: `frontend/public/art/quicklinks/forecast-glass.webp`, 960×640.
SHA-256: `5d556119520e53221bcca38b970ef348cbe2e220bf56d39ce3b3bb6f033e8320`.
Для будущих вариантов прикладывать этот файл как визуальный референс и
сохранять новый промпт, модель, параметры и результат отдельно от оригинала.

## Reconstructed prompt

> Create one premium editorial brand sculpture for ForecastEconomy. Use the
> attached approved image as the visual reference for material, silhouette,
> lighting and composition. The subject is a single freestanding F-shaped
> sculpture made entirely from thick, clear optical glass: one gently curved,
> slightly leaning vertical stem and two broad horizontal arms with smoothly
> rounded, polished edges. The glass has substantial physical thickness,
> believable refraction, clear internal light paths and restrained reflections.
> It should feel fluid but precise, graceful and architectural, like a museum
> product photograph, rather than melted plastic or chrome.
>
> Landscape 3:2 composition. Place the sculpture in the right half of the
> frame, leaving the left 40–45 percent quiet and nearly empty for later
> typography. Show the complete main silhouette with comfortable breathing
> room. Use a matte pearl studio floor and continuous softly graduated pearl
> backdrop, based on #EEF0F4. Add subtle champagne #AD8A48 caustics and fine
> ice-blue #CAD8E5 edge reflections, with controlled ink #202A3C reflections
> inside the glass. Keep the scene bright, restrained and mostly neutral.
> Soft broad daylight from the upper left; a natural contact shadow and a
> delicate reflection on the floor. A close three-quarter product view with
> sharp glass edges and a softly receding background.
>
> No words, captions, numbers, economic values, charts, axes, extra letters,
> additional logos or watermark. The F-shaped sculpture is the only symbol.
> No neon, rainbow hologram, dark background, metallic finish, cartoon styling
> or busy scenery. This is decorative artwork only; all factual data and
> readable branding will be typeset separately in code.

## Границы вариаций

- Сохранять палитру, оптическое стекло, свободное поле слева и узнаваемую
  F-форму. Менять по одному параметру за вариант: угол, мягкость света либо
  степень изгиба.
- Не дорисовывать экономические значения в иллюстрации. Числа, графики,
  единицы, подписи и домен принадлежат программному renderer.
- Для предметных иллюстраций других тем использовать их собственные
  сохранённые промпты. Эта реконструкция относится только к `forecast-glass`.
