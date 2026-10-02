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
> resized and cloud channel removed for ForecastEconomy.

Link `Solar System Scope` to the collection above and `CC BY 4.0` to the license.
The originals and the derivatives retain the same texture attribution.

Exact source URLs, byte lengths, SHA-256 hashes, dimensions, conversion recipes,
runtime paths and channel meanings are in [source-manifest.json](source-manifest.json).

## Runtime set and first surface

All devices use one shared set. The real 2048 × 1024 surface appears as soon as
`earth_day_2048.webp` has loaded (**263,130 bytes**). It is not delayed by material
maps or optional geography refinement. A neutral one-pixel material supplies
valid initial shader input.

The day image is already cloud-free; the file itself remains unchanged.
Since 2026-10-02 the shader lightens it at render time: dark blue-led pixels are
treated as water and drawn in a calm light slate tone, land shadows are lifted,
and the limb is shaded neutrally for volume. Lighting stays broad and camera-side,
without clouds, a colored rim, atmosphere halo or synthetic ocean highlights.

After the day surface, `earth_material_cloudless_512_10eb5bd716c9.webp` supplies
bump and retained roughness channels (**90,120 bytes**); its B channel is zero.
This map is optional: an error
keeps the already loaded Earth usable. Browsers reporting `connection.saveData`
receive only the day map. Night lights and the original 4096 maps remain source
assets; the runtime does not request them.

The complete texture transfer is **353,250 bytes**, excluding headers,
JavaScript and atlas geometry. The former desktop and compact sets transferred
2,248,543 and 1,136,358 bytes respectively. The first-surface image is unchanged;
the new material filename includes its content hash to permit safe static caching.

The 512 × 256 material derivative uses Pillow 11.1.0, Lanczos resizing and
lossless WebP (method 6). The original RGB was resized first; R/G were retained
exactly and B was replaced with zero. Decoded R/G bytes were verified to equal
the resized source channels, and every decoded B byte is zero. Resizing changes
sampling; encoding adds no R/G loss or sRGB/profile transformation. The source
JPEG already has compression. The previous cloud-bearing 512 derivative remains
an archived asset and is not requested by the current runtime.

Approximate RGBA8 texture storage with mipmaps is 10.67 MiB for day and 0.67 MiB
for the material. The 2048 × 1024 country atlas and 1024 × 512 selection atlas
use no mipmaps, adding 8 and 2 MiB. The system-font label atlas adds another
8 MiB (2048 × 1024, no mipmaps). The resulting approximately 29.34 MiB is
arithmetic from dimensions, excluding framebuffers and geometry; actual GPU
memory is not measured. Pixel density is capped at 1.5 on desktop, 1.25 on
compact devices and 1 on devices reporting at most 4 GB or explicit data saving.

## Packed map channels

The runtime uses the example's R/G channels with its cloud channel removed:

| Channel | Meaning | Color space |
| --- | --- | --- |
| Day RGB | Surface color | `SRGBColorSpace` |
| Night RGB (archived) | City lights; not rendered | `SRGBColorSpace` |
| Packed R | Bump / elevation | `NoColorSpace` |
| Packed G | Roughness retained; current shader has no specular term | `NoColorSpace` |
| Packed B | Zero | `NoColorSpace` |

The archived original packed map has its cloud mask in B. The current runtime
does not sample it or produce clouds. Bump mapping changes lighting and does not
create actual terrain geometry.

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
