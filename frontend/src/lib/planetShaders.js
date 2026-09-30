// Local, archived satellite composites; lighting is illustrative, not live weather.
export const PLANET_VERTEX = `
  varying vec2 vUv;
  varying vec3 vWorldPosition;
  varying vec3 vWorldNormal;
  void main() {
    vUv = uv;
    vWorldPosition = (modelMatrix * vec4(position, 1.0)).xyz;
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
  varying vec3 vWorldPosition;
  varying vec3 vWorldNormal;

  void main() {
    vec3 surface = texture2D(surfaceMap, vUv).rgb;
    vec3 normal = normalize(vWorldNormal);
    vec3 east = normalize(vec3(normal.z, 0.0001, -normal.x));
    vec3 north = normalize(cross(normal, east));
    float dx = texture2D(surfaceMap, vUv + vec2(surfaceTexel, 0.0)).r
             - texture2D(surfaceMap, vUv - vec2(surfaceTexel, 0.0)).r;
    float dy = texture2D(surfaceMap, vUv + vec2(0.0, surfaceTexel * 2.0)).r
             - texture2D(surfaceMap, vUv - vec2(0.0, surfaceTexel * 2.0)).r;
    vec3 terrainNormal = normalize(normal - east * dx * 0.45 - north * dy * 0.45);
    vec3 viewDirection = normalize(cameraPosition - vWorldPosition);
    // A broad camera-side daylight keeps countries readable throughout exploration.
    // This is an illustrative atlas light, not the Earth's current terminator.
    vec3 sunDirection = normalize(normalize(cameraPosition) + vec3(-0.28, 0.38, 0.0));
    float sunlight = dot(terrainNormal, sunDirection);
    float clouds = smoothstep(0.2, 1.0, surface.b);
    vec3 dayColor = texture2D(dayMap, vUv).rgb;
    dayColor = mix(dayColor, vec3(0.92, 0.95, 1.0), clouds * 0.88);
    dayColor *= 0.68 + max(sunlight, 0.0) * 0.44;
    float sea = 1.0 - smoothstep(0.08, 0.35, surface.g);
    dayColor = mix(dayColor, vec3(0.045, 0.2, 0.33), sea * (1.0 - clouds) * 0.18);
    float reflection = pow(max(dot(reflect(-sunDirection, terrainNormal), viewDirection), 0.0), 65.0);
    dayColor += vec3(0.76, 0.86, 1.0) * reflection * sea * (1.0 - clouds) * 0.2;
    vec3 color = dayColor;
    float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 3.6);
    color += vec3(0.2, 0.47, 0.65) * rim * 0.24;
    vec4 atlas = texture2D(atlasMap, vUv);
    color = mix(color, atlas.rgb, atlas.a);
    // Apply interaction last: clouds never hide the chosen country's outline.
    vec4 highlight = texture2D(highlightMap, vUv);
    color = mix(color, highlight.rgb, highlight.a);
    gl_FragColor = vec4(color, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

export const ATMOSPHERE_FRAGMENT = `
  varying vec3 vWorldPosition;
  varying vec3 vWorldNormal;
  void main() {
    vec3 normal = normalize(vWorldNormal);
    vec3 viewDirection = normalize(cameraPosition - vWorldPosition);
    float edge = pow(1.0 - abs(dot(normal, viewDirection)), 3.0);
    vec3 color = vec3(0.28, 0.64, 0.8);
    gl_FragColor = vec4(color, edge * 0.36);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;
