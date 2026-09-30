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
  uniform sampler2D nightMap;
  uniform sampler2D surfaceMap;
  uniform sampler2D atlasMap;
  uniform vec3 sunDirection;
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
    float dy = texture2D(surfaceMap, vUv + vec2(0.0, surfaceTexel)).r
             - texture2D(surfaceMap, vUv - vec2(0.0, surfaceTexel)).r;
    vec3 terrainNormal = normalize(normal - east * dx * 0.45 - north * dy * 0.45);
    vec3 viewDirection = normalize(cameraPosition - vWorldPosition);
    float sunlight = dot(terrainNormal, sunDirection);
    float dayStrength = smoothstep(-0.12, 0.18, sunlight);
    float clouds = smoothstep(0.2, 1.0, surface.b);
    vec3 dayColor = texture2D(dayMap, vUv).rgb;
    dayColor = mix(dayColor, vec3(0.92, 0.95, 1.0), clouds * 0.88);
    dayColor *= 0.22 + max(sunlight, 0.0) * 1.02;
    float sea = 1.0 - smoothstep(0.08, 0.35, surface.g);
    float reflection = pow(max(dot(reflect(-sunDirection, terrainNormal), viewDirection), 0.0), 65.0);
    dayColor += vec3(0.76, 0.86, 1.0) * reflection * sea * (1.0 - clouds) * 0.55;
    vec3 nightColor = vec3(0.004, 0.012, 0.025)
      + texture2D(nightMap, vUv).rgb * 1.75 * (1.0 - clouds * 0.75);
    vec3 color = mix(nightColor, dayColor, dayStrength);
    float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 3.6);
    color += vec3(0.12, 0.36, 0.7) * rim * (0.12 + dayStrength * 0.35);
    vec4 atlas = texture2D(atlasMap, vUv);
    color = mix(color, atlas.rgb * (0.65 + dayStrength * 0.35), atlas.a);
    gl_FragColor = vec4(color, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

export const ATMOSPHERE_FRAGMENT = `
  uniform vec3 sunDirection;
  varying vec3 vWorldPosition;
  varying vec3 vWorldNormal;
  void main() {
    vec3 normal = normalize(vWorldNormal);
    vec3 viewDirection = normalize(cameraPosition - vWorldPosition);
    float edge = pow(1.0 - abs(dot(normal, viewDirection)), 3.0);
    float day = smoothstep(-0.25, 0.45, dot(normal, sunDirection));
    vec3 color = mix(vec3(0.18, 0.16, 0.4), vec3(0.18, 0.5, 1.0), day);
    gl_FragColor = vec4(color, edge * (0.15 + day * 0.55));
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;
