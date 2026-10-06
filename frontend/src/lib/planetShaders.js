// Local cloud-free satellite composite; neutral atlas lighting is illustrative.
export const PLANET_VERTEX = `
  varying vec2 vUv;
  varying vec3 vWorldNormal;
  void main() {
    vUv = uv;
    vWorldNormal = normalize(mat3(modelMatrix) * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// highlightMap holds two coverage masks: red = selected country, green = hovered country.
// The outline is derived from the mask on the GPU, so it stays about 1.5 screen pixels thin
// and smooth at any zoom, instead of scaling with the texture.
export const PLANET_FRAGMENT = `
  uniform sampler2D dayMap;
  uniform sampler2D surfaceMap;
  uniform sampler2D atlasMap;
  uniform sampler2D highlightMap;
  uniform float surfaceTexel;
  uniform float dataWash;
  uniform float highlightTexel;
  varying vec2 vUv;
  varying vec3 vWorldNormal;

  // Water is recognised from the image itself (dark and blue-led), so grading works
  // before and without the optional material map.
  float waterOf(vec2 uv) {
    vec3 c = texture2D(dayMap, uv).rgb;
    float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float blueLead = c.b - max(c.r, c.g);
    return smoothstep(0.004, 0.03, blueLead) * (1.0 - smoothstep(0.22, 0.42, lum));
  }

  // Approximate distance, in screen pixels, from the 0.5 crossing of a coverage mask.
  float edgeDistance(float m) {
    return abs(m - 0.5) / max(fwidth(m), 0.0005);
  }

  // sRGB 0..1 to linear light. The argument is always clamped to 0..1 first, so pow() never sees a negative base.
  vec3 srgbToLinear(vec3 c) {
    c = clamp(c, 0.0, 1.0);
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c));
  }

  // Round 6 palette of the data globe, sRGB: ocean #DCE8F3 and land without data #E6E3DC.
  const vec3 OCEAN_SRGB = vec3(0.8627, 0.9098, 0.9529);
  const vec3 LAND_SRGB = vec3(0.9020, 0.8902, 0.8627);
  // Selection and hover: a thin blue light along the border (#2C4A8A, #3558A0), not a frame.
  const vec3 SELECT_SRGB = vec3(0.1725, 0.2902, 0.5412);
  const vec3 HOVER_SRGB = vec3(0.2078, 0.3451, 0.6275);

  // The atlas is stored with premultiplied alpha (filtering stays correct and thin lines never turn black),
  // in sRGB values. Straighten, then decode to linear light.
  vec3 atlasToLinear(vec4 atlas) {
    return srgbToLinear(atlas.rgb / max(atlas.a, 0.004));
  }

  // A light five-tap blur of the selection masks turns the staircase of a magnified texture into a smooth edge.
  vec3 softMask(vec2 uv) {
    vec2 d = vec2(highlightTexel, highlightTexel * 2.0) * 0.8;
    vec3 c = texture2D(highlightMap, uv).rgb * 0.4;
    c += texture2D(highlightMap, uv + vec2(d.x, 0.0)).rgb * 0.15;
    c += texture2D(highlightMap, uv - vec2(d.x, 0.0)).rgb * 0.15;
    c += texture2D(highlightMap, uv + vec2(0.0, d.y)).rgb * 0.15;
    c += texture2D(highlightMap, uv - vec2(0.0, d.y)).rgb * 0.15;
    return c;
  }

  void main() {
    vec3 normal = normalize(vWorldNormal);
    vec3 east = normalize(vec3(normal.z, 0.0001, -normal.x));
    vec3 north = normalize(cross(normal, east));
    float dx = texture2D(surfaceMap, vUv + vec2(surfaceTexel, 0.0)).r
             - texture2D(surfaceMap, vUv - vec2(surfaceTexel, 0.0)).r;
    float dy = texture2D(surfaceMap, vUv + vec2(0.0, surfaceTexel * 2.0)).r
             - texture2D(surfaceMap, vUv - vec2(0.0, surfaceTexel * 2.0)).r;
    vec3 terrainNormal = normalize(normal - east * dx * 0.28 - north * dy * 0.28);
    // A broad camera-side daylight keeps countries readable throughout exploration.
    // This is an illustrative atlas light, not the Earth's current terminator.
    vec3 sunDirection = normalize(normalize(cameraPosition) + vec3(-0.18, 0.24, 0.0));
    float sunlight = dot(terrainNormal, sunDirection);
    vec3 dayColor = texture2D(dayMap, vUv).rgb;
    float luminance = dot(dayColor, vec3(0.2126, 0.7152, 0.0722));
    float water = waterOf(vUv);
    // Land keeps its real terrain; shadows are lifted so countries read on a light page.
    vec3 land = mix(dayColor, vec3(luminance), 0.08);
    // The source composite is flat; a little saturation makes land and forest readable against the sea.
    land = mix(vec3(dot(land, vec3(0.2126, 0.7152, 0.0722))), land, 1.16);
    // Saturation above 1 extrapolates: a texel with a channel near zero (deep forest, dark water at a coast, 0.2 % of the
    // 4096 map) goes NEGATIVE, and pow() of a negative base is undefined (NaN on Metal and ANGLE): that texel drew
    // a hard black speck along the Caucasus, Caspian, Aral and US east coasts (round 6). Clamp before pow().
    land = max(land, vec3(0.0));
    land = pow(land, vec3(0.74)) * vec3(1.04, 1.015, 0.97);
    // A calm sea with depth: open water is a deeper blue, the shelf near the coast is pale turquoise.
    vec3 deepSea = vec3(0.30, 0.50, 0.68);
    vec3 midSea = mix(vec3(0.43, 0.61, 0.73), vec3(0.60, 0.75, 0.84), smoothstep(0.0, 0.06, luminance));
    // Shallow water: a soft pale-turquoise band hugging every coast, so shores glow gently.
    vec2 reach = vec2(4.0 / 2048.0, 4.0 / 1024.0);
    float around = 0.25 * (waterOf(vUv + vec2(reach.x, 0.0)) + waterOf(vUv - vec2(reach.x, 0.0))
                         + waterOf(vUv + vec2(0.0, reach.y)) + waterOf(vUv - vec2(0.0, reach.y)));
    float shallow = clamp((1.0 - around) * 1.5, 0.0, 1.0) * water;
    // A wider ring of the same probe: how far the nearest coast is, for the gradient into open ocean.
    vec2 wide = vec2(22.0 / 2048.0, 22.0 / 1024.0);
    float farWater = 0.25 * (waterOf(vUv + vec2(wide.x, 0.0)) + waterOf(vUv - vec2(wide.x, 0.0))
                      + waterOf(vUv + vec2(0.0, wide.y)) + waterOf(vUv - vec2(0.0, wide.y)));
    vec3 sea = mix(midSea, deepSea, smoothstep(0.55, 1.0, farWater) * 0.9);
    sea = mix(sea, vec3(0.74, 0.88, 0.89), shallow * 0.62);
    vec3 surface = mix(land, sea, water);
    // "Data": the photograph gives way to a calm flat palette (ocean #DCE8F3, land without data #E6E3DC);
    // only a trace of relief stays, so the scale of the country colours reads as one thing.
    float gray = dot(surface, vec3(0.2126, 0.7152, 0.0722));
    vec3 flatLand = srgbToLinear(LAND_SRGB) * clamp(0.97 + (gray - 0.5) * 0.22, 0.86, 1.02);
    vec3 flatSurface = mix(flatLand, srgbToLinear(OCEAN_SRGB), water);
    surface = mix(surface, flatSurface, dataWash);
    surface *= 0.885 + max(sunlight, 0.0) * 0.12;
    // A soft glint of the light on open water gives the ocean a surface (faint in data mode: no gloss).
    vec3 toCamera = normalize(cameraPosition - normal);
    float glint = pow(max(dot(reflect(-sunDirection, normal), toCamera), 0.0), 26.0);
    surface += vec3(0.62, 0.72, 0.80) * glint * (0.30 - 0.22 * dataWash) * water;
    // Limb: a little shade for volume, then a thin veil of pale-blue air along the edge.
    float facing = max(dot(normal, normalize(cameraPosition)), 0.0);
    surface *= mix(0.84, 1.0, smoothstep(0.0, 0.5, facing));
    float rim = pow(max(1.0 - facing, 0.0), 2.6);
    surface = mix(surface, vec3(0.66, 0.80, 0.93), rim * 0.34 * (1.0 - dataWash * 0.45));
    vec3 color = surface;
    vec4 atlas = texture2D(atlasMap, vUv);
    color = color * (1.0 - atlas.a) + atlasToLinear(atlas) * atlas.a;

    // Interaction: a faint blue tint inside the country and a thin blue light on its border.
    vec3 hl = softMask(vUv);
    float insideSelected = smoothstep(0.35, 0.65, hl.r);
    float insideHovered = smoothstep(0.35, 0.65, hl.g) * (1.0 - insideSelected);
    vec3 blueSelected = srgbToLinear(SELECT_SRGB);
    vec3 blueHovered = srgbToLinear(HOVER_SRGB);
    color = mix(color, blueSelected, insideSelected * 0.10);
    color = mix(color, blueHovered, insideHovered * 0.07);
    float dSel = edgeDistance(hl.r);
    float dHov = edgeDistance(hl.g);
    // Edge-ness is 1 on the border and 0 in flat areas, so soft halos never end in a hard step.
    float edgeSel = smoothstep(0.0, 0.3, 2.0 * min(hl.r, 1.0 - hl.r));
    float edgeHov = smoothstep(0.0, 0.3, 2.0 * min(hl.g, 1.0 - hl.g));
    float haloSel = (1.0 - smoothstep(0.7, 3.0, dSel)) * edgeSel * 0.34;
    float haloHov = (1.0 - smoothstep(0.7, 2.4, dHov)) * edgeHov * 0.24;
    color = mix(color, vec3(0.90, 0.95, 1.0), max(haloSel, haloHov));
    float lineHov = 1.0 - smoothstep(0.45, 1.25, dHov);
    color = mix(color, blueHovered, lineHov * edgeHov * 0.8);
    float lineSel = 1.0 - smoothstep(0.55, 1.35, dSel);
    color = mix(color, blueSelected, lineSel * edgeSel);

    gl_FragColor = vec4(color, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

// A thin shell just outside the sphere. It is seen only as a ring around the limb: brightest
// at the surface and fading to nothing outward. The constant 0.26 is the view-angle cosine
// where the limb of the 1.0 sphere meets this 1.035 shell.
export const ATMOSPHERE_VERTEX = `
  varying vec3 vShellNormal;
  varying vec3 vShellView;
  void main() {
    vShellNormal = normalize(normalMatrix * normal);
    vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
    vShellView = normalize(-viewPosition.xyz);
    gl_Position = projectionMatrix * viewPosition;
  }
`;

export const ATMOSPHERE_FRAGMENT = `
  uniform float strength;
  varying vec3 vShellNormal;
  varying vec3 vShellView;
  void main() {
    float t = clamp(-dot(normalize(vShellNormal), normalize(vShellView)) / 0.26, 0.0, 1.0);
    float alpha = pow(t, 1.8) * strength;
    gl_FragColor = vec4(vec3(0.58, 0.76, 0.95), alpha);
    #include <colorspace_fragment>
  }
`;
