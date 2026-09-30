import {
  Component, Suspense, useEffect, useMemo, useRef, useState,
} from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  AdditiveBlending, BackSide, CanvasTexture, Color, LinearFilter,
  NoColorSpace, Quaternion, SphereGeometry, SRGBColorSpace,
  TextureLoader, Vector3,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { geoEquirectangular, geoPath } from 'd3-geo';
import {
  bindPlanetCountries, loadPlanetFeatures, lonLatToSphere,
  normalizePlanetCountryCode, pickPlanetCountry, sphereToLonLat,
} from '../lib/planetGeometry';
import { WORLD_FEATURES } from '../lib/worldTopology';
import { useT } from '../i18n';
import {
  ATMOSPHERE_FRAGMENT, PLANET_FRAGMENT, PLANET_VERTEX,
} from '../lib/planetShaders';

const SUN = new Vector3(-0.8, 0.55, 1).normalize();
const DEFAULT_FOCUS = [25, 24];
const MIN_DISTANCE = 1.45;
const MAX_DISTANCE = 4.8;
const INITIAL_DISTANCE = 3.35;

function valueFor(collection, code) {
  return collection instanceof Map ? collection.get(code) : collection?.[code];
}

/** Geography is rendered independently of country coverage in the API. */
function paintAtlas(entries, { mode, valuesByCode, colorModel, selectedCode }) {
  const canvas = document.createElement('canvas');
  canvas.width = 2048;
  canvas.height = 1024;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Cannot render country boundaries');
  const projection = geoEquirectangular()
    .scale(canvas.width / (2 * Math.PI))
    .translate([canvas.width / 2, canvas.height / 2]);
  const path = geoPath(projection, context);
  const selected = normalizePlanetCountryCode(selectedCode);
  for (const entry of entries) {
    context.beginPath();
    path(entry.feature);
    const value = valueFor(valuesByCode, entry.dataCode);
    const hasValue = value != null && value !== '' && Number.isFinite(Number(value));
    if (mode === 'data') {
      context.globalAlpha = hasValue ? 0.72 : 0.12;
      context.fillStyle = hasValue ? colorModel.colorFor(value) : '#7f8c9b';
      context.fill();
    }
    context.globalAlpha = mode === 'data' ? 0.62 : 0.4;
    context.strokeStyle = '#bacbdd';
    context.lineWidth = 0.85;
    context.stroke();
  }
  if (selected) {
    for (const entry of entries.filter((item) => item.code === selected)) {
      context.beginPath();
      path(entry.feature);
      context.globalAlpha = mode === 'data' ? 0.14 : 0.27;
      context.fillStyle = '#eac98b';
      context.fill();
      context.globalAlpha = 1;
      context.strokeStyle = '#ffe1a4';
      context.lineWidth = 2.5;
      context.stroke();
    }
  }
  context.globalAlpha = 1;
  return canvas;
}

/** Owns resources so retries/unmounts release textures, including partial loads. */
function usePlanetTextures(compact, onError) {
  const [textures, setTextures] = useState(null);
  useEffect(() => {
    let active = true;
    const owned = [];
    const loader = new TextureLoader();
    const paths = compact ? [
      '/planet/earth_day_2048.webp',
      '/planet/earth_night_2048.webp',
      '/planet/earth_bump_roughness_clouds_1024.webp',
    ] : [
      '/planet/earth_day_4096.jpg',
      '/planet/earth_night_4096.jpg',
      '/planet/earth_bump_roughness_clouds_4096.jpg',
    ];
    const requests = paths.map((path, index) => loader.loadAsync(path).then((texture) => {
      owned.push(texture);
      if (!active) { texture.dispose(); return texture; }
      texture.colorSpace = index === 2 ? NoColorSpace : SRGBColorSpace;
      texture.anisotropy = compact ? 2 : 4;
      return texture;
    }));
    Promise.all(requests).then(([day, night, surface]) => {
      if (active) setTextures({ day, night, surface });
    }).catch((error) => {
      if (active) onError(error);
    });
    return () => {
      active = false;
      owned.forEach((texture) => texture.dispose());
    };
  }, [compact, onError]);
  return textures;
}

function PlanetControls({ entries, cameraCommand, reducedMotion, defaultScope }) {
  const { camera, gl, invalidate } = useThree();
  const controlsRef = useRef(null);
  const flightRef = useRef(null);
  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    controls.enablePan = false;
    controls.enableDamping = !reducedMotion;
    controls.dampingFactor = 0.12;
    controls.rotateSpeed = 0.55;
    controls.zoomSpeed = 0.75;
    controls.minDistance = MIN_DISTANCE;
    controls.maxDistance = MAX_DISTANCE;
    controls.minPolarAngle = 0.035;
    controls.maxPolarAngle = Math.PI - 0.035;
    controls.addEventListener('change', invalidate);
    const interrupt = () => { flightRef.current = null; invalidate(); };
    controls.addEventListener('start', interrupt);
    controlsRef.current = controls;
    controls.update();
    return () => {
      controls.removeEventListener('change', invalidate);
      controls.removeEventListener('start', interrupt);
      controls.dispose();
      controlsRef.current = null;
    };
  }, [camera, gl, invalidate, reducedMotion]);

  useEffect(() => {
    if (!cameraCommand) return;
    const currentDistance = camera.position.length();
    let target = camera.position.clone();
    if (cameraCommand.type === 'focus') {
      const code = normalizePlanetCountryCode(cameraCommand.countryCode);
      const entry = entries.find((item) => item.code === code);
      if (!entry) return;
      target = new Vector3(...lonLatToSphere(entry.focus, 2.6));
    } else if (cameraCommand.type === 'reset') {
      target = new Vector3(...lonLatToSphere(
        defaultScope === 'europe' ? [15, 47] : DEFAULT_FOCUS,
        INITIAL_DISTANCE,
      ));
    } else {
      const factor = cameraCommand.type === 'zoomIn' ? 0.8 : 1.25;
      target.normalize().multiplyScalar(Math.min(MAX_DISTANCE, Math.max(MIN_DISTANCE, currentDistance * factor)));
    }
    if (reducedMotion) {
      camera.position.copy(target);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.update();
      flightRef.current = null;
    } else {
      const start = camera.position.clone().normalize();
      flightRef.current = {
        start,
        rotation: new Quaternion().setFromUnitVectors(start, target.clone().normalize()),
        fromDistance: currentDistance,
        toDistance: target.length(),
        elapsed: 0,
      };
    }
    invalidate();
  }, [cameraCommand, entries, camera, invalidate, reducedMotion, defaultScope]);

  useFrame((_, delta) => {
    const flight = flightRef.current;
    if (flight) {
      flight.elapsed += Math.min(delta, 0.05);
      const progress = Math.min(1, flight.elapsed / 0.65);
      const ease = 1 - (1 - progress) ** 3;
      const rotation = new Quaternion().slerpQuaternions(new Quaternion(), flight.rotation, ease);
      camera.position.copy(flight.start).applyQuaternion(rotation)
        .multiplyScalar(flight.fromDistance + (flight.toDistance - flight.fromDistance) * ease);
      camera.lookAt(0, 0, 0);
      if (progress === 1) flightRef.current = null;
      invalidate();
    }
    controlsRef.current?.update();
  });
  return null;
}

function Earth({ textures, entries, mode, valuesByCode, colorModel, selectedCode, onHover, onSelect, onReady }) {
  const { invalidate, gl } = useThree();
  const downRef = useRef(null);
  const readyRef = useRef(false);
  const geometry = useMemo(() => {
    const sphere = new SphereGeometry(1, 96, 64);
    // SphereGeometry starts at -X. This aligns its u=0 with longitude ±180°.
    sphere.rotateY(-Math.PI / 2);
    return sphere;
  }, []);
  const atlas = useMemo(() => {
    const texture = new CanvasTexture(paintAtlas(entries, { mode, valuesByCode, colorModel, selectedCode }));
    texture.colorSpace = SRGBColorSpace;
    texture.minFilter = LinearFilter;
    texture.generateMipmaps = false;
    return texture;
  }, [entries, mode, valuesByCode, colorModel, selectedCode]);
  useEffect(() => {
    invalidate();
    return () => atlas.dispose();
  }, [atlas, invalidate]);
  const uniforms = useMemo(() => ({
    dayMap: { value: textures.day },
    nightMap: { value: textures.night },
    surfaceMap: { value: textures.surface },
    atlasMap: { value: atlas },
    sunDirection: { value: SUN },
    surfaceTexel: { value: 1 / textures.surface.image.width },
  }), [textures, atlas]);
  const atmosphereUniforms = useMemo(() => ({ sunDirection: { value: SUN } }), []);
  useEffect(() => () => geometry.dispose(), [geometry]);

  const hit = (event) => pickPlanetCountry(entries, sphereToLonLat(event.point));
  const pointerMove = (event) => {
    if (event.buttons) return;
    const entry = hit(event);
    const code = entry?.country ? entry.dataCode : null;
    gl.domElement.style.setProperty('cursor', code ? 'pointer' : 'grab');
    onHover(code);
  };
  const pointerUp = (event) => {
    const down = downRef.current;
    downRef.current = null;
    if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 6) return;
    const entry = hit(event);
    onSelect(entry?.country ? entry.dataCode : null);
  };
  const selected = selectedCode
    ? entries.find((entry) => entry.code === normalizePlanetCountryCode(selectedCode)) : null;
  const markerPosition = selected ? new Vector3(...lonLatToSphere(selected.focus, 1.013)) : null;
  const markerRotation = markerPosition
    ? new Quaternion().setFromUnitVectors(new Vector3(0, 0, 1), markerPosition.clone().normalize())
    : null;

  return (
    <>
      <mesh
        geometry={geometry}
        onAfterRender={() => {
          if (!readyRef.current) { readyRef.current = true; onReady(); }
        }}
        onPointerDown={(event) => { downRef.current = { x: event.clientX, y: event.clientY }; }}
        onPointerUp={pointerUp}
        onPointerMove={pointerMove}
        onPointerOut={() => { onHover(null); gl.domElement.style.setProperty('cursor', 'grab'); }}
      >
        <shaderMaterial vertexShader={PLANET_VERTEX} fragmentShader={PLANET_FRAGMENT} uniforms={uniforms} />
      </mesh>
      <mesh scale={1.025} raycast={() => null}>
        <sphereGeometry args={[1, 64, 48]} />
        <shaderMaterial
          vertexShader={PLANET_VERTEX}
          fragmentShader={ATMOSPHERE_FRAGMENT}
          uniforms={atmosphereUniforms}
          side={BackSide}
          transparent
          depthWrite={false}
          blending={AdditiveBlending}
        />
      </mesh>
      {selected && (
        <mesh position={markerPosition} quaternion={markerRotation} raycast={() => null}>
          <ringGeometry args={[0.009, 0.014, 32]} />
          <meshBasicMaterial color="#ffe1a4" toneMapped={false} />
        </mesh>
      )}
    </>
  );
}

function SceneContents({ entries, compact, onError, ...props }) {
  const textures = usePlanetTextures(compact, onError);
  return (
    <>
      <PlanetControls entries={entries} {...props} />
      {textures && <Earth textures={textures} entries={entries} {...props} />}
    </>
  );
}

class SceneBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error) { this.props.onError(error); }
  render() { return this.state.failed ? null : this.props.children; }
}

/** Three is a lazy leaf: HTML search/cards and SVG fallback never depend on a GPU. */
export default function PlanetScene({ countries, defaultScope, onError, ...props }) {
  const t = useT();
  const [features, setFeatures] = useState(WORLD_FEATURES);
  const atlasLevel = useRef(0);
  const [compact] = useState(() => window.matchMedia('(max-width: 767px)').matches);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const entries = useMemo(() => bindPlanetCountries(countries, features), [countries, features]);
  useEffect(() => {
    let active = true;
    loadPlanetFeatures('detailed').then((detail) => {
      if (active && detail?.length && atlasLevel.current < 1) {
        atlasLevel.current = 1;
        setFeatures(detail);
      }
    });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!props.selectedCode) return undefined;
    let active = true;
    // Microstates and disconnected territories need the complete atlas when focused.
    loadPlanetFeatures('fine').then((fine) => {
      if (active && fine?.length) {
        atlasLevel.current = 2;
        setFeatures(fine);
      }
    });
    return () => { active = false; };
  }, [props.selectedCode]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(preference.matches);
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);
  const initialPosition = lonLatToSphere(defaultScope === 'europe' ? [15, 47] : DEFAULT_FOCUS, INITIAL_DISTANCE);
  return (
    <SceneBoundary onError={onError}>
      <Canvas
        frameloop="demand"
        dpr={[1, compact ? 1.25 : 1.75]}
        camera={{ position: initialPosition, fov: 40, near: 0.05, far: 20 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
        onCreated={({ gl, scene }) => {
          scene.background = new Color('#040b15');
          gl.domElement.setAttribute('aria-label', t('planet.earth'));
        }}
      >
        <Suspense fallback={null}>
          <ContextLifecycle onError={onError} />
          <SceneContents
            entries={entries}
            compact={compact}
            reducedMotion={reducedMotion}
            defaultScope={defaultScope}
            onError={onError}
            {...props}
          />
        </Suspense>
      </Canvas>
    </SceneBoundary>
  );
}

function ContextLifecycle({ onError }) {
  const { gl } = useThree();
  useEffect(() => {
    const canvas = gl.domElement;
    const lost = (event) => { event.preventDefault(); onError(new Error('WebGL context lost')); };
    canvas.addEventListener('webglcontextlost', lost);
    return () => canvas.removeEventListener('webglcontextlost', lost);
  }, [gl, onError]);
  return null;
}
