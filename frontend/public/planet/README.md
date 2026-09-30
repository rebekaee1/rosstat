# Earth runtime textures

These assets are satellite-derived Earth textures for the local interactive
planet. They are historical composites with artistic processing, not current
satellite imagery or live weather.

## Source and attribution

The three 4096 × 2048 JPEG files were downloaded unchanged on 2026-09-30 from the
[official Three.js Earth example](https://threejs.org/examples/webgpu_tsl_earth.html).
The [example source](https://github.com/mrdoob/three.js/blob/dev/examples/webgpu_tsl_earth.html)
credits **Solar System Scope** for the Earth textures, resized and merged for
the example. Solar System Scope describes these as adjusted derivatives of NASA
elevation, imagery and Blue Marble data. Do not describe these files as unmodified
NASA originals.

Original texture collection:
<https://www.solarsystemscope.com/textures/>

The collection is distributed under **Creative Commons Attribution 4.0
International**: <https://creativecommons.org/licenses/by/4.0/>. Credit the source
and identify modifications when publishing the assets. The Three.js code license
does not replace the texture attribution requirement.

Suggested visible credit:

> Earth textures: Solar System Scope / INOVE, CC BY 4.0. Adapted by Three.js;
> mobile versions resized for ForecastEconomy.

Link `Solar System Scope` to the collection above and `CC BY 4.0` to the license.
The originals and the derivatives retain the same texture attribution.

Exact source URLs, byte lengths, SHA-256 hashes, dimensions, conversion recipes,
runtime paths and channel meanings are in [source-manifest.json](source-manifest.json).

## Runtime sets

| Asset | Desktop | Mobile |
| --- | --- | --- |
| Surface color | `earth_day_4096.jpg` | `earth_day_2048.webp` |
| Night lights | `earth_night_4096.jpg` | `earth_night_2048.webp` |
| Packed material data | `earth_bump_roughness_clouds_4096.jpg` | `earth_bump_roughness_clouds_1024.webp` |

Desktop transfer: **2,248,543 bytes** for all three textures. Mobile transfer:
**1,136,358 bytes**. These are actual file lengths, excluding HTTP headers and
the JavaScript renderer. Load one set at a time; avoid preloading both sets.

The mobile color maps retain 2048 × 1024 resolution. Their WebP encodings use
Pillow 12.1.1, Lanczos resizing, quality 92 (day), quality 95 (night), method 6.
The mobile packed map uses 1024 × 512 resolution and lossless WebP, method 6.
Its decoded RGB bytes were verified to equal the resized RGB pixels exactly.
Resizing necessarily changes sampling; the lossless encoding adds no additional
channel loss. The downloaded source packed JPEG already contains its author's
JPEG compression.

A lossless 2048 packed derivative was evaluated and discarded because it
increased transfer size to 2.69 MB. The 1024 material map provides a genuinely
smaller mobile set without introducing another lossy compression step.

RGBA8 storage with full mipmaps is approximately 128 MiB for the three desktop
textures and 24 MiB for the mobile set. This is arithmetic from dimensions, not
a browser GPU-memory measurement; actual renderer storage can differ.

## Packed map channels

This layout follows the official Three.js example source:

| Channel | Meaning | Color space |
| --- | --- | --- |
| Day RGB | Surface color | `SRGBColorSpace` |
| Night RGB | City lights | `SRGBColorSpace` |
| Packed R | Bump / elevation | `NoColorSpace` |
| Packed G | Roughness | `NoColorSpace` |
| Packed B | Cloud mask | `NoColorSpace` |

The example calculates cloud strength with `smoothstep(0.2, 1.0, packed.b)`,
roughness from `max(packed.g, step(0.01, cloudsStrength))`, and bump elevation
from `max(packed.r, cloudsStrength)`. This is material detail; bump mapping
changes lighting and does not create actual terrain geometry.

Do not assign sRGB conversion to the packed map or save it through a color
profile conversion. The texture images use a 2:1 equirectangular projection.
Confirm the globe UV orientation against known geographical landmarks before
accepting country overlays; a rotated texture can still look plausible.

## Resilience and verification

All runtime assets are served from this project's own `/planet/` path. Third-party
texture services are needed only when refreshing source files. A first visit
while offline still requires an HTML/SVG country-selection fallback; local URLs
alone do not constitute offline caching.

Verify texture loading and decode errors, unavailable WebGL, context loss and
restoration, background-tab suspension, reduced motion, mobile quality selection,
and the chosen country's alignment with coastlines. A texture failure must not
leave an empty black interaction area. A country list/search must remain usable
without the 3D renderer.

No artificial planet poster has been added: use a deterministic capture of the
actual scene if a spherical loading image is required.
