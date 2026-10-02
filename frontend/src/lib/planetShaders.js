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
    // Small neutral grading softens the archive's contrast without recoloring geography.
    float luminance = dot(dayColor, vec3(0.2126, 0.7152, 0.0722));
    dayColor = mix(dayColor, vec3(luminance), 0.07);
    dayColor *= vec3(1.025, 1.01, 0.99) * (0.82 + max(sunlight, 0.0) * 0.3);
    vec3 color = dayColor;
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
