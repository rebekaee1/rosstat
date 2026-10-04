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

export const PLANET_FRAGMENT = `
  uniform sampler2D dayMap;
  uniform sampler2D surfaceMap;
  uniform sampler2D atlasMap;
  uniform sampler2D highlightMap;
  uniform float surfaceTexel;
  uniform float dataWash;
  varying vec2 vUv;
  varying vec3 vWorldNormal;

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
    // Water is recognised from the image itself (dark and blue-led), so the light
    // grading works before and without the optional material map.
    float blueLead = dayColor.b - max(dayColor.r, dayColor.g);
    float water = smoothstep(0.004, 0.03, blueLead) * (1.0 - smoothstep(0.22, 0.42, luminance));
    // Land keeps its real terrain; shadows are lifted so countries read on a light page.
    vec3 land = mix(dayColor, vec3(luminance), 0.08);
    // The source composite is flat; a little saturation makes land and forest readable against the sea.
    land = mix(vec3(dot(land, vec3(0.2126, 0.7152, 0.0722))), land, 1.16);
    land = pow(land, vec3(0.74)) * vec3(1.04, 1.015, 0.97);
    // A calm porcelain sea replaces the archive's near-black navy. Depth survives
    // as a small tonal variation; no highlight, halo or coloured rim is added.
    vec3 sea = mix(vec3(0.43, 0.61, 0.73), vec3(0.60, 0.75, 0.84), smoothstep(0.0, 0.06, luminance));
    vec3 surface = mix(land, sea, water);
    surface *= 0.9 + max(sunlight, 0.0) * 0.16;
    // «Данные»: подложка уходит в спокойный светлый тон, чтобы раскраска стран читалась как шкала,
    // а не терялась в бежевой пустыне. Рельеф остаётся лёгкой тенью.
    float gray = dot(surface, vec3(0.2126, 0.7152, 0.0722));
    vec3 pale = vec3(0.86, 0.885, 0.91) + (gray - 0.5) * 0.14;
    surface = mix(surface, mix(pale, sea, water), dataWash * 0.82);
    // Neutral limb shading gives the sphere volume without tinting its edge.
    float facing = max(dot(normal, normalize(cameraPosition)), 0.0);
    surface *= mix(0.72, 1.0, smoothstep(0.0, 0.55, facing));
    vec3 color = surface;
    vec4 atlas = texture2D(atlasMap, vUv);
    color = mix(color, atlas.rgb, atlas.a);
    // Interaction remains a separate lightweight layer over the natural surface.
    vec4 highlight = texture2D(highlightMap, vUv);
    color = mix(color, highlight.rgb, highlight.a);
    gl_FragColor = vec4(color, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;
