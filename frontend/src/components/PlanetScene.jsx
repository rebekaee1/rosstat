import {
  Component, Suspense, useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  CanvasTexture, DataTexture, LinearFilter, LinearMipmapLinearFilter,
  NoColorSpace, Quaternion, SphereGeometry, SRGBColorSpace,
  TextureLoader, Vector3,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { geoEquirectangular, geoPath } from 'd3-geo';
import {
  bindPlanetCountries, loadPlanetFeatures, lonLatToSphere,
  normalizePlanetCountryCode, pickPlanetCountry, planetNeedsFineFeatures, sphereToLonLat,
} from '../lib/planetGeometry';
import { WORLD_FEATURES } from '../lib/worldTopology';
import {
  beginPlanetPointer, createPlanetPointerState, endPlanetPointer,
  movePlanetPointer, planetFitDistance, planetRenderBudget,
} from '../lib/planetNavigation';
import { useLocale, useT } from '../i18n';
import PlanetLabels from './PlanetLabels';
import {
  PLANET_FRAGMENT, PLANET_VERTEX,
} from '../lib/planetShaders';

const DEFAULT_FOCUS = [25, 24];
const MIN_DISTANCE = 1.45;
const MAX_DISTANCE = 4.8;
// Closer than this the 2048 px day map starts to blur; the 4096 px map is fetched once, on demand.
const DETAIL_DISTANCE = 2.7;
const INITIAL_DISTANCE = 3.35;
const FLIGHT_SECONDS = 0.6;
const INTRO_SECONDS = 1.4;
// The first view arrives with a short turn from the west; it never repeats.
const INTRO_OFFSET = [-42, 8];

function valueFor(collection, code) {
  return collection instanceof Map ? collection.get(code) : collection?.[code];
}

/** Geography is rendered independently of country coverage in the API. */
function paintAtlas(entries, { mode, valuesByCode, colorModel }) {
  const canvas = document.createElement('canvas');
  canvas.width = 2048;
  canvas.height = 1024;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Cannot render country boundaries');
  const projection = geoEquirectangular()
    .scale(canvas.width / (2 * Math.PI))
    .translate([canvas.width / 2, canvas.height / 2]);
  const path = geoPath(projection, context);
  context.lineJoin = 'round';
  for (const entry of entries) {
    context.beginPath();
    path(entry.feature);
    const value = valueFor(valuesByCode, entry.dataCode);
    const hasValue = value != null && value !== '' && Number.isFinite(Number(value));
    if (mode === 'data') {
      context.globalAlpha = hasValue ? 0.68 : 0.12;
      context.fillStyle = hasValue ? colorModel.colorFor(value) : '#7f8c9b';
      context.fill();
    }
    // A paper halo and graphite line preserve borders over any real terrain.
    context.globalAlpha = 0.86;
    context.strokeStyle = '#fffaf0';
    context.lineWidth = 2.8;
    context.stroke();
    context.globalAlpha = mode === 'data' ? 0.72 : 0.82;
    context.strokeStyle = '#202a3c';
    context.lineWidth = 1.15;
    context.stroke();
  }
  context.globalAlpha = 1;
  return canvas;
}

/** Hover/selection update two polygons, without repainting the complete atlas. */
function paintHighlight(entries, selectedCode, hoveredCode) {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 512;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Cannot render country selection');
  const path = geoPath(geoEquirectangular()
    .scale(canvas.width / (2 * Math.PI))
    .translate([canvas.width / 2, canvas.height / 2]), context);
  context.lineJoin = 'round';
  const selected = normalizePlanetCountryCode(selectedCode);
  const hovered = normalizePlanetCountryCode(hoveredCode);
  for (const code of new Set([hovered, selected].filter(Boolean))) {
    const isSelected = code === selected;
    for (const entry of entries.filter((item) => item.code === code)) {
      context.beginPath();
      path(entry.feature);
      context.globalAlpha = isSelected ? 0.18 : 0.1;
      context.fillStyle = '#ad8a48';
      context.fill();
      context.globalAlpha = 0.95;
      context.strokeStyle = '#fffaf0';
      context.lineWidth = isSelected ? 4.1 : 3.1;
      context.stroke();
      context.globalAlpha = 1;
      context.strokeStyle = isSelected ? '#80642f' : '#ad8a48';
      context.lineWidth = isSelected ? 2.3 : 1.7;
      context.stroke();
    }
  }
  context.globalAlpha = 1;
  return canvas;
}

/** Owns resources so retries/unmounts release textures, including partial loads. */
function usePlanetTextures(budget, onError, wantDetail) {
  const [textures, setTextures] = useState(null);
  const detailTexture = useRef(null);
  useEffect(() => {
    let active = true;
    const owned = [];
    const loader = new TextureLoader();
    // A neutral one-pixel material lets the real day image appear independently.
    const neutral = new DataTexture(new Uint8Array([128, 255, 0, 255]), 1, 1);
    neutral.colorSpace = NoColorSpace;
    neutral.needsUpdate = true;
    owned.push(neutral);
    loader.loadAsync('/planet/earth_day_2048.webp').then((day) => {
      owned.push(day);
      if (!active) { day.dispose(); return; }
      day.colorSpace = SRGBColorSpace;
      day.anisotropy = 2;
      setTextures({ day, surface: neutral });
      // Material detail is optional: it never blocks the first credible surface.
      if (!budget.materialDetail) return;
      loader.loadAsync('/planet/earth_material_cloudless_512_10eb5bd716c9.webp').then((surface) => {
        owned.push(surface);
        if (!active) { surface.dispose(); return; }
        surface.colorSpace = NoColorSpace;
        surface.anisotropy = 2;
        setTextures({ day, surface });
      }).catch(() => { /* Keep the real day surface if optional detail is unavailable. */ });
    }).catch((error) => {
      if (active) onError(error);
    });
    return () => {
      active = false;
      owned.forEach((texture) => texture.dispose());
    };
  }, [budget, onError]);
  // Sharper day map, only after the visitor zooms in and only where the device can afford it.
  const hasSurface = Boolean(textures);
  const hasDetail = Boolean(textures?.detail);
  useEffect(() => {
    if (!wantDetail || !budget.materialDetail || !hasSurface || hasDetail) return undefined;
    let active = true;
    new TextureLoader().loadAsync('/planet/earth_day_4096.jpg').then((big) => {
      if (!active) { big.dispose(); return; }
      big.colorSpace = SRGBColorSpace;
      big.anisotropy = 4;
      detailTexture.current = big;
      setTextures((previous) => (previous ? { ...previous, day: big, detail: true } : previous));
    }).catch(() => { /* The 2048 px map stays; detail is optional. */ });
    return () => { active = false; };
  }, [wantDetail, budget, hasSurface, hasDetail]);
  useEffect(() => () => { detailTexture.current?.dispose(); detailTexture.current = null; }, []);
  return textures;
}

function PlanetControls({ entries, cameraCommand, reducedMotion, defaultScope, interactive, touchNavigation, onHover, surfaceReady, onZoomDetail }) {
  const { camera, gl, invalidate, size } = useThree();
  const controlsRef = useRef(null);
  const flightRef = useRef(null);
  const aspect = size.width / size.height;
  // On a narrow phone stage the control column would sit on the sphere; leave it a margin.
  const fitDistance = planetFitDistance({ fov: camera.fov, aspect, padding: aspect < 1 ? 1.2 : 1.08 });
  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    controls.enabled = interactive;
    // Wheel belongs to the page. Only an explicitly active touch mode owns pinch.
    controls.enableZoom = interactive && touchNavigation;
    // OrbitControls.connect() writes 'none'; override it after connecting.
    gl.domElement.style.setProperty('touch-action', interactive ? 'none' : 'pan-y pinch-zoom');
    controls.enablePan = false;
    controls.enableDamping = !reducedMotion;
    controls.dampingFactor = 0.12;
    controls.rotateSpeed = 0.55;
    controls.zoomSpeed = 0.75;
    controls.minDistance = MIN_DISTANCE;
    controls.maxDistance = Math.max(MAX_DISTANCE, fitDistance);
    controls.minPolarAngle = 0.035;
    controls.maxPolarAngle = Math.PI - 0.035;
    const onChange = () => {
      // The closer the camera, the less surface a pixel of drag should cover; otherwise zoomed maps race away.
      controls.rotateSpeed = 0.55 * Math.min(1, Math.max(0.35, (camera.position.length() - 1) / Math.max(1.2, fitDistance - 1)));
      invalidate();
      if (camera.position.length() < DETAIL_DISTANCE) onZoomDetail?.();
    };
    controls.addEventListener('change', onChange);
    const interrupt = () => { flightRef.current = null; onHover(null); invalidate(); };
    controls.addEventListener('start', interrupt);
    controlsRef.current = controls;
    controls.update();
    return () => {
      controls.removeEventListener('change', onChange);
      controls.removeEventListener('start', interrupt);
      controls.dispose();
      controlsRef.current = null;
    };
  }, [camera, gl, invalidate, reducedMotion, interactive, touchNavigation, onHover, fitDistance, onZoomDetail]);

  useEffect(() => {
    if (camera.position.length() < fitDistance) {
      camera.position.normalize().multiplyScalar(fitDistance);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.update();
      invalidate();
    }
  }, [camera, fitDistance, invalidate]);

  useEffect(() => {
    if (!cameraCommand) return;
    onHover(null);
    const currentDistance = camera.position.length();
    let target = camera.position.clone();
    if (cameraCommand.type === 'focus') {
      const code = normalizePlanetCountryCode(cameraCommand.countryCode);
      const entry = entries.find((item) => item.code === code);
      if (!entry) return;
      if (!entry.focus) return;
      target = new Vector3(...lonLatToSphere(entry.focus, Math.max(currentDistance, fitDistance)));
    } else if (cameraCommand.type === 'reset') {
      target = new Vector3(...lonLatToSphere(
        defaultScope === 'europe' ? [15, 47] : DEFAULT_FOCUS,
        Math.max(INITIAL_DISTANCE, fitDistance),
      ));
    } else {
      const factor = cameraCommand.type === 'zoomIn' ? 0.8 : 1.25;
      target.normalize().multiplyScalar(Math.min(Math.max(MAX_DISTANCE, fitDistance), Math.max(MIN_DISTANCE, currentDistance * factor)));
      if (target.length() < DETAIL_DISTANCE) onZoomDetail?.();
    }
    if (reducedMotion || cameraCommand.instant) {
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
        duration: FLIGHT_SECONDS,
      };
    }
    invalidate();
  }, [cameraCommand, entries, camera, invalidate, reducedMotion, defaultScope, fitDistance, onHover, onZoomDetail]);

  const introDone = useRef(false);
  useEffect(() => {
    if (!surfaceReady || introDone.current) return;
    introDone.current = true;
    if (cameraCommand) return;
    // The canvas already opened at the offset view, so the turn starts without a jump.
    const distance = camera.position.length();
    const focus = defaultScope === 'europe' ? [15, 47] : DEFAULT_FOCUS;
    const to = new Vector3(...lonLatToSphere(focus, distance));
    if (reducedMotion) {
      camera.position.copy(to);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.update();
      invalidate();
      return;
    }
    const start = camera.position.clone().normalize();
    flightRef.current = {
      start,
      rotation: new Quaternion().setFromUnitVectors(start, to.clone().normalize()),
      fromDistance: distance,
      toDistance: distance,
      elapsed: 0,
      duration: INTRO_SECONDS,
    };
    invalidate();
    // Only the first ready surface starts the turn; later commands own the camera.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [surfaceReady]);

  useFrame((_, delta) => {
    const flight = flightRef.current;
    if (flight) {
      flight.elapsed += Math.min(delta, 0.05);
      const progress = Math.min(1, flight.elapsed / flight.duration);
      // Ease in and out: the globe starts and settles softly instead of snapping.
      const ease = progress < 0.5 ? 4 * progress ** 3 : 1 - ((-2 * progress + 2) ** 3) / 2;
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

function Earth({ textures, budget, entries, locale, mode, valuesByCode, unit, showValues, colorModel, selectedCode, cameraCommand, onHover, onSelect, onReady }) {
  const { invalidate, gl } = useThree();
  const pointerState = useRef(createPlanetPointerState());
  const completedTap = useRef(null);
  const hoverCode = useRef(null);
  const [hover, setHover] = useState(null);
  const hoveredCode = hover && hover.command === cameraCommand ? hover.code : null;
  const readyRef = useRef(false);
  const geometry = useMemo(() => {
    const sphere = new SphereGeometry(1, ...budget.sphereSegments);
    // SphereGeometry starts at -X. This aligns its u=0 with longitude ±180°.
    sphere.rotateY(-Math.PI / 2);
    return sphere;
  }, [budget]);
  const atlas = useMemo(() => {
    const texture = new CanvasTexture(paintAtlas(entries, { mode, valuesByCode, colorModel }));
    texture.colorSpace = SRGBColorSpace;
    // Mipmaps: thin border lines otherwise sparkle when the sphere is minified on a phone.
    texture.minFilter = LinearMipmapLinearFilter;
    texture.generateMipmaps = true;
    texture.anisotropy = 4;
    return texture;
  }, [entries, mode, valuesByCode, colorModel]);
  const highlight = useMemo(() => {
    const texture = new CanvasTexture(paintHighlight(entries, selectedCode, hoveredCode));
    texture.colorSpace = SRGBColorSpace;
    texture.minFilter = LinearFilter;
    texture.generateMipmaps = false;
    return texture;
  }, [entries, selectedCode, hoveredCode]);
  useEffect(() => {
    invalidate();
    return () => atlas.dispose();
  }, [atlas, invalidate]);
  useEffect(() => {
    invalidate();
    return () => highlight.dispose();
  }, [highlight, invalidate]);
  const uniforms = useMemo(() => ({
    dayMap: { value: textures.day },
    surfaceMap: { value: textures.surface },
    atlasMap: { value: atlas },
    highlightMap: { value: highlight },
    surfaceTexel: { value: 1 / textures.surface.image.width },
  }), [textures, atlas, highlight]);
  useEffect(() => () => geometry.dispose(), [geometry]);

  useEffect(() => {
    const canvas = gl.domElement;
    const ownerDocument = canvas.ownerDocument;
    const down = (event) => {
      completedTap.current = null;
      pointerState.current = beginPlanetPointer(pointerState.current, event);
      hoverCode.current = null;
      setHover(null);
      onHover(null);
    };
    const additionalDown = (event) => {
      const state = pointerState.current;
      // Only a gesture started on this canvas owns outside contacts.
      if (!state.activeIds.length || state.activeIds.includes(event.pointerId)) return;
      completedTap.current = null;
      pointerState.current = beginPlanetPointer(state, event);
      hoverCode.current = null;
      setHover(null);
      onHover(null);
    };
    const move = (event) => {
      pointerState.current = movePlanetPointer(pointerState.current, event);
    };
    const end = (event) => {
      const result = endPlanetPointer(pointerState.current, event, event.type === 'pointercancel');
      pointerState.current = result.state;
      completedTap.current = result.tap ? { pointerId: event.pointerId, timeStamp: event.timeStamp } : null;
    };
    canvas.addEventListener('pointerdown', down, true);
    ownerDocument.addEventListener('pointerdown', additionalDown, true);
    ownerDocument.addEventListener('pointermove', move, true);
    ownerDocument.addEventListener('pointerup', end, true);
    ownerDocument.addEventListener('pointercancel', end, true);
    return () => {
      canvas.removeEventListener('pointerdown', down, true);
      ownerDocument.removeEventListener('pointerdown', additionalDown, true);
      ownerDocument.removeEventListener('pointermove', move, true);
      ownerDocument.removeEventListener('pointerup', end, true);
      ownerDocument.removeEventListener('pointercancel', end, true);
      pointerState.current = createPlanetPointerState();
      completedTap.current = null;
    };
  }, [gl, onHover]);

  useEffect(() => {
    hoverCode.current = null;
    onHover(null);
    gl.domElement.style.setProperty('cursor', 'grab');
  }, [cameraCommand, gl, onHover]);

  const hit = (event) => pickPlanetCountry(entries, sphereToLonLat(event.point));
  const pointerMove = (event) => {
    if (event.buttons || event.pointerType === 'touch') return;
    const entry = hit(event);
    const code = entry?.country ? entry.dataCode : null;
    const key = code || (entry ? 'geo:' + entry.id : null);
    gl.domElement.style.setProperty('cursor', code ? 'pointer' : 'grab');
    if (hoverCode.current !== key) {
      hoverCode.current = key;
      setHover({ code, command: cameraCommand });
      // Land without a catalog route still names itself instead of ignoring the pointer.
      onHover(code, code ? null : entry?.name || null);
    }
  };
  const pointerUp = (event) => {
    const tap = completedTap.current;
    completedTap.current = null;
    if (!tap || tap.pointerId !== event.pointerId || tap.timeStamp !== event.nativeEvent.timeStamp) return;
    const entry = hit(event);
    onSelect(entry?.country ? entry.dataCode : null);
  };
  const selected = selectedCode
    ? entries.find((entry) => entry.code === normalizePlanetCountryCode(selectedCode)) : null;
  const markerPosition = selected?.focus ? new Vector3(...lonLatToSphere(selected.focus, 1.013)) : null;
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
        onPointerUp={pointerUp}
        onPointerMove={pointerMove}
        onPointerOut={() => { hoverCode.current = null; setHover(null); onHover(null); gl.domElement.style.setProperty('cursor', 'grab'); }}
      >
        <shaderMaterial vertexShader={PLANET_VERTEX} fragmentShader={PLANET_FRAGMENT} uniforms={uniforms} />
      </mesh>
      <PlanetLabels entries={entries} locale={locale} valuesByCode={valuesByCode} unit={unit} showValues={showValues} selectedCode={selectedCode}
        hoverCode={hoveredCode} compact={budget.sphereSegments[0] <= 64} />
      {markerPosition && (
        <mesh position={markerPosition} quaternion={markerRotation} raycast={() => null}>
          <ringGeometry args={[0.01, 0.016, 32]} />
          <meshBasicMaterial color="#fffaf0" toneMapped={false} />
          <mesh position={[0, 0, 0.001]} raycast={() => null}>
            <ringGeometry args={[0.0115, 0.014, 32]} />
            <meshBasicMaterial color="#ad8a48" toneMapped={false} />
          </mesh>
        </mesh>
      )}
    </>
  );
}

function SceneContents({ entries, budget, onError, ...props }) {
  const [wantDetail, setWantDetail] = useState(false);
  const requestDetail = useCallback(() => setWantDetail(true), []);
  const textures = usePlanetTextures(budget, onError, wantDetail);
  return (
    <>
      <PlanetControls entries={entries} onZoomDetail={requestDetail} {...props} />
      {textures && <Earth textures={textures} budget={budget} entries={entries} {...props} />}
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
export default function PlanetScene({ countries, defaultScope, onError, onReady, interactive = true, touchNavigation = false, ...props }) {
  const t = useT();
  const { locale } = useLocale();
  const [features, setFeatures] = useState(WORLD_FEATURES);
  const atlasLevel = useRef(0);
  const [surfaceReady, setSurfaceReady] = useState(false);
  const [budget] = useState(() => planetRenderBudget({
    compact: window.matchMedia('(max-width: 767px), (pointer: coarse)').matches,
    deviceMemory: navigator.deviceMemory,
    saveData: navigator.connection?.saveData,
  }));
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const entries = useMemo(() => bindPlanetCountries(countries, features, { locale }), [countries, features, locale]);
  const handleReady = useCallback(() => {
    setSurfaceReady(true);
    onReady();
  }, [onReady]);
  useEffect(() => {
    if (!surfaceReady || !budget.materialDetail) return undefined;
    let active = true;
    const refine = () => loadPlanetFeatures('detailed').then((detail) => {
        if (active && detail?.length && atlasLevel.current < 1) {
          atlasLevel.current = 1;
          setFeatures(detail);
        }
      });
    // Draw the base atlas first; refinement must not compete with the day map.
    const idle = window.requestIdleCallback?.(refine, { timeout: 1500 });
    const timer = idle == null ? window.setTimeout(refine, 200) : null;
    return () => {
      active = false;
      if (idle != null) window.cancelIdleCallback(idle);
      if (timer != null) window.clearTimeout(timer);
    };
  }, [surfaceReady, budget]);
  useEffect(() => {
    if (atlasLevel.current >= 2 || !planetNeedsFineFeatures(entries, props.selectedCode)) return undefined;
    let active = true;
    // Microstates and disconnected territories need the complete atlas when focused.
    loadPlanetFeatures('fine').then((fine) => {
      if (active && fine?.length) {
        atlasLevel.current = 2;
        setFeatures(fine);
      }
    });
    return () => { active = false; };
  }, [entries, props.selectedCode]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(preference.matches);
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);
  const [introOffset] = useState(() => (reducedMotion ? [0, 0] : INTRO_OFFSET));
  const initialFocus = defaultScope === 'europe' ? [15, 47] : DEFAULT_FOCUS;
  const initialPosition = lonLatToSphere([initialFocus[0] + introOffset[0], initialFocus[1] + introOffset[1]], INITIAL_DISTANCE);
  return (
    <SceneBoundary onError={onError}>
      <Canvas
        frameloop="demand"
        dpr={[1, budget.maxDpr]}
        camera={{ position: initialPosition, fov: 40, near: 0.05, far: 20 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x000000, 0);
          gl.domElement.setAttribute('aria-label', t('planet.earth'));
        }}
      >
        <Suspense fallback={null}>
          <ContextLifecycle onError={onError} />
          <SceneContents
            entries={entries}
            locale={locale}
            budget={budget}
            reducedMotion={reducedMotion}
            defaultScope={defaultScope}
            onError={onError}
            interactive={interactive}
            touchNavigation={touchNavigation}
            surfaceReady={surfaceReady}
            {...props}
            onReady={handleReady}
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
