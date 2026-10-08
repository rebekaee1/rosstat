import {
  Component, Suspense, useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  BackSide, CanvasTexture, DataTexture, LinearMipmapLinearFilter,
  NoColorSpace, Quaternion, SphereGeometry, SRGBColorSpace,
  TextureLoader, Vector3,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { geoArea, geoEquirectangular, geoPath } from 'd3-geo';
import {
  bindPlanetCountries, loadPlanetFeatures, lonLatToSphere,
  normalizePlanetCountryCode, pickPlanetCountry, planetNeedsFineFeatures, sphereToLonLat,
} from '../lib/planetGeometry';
import { outlineRings, substantialPolygons } from '../lib/planetAtlas';
import {
  bestStartFocus, dataVectors, focusDistance, hasVisibleData, liftedFocus, zoomedDistance,
} from '../lib/planetView';
import { WORLD_FEATURES } from '../lib/worldTopology';
import { WORLD_NO_DATA } from '../lib/worldMapColors';
import {
  beginPlanetPointer, createPlanetPointerState, endPlanetPointer,
  movePlanetPointer, planetFitDistance, planetRenderBudget,
} from '../lib/planetNavigation';
import { useLocale, useT } from '../i18n';
import PlanetLabels from './PlanetLabels';
import {
  ATMOSPHERE_FRAGMENT, ATMOSPHERE_VERTEX, PLANET_FRAGMENT, PLANET_VERTEX,
} from '../lib/planetShaders';

// Запасная стартовая сторона (Атлантика: Америка, Европа, Африка); обычно её заменяет bestStartFocus по данным.
// Запасной стартовый вид, пока данных ещё нет: Европа и Азия (там больше всего окрашенных стран), а не пустая Атлантика с Африкой.
const DEFAULT_FOCUS = [30, 38];
const MIN_DISTANCE = 1.45;
const MAX_DISTANCE = 4.8;
// Closer than this the 2048 px day map starts to blur; the 4096 px map is fetched once, on demand.
const DETAIL_DISTANCE = 2.7;
// Ближе этого расстояния подгружается подробный атлас 10m (линии границ без «лесенки»).
const DEEP_DISTANCE = 2.15;
// Ближе этого расстояния на шаре подписываются страны, а не только выбранная.
const LABEL_DISTANCE = 2.9;
// Самовращение до первого касания: градусов в секунду и кадров в секунду (30: экономим батарею).
const SPIN_DEGREES_PER_SECOND = 4.5;
const SPIN_TICK_MS = 33;
const DOUBLE_TAP_MS = 320;
const Y_AXIS = new Vector3(0, 1, 0);
const INITIAL_DISTANCE = 3.35;
const FLIGHT_SECONDS = 0.6;
const INTRO_SECONDS = 1.4;
// The first view arrives with a short turn from the west; it never repeats.
const INTRO_OFFSET = [-42, 8];

function valueFor(collection, code) {
  return collection instanceof Map ? collection.get(code) : collection?.[code];
}

const ATLAS_WIDTH = 2048;
const ATLAS_DETAIL_WIDTH = 4096;
// A ring smaller than this (in atlas pixels at 2048 wide, about 1.4 degrees) gets a fill but no outline:
// the border line is as wide as such a ring, so it would be a black speck (Greenland fjord islets,
// Azov and Caspian islands, lakes, atolls). The threshold is in degrees, so it holds for the 4096 atlas too.
const MIN_OUTLINE_SPAN = 8;
// Land smaller than this (about 0.7 degrees, 4 px at 2048) is not painted either: in the 50m atlas the Aegean, the Adriatic,
// the US east coast and the Azov and Caspian seas hold swarms of rings a pixel wide, and each of them is a speck of dust on the
// sphere (round 5). The largest part of every country is always painted, so Malta or Singapore stay.
const MIN_FILL_SPAN_DEGREES = 0.7;

/** Outline only the rings big enough to carry it; the fill keeps every tiny island. */
function tracePath(path, context, geometry, minSpanDegrees) {
  context.beginPath();
  for (const ring of outlineRings(geometry, minSpanDegrees)) path({ type: 'LineString', coordinates: ring });
}

// Страны без данных (круг 6): нейтральная суша #E6E3DC без штриховки; океан в шейдере #DCE8F3, шкала значений — лёд → синий.
const NO_DATA_FILL = WORLD_NO_DATA;

/** Geography is rendered independently of country coverage in the API. */
function paintAtlas(entries, { mode, valuesByCode, colorModel, width = ATLAS_WIDTH }) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = width / 2;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Cannot render country boundaries');
  const scale = width / ATLAS_WIDTH;
  const projection = geoEquirectangular()
    .scale(canvas.width / (2 * Math.PI))
    .translate([canvas.width / 2, canvas.height / 2]);
  const path = geoPath(projection, context);
  const minSpanDegrees = MIN_OUTLINE_SPAN * 360 / ATLAS_WIDTH;
  context.lineJoin = 'round';
  context.lineCap = 'round';
  for (const entry of entries) {
    if (mode === 'data') {
      context.beginPath();
      path(substantialPolygons(entry.feature.geometry, MIN_FILL_SPAN_DEGREES));
      const value = valueFor(valuesByCode, entry.dataCode);
      const hasValue = value != null && value !== '' && Number.isFinite(Number(value));
      // Суша закрашена почти непрозрачно: шкала читается с первого взгляда, а не «просвечивает» рельефом.
      // Круг 10 (К1): золота нет, страна на первом месте — просто самая тёмная ступень шкалы.
      context.globalAlpha = 0.92;
      context.fillStyle = !hasValue ? NO_DATA_FILL : colorModel.colorFor(value);
      context.fill();
    }
    // Borders are a hairline: a pale veil keeps them visible over dark colours, a thin graphite line draws them.
    tracePath(path, context, entry.feature.geometry, minSpanDegrees);
    context.globalAlpha = 0.36;
    context.strokeStyle = '#ffffff';
    context.lineWidth = 1.7 * scale;
    context.stroke();
    context.globalAlpha = mode === 'data' ? 0.34 : 0.46;
    context.strokeStyle = '#202a3c';
    context.lineWidth = 0.7 * scale;
    context.stroke();
  }
  context.globalAlpha = 1;
  return canvas;
}

/**
 * Selection and hover are two coverage masks (red = selected, green = hovered), not drawn lines:
 * the shader turns the mask edge into a thin, smooth outline of constant screen width.
 */
function paintHighlight(canvas, entries, selectedCode, hoveredCode) {
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Cannot render country selection');
  const path = geoPath(geoEquirectangular()
    .scale(canvas.width / (2 * Math.PI))
    .translate([canvas.width / 2, canvas.height / 2]), context);
  context.globalCompositeOperation = 'source-over';
  context.globalAlpha = 1;
  context.fillStyle = '#000';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.globalCompositeOperation = 'lighter';
  const selected = normalizePlanetCountryCode(selectedCode);
  const hovered = normalizePlanetCountryCode(hoveredCode);
  const layers = [[hovered, 'rgb(0,255,0)'], [selected, 'rgb(255,0,0)']];
  for (const [code, color] of layers) {
    if (!code) continue;
    context.fillStyle = color;
    for (const entry of entries) {
      if (entry.code !== code) continue;
      context.beginPath();
      path(entry.feature);
      context.fill();
    }
  }
  context.globalCompositeOperation = 'source-over';
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
      day.anisotropy = 8;
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
      big.anisotropy = 8;
      detailTexture.current = big;
      setTextures((previous) => (previous ? { ...previous, day: big, detail: true } : previous));
    }).catch(() => { /* The 2048 px map stays; detail is optional. */ });
    return () => { active = false; };
  }, [wantDetail, budget, hasSurface, hasDetail]);
  useEffect(() => () => { detailTexture.current?.dispose(); detailTexture.current = null; }, []);
  return textures;
}

function PlanetControls({
  entries, valuesByCode, cameraCommand, reducedMotion, defaultScope, interactive, touchNavigation, onHover,
  surfaceReady, onZoomDetail, onZoomDeep, autoRotate, onInteract, onView, onOcean, onZoomState, controlApi, homeFocus,
}) {
  const { camera, gl, invalidate, size } = useThree();
  const controlsRef = useRef(null);
  const flightRef = useRef(null);
  const draggingRef = useRef(false);
  const hoveredByMouse = useRef(false);
  const [visible, setVisible] = useState(true);
  const aspect = size.width / size.height;
  // The sphere should fill the stage: overlays (buttons, card sheet) sit on top of it, not beside it.
  const fitDistance = planetFitDistance({ fov: camera.fov, aspect, padding: size.width < 520 ? 1.1 : aspect < 1 ? 1.14 : 1.08 });
  const maxDistance = Math.max(MAX_DISTANCE, fitDistance);
  const vectors = useMemo(() => dataVectors(entries, valuesByCode), [entries, valuesByCode]);
  // Callbacks and data change identity often; the long-lived listeners below read the latest through this ref.
  const live = useRef({});
  live.current = {
    vectors, onView, onOcean, onZoomState, onInteract, onZoomDetail, onZoomDeep, onHover, fitDistance, maxDistance,
  };
  const oceanRef = useRef(null);
  const zoomedRef = useRef(null);

  const startFlight = useCallback((target, duration = FLIGHT_SECONDS) => {
    const controls = controlsRef.current;
    if (reducedMotion || duration <= 0) {
      camera.position.copy(target);
      camera.lookAt(0, 0, 0);
      controls?.update();
      flightRef.current = null;
    } else {
      const currentDistance = camera.position.length();
      const start = camera.position.clone().normalize();
      flightRef.current = {
        start,
        rotation: new Quaternion().setFromUnitVectors(start, target.clone().normalize()),
        fromDistance: currentDistance,
        toDistance: target.length(),
        elapsed: 0,
        duration,
      };
    }
    invalidate();
  }, [camera, invalidate, reducedMotion]);

  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    const canvas = gl.domElement;
    // На телефоне шар вращается сразу: горизонтальный свайп поворачивает его, а вертикальный остаётся прокруткой
    // страницы (touch-action: pan-y). Свободное вращение по двум осям включается кнопкой «Свободное вращение».
    const spinOnly = touchNavigation && !interactive;
    controls.enabled = true;
    // Щипок на телефоне всегда принадлежит шару; колесо мыши на компьютере остаётся за страницей.
    controls.enableZoom = touchNavigation;
    controls.zoomSpeed = 0.6;
    // OrbitControls.connect() writes 'none'; override it after connecting. Без pinch-zoom: щипок масштабирует
    // планету, а не всю страницу браузера.
    canvas.style.setProperty('touch-action', interactive ? 'none' : 'pan-y');
    controls.enablePan = false;
    controls.enableDamping = !reducedMotion;
    controls.dampingFactor = 0.12;
    controls.rotateSpeed = 0.55;
    controls.minDistance = MIN_DISTANCE;
    controls.maxDistance = live.current.maxDistance;
    controls.minPolarAngle = 0.035;
    controls.maxPolarAngle = Math.PI - 0.035;
    // Наклон фиксируется только на время пальца: вертикальное движение не крутит шар,
    // а программный перелёт к стране по-прежнему может менять широту.
    const lockTilt = () => {
      if (!spinOnly) return;
      const tilt = controls.getPolarAngle();
      controls.minPolarAngle = tilt;
      controls.maxPolarAngle = tilt;
    };
    const unlockTilt = () => {
      controls.minPolarAngle = 0.035;
      controls.maxPolarAngle = Math.PI - 0.035;
    };
    const report = () => {
      const distance = camera.position.length();
      const lonLat = sphereToLonLat(camera.position);
      live.current.onView?.({ lon: lonLat?.[0] ?? 0, lat: lonLat?.[1] ?? 0, distance });
      const zoomed = distance < LABEL_DISTANCE;
      if (zoomedRef.current !== zoomed) { zoomedRef.current = zoomed; live.current.onZoomState?.(zoomed); }
      const water = !hasVisibleData(live.current.vectors, [camera.position.x, camera.position.y, camera.position.z]);
      if (oceanRef.current !== water) { oceanRef.current = water; live.current.onOcean?.(water); }
    };
    const onChange = () => {
      // The closer the camera, the less surface a pixel of drag should cover; otherwise zoomed maps race away.
      const fit = live.current.fitDistance;
      controls.rotateSpeed = 0.55 * Math.min(1, Math.max(0.35, (camera.position.length() - 1) / Math.max(1.2, fit - 1)));
      invalidate();
      const distance = camera.position.length();
      if (distance < DETAIL_DISTANCE) live.current.onZoomDetail?.();
      if (distance < DEEP_DISTANCE) live.current.onZoomDeep?.();
      report();
    };
    controls.addEventListener('change', onChange);
    const onStart = () => {
      draggingRef.current = true;
      lockTilt();
      flightRef.current = null;
      live.current.onHover(null);
      live.current.onInteract?.();
      invalidate();
    };
    const onEnd = () => { draggingRef.current = false; unlockTilt(); };
    controls.addEventListener('start', onStart);
    controls.addEventListener('end', onEnd);

    // Щипок по шару: Safari присылает свои gesture-события и масштабирует страницу, если их не остановить;
    // Chrome и Firefox на телефонах слушаются touch-action (выше).
    const stopGesture = (event) => event.preventDefault();
    canvas.addEventListener('gesturestart', stopGesture, { passive: false });
    canvas.addEventListener('gesturechange', stopGesture, { passive: false });
    // Страховка для iOS: щипок двумя пальцами по шару не должен масштабировать страницу ни при каких обстоятельствах.
    const stopPinch = (event) => { if (event.touches && event.touches.length > 1) event.preventDefault(); };
    canvas.addEventListener('touchstart', stopPinch, { passive: false });
    canvas.addEventListener('touchmove', stopPinch, { passive: false });
    // Щипок на тачпаде приходит как колесо с зажатым ctrl: он должен масштабировать планету, а не страницу.
    const onWheel = (event) => {
      if (!event.ctrlKey) return;
      event.preventDefault();
      const distance = camera.position.length();
      const next = Math.min(live.current.maxDistance, Math.max(MIN_DISTANCE, distance * Math.exp(event.deltaY * 0.01)));
      flightRef.current = null;
      camera.position.multiplyScalar(next / distance);
      controls.update();
      live.current.onInteract?.();
      invalidate();
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    const enter = (event) => { if (event.pointerType === 'mouse') hoveredByMouse.current = true; };
    const leave = () => { hoveredByMouse.current = false; };
    canvas.addEventListener('pointerenter', enter);
    canvas.addEventListener('pointerleave', leave);

    controlsRef.current = controls;
    controls.update();
    report();
    return () => {
      controls.removeEventListener('change', onChange);
      controls.removeEventListener('start', onStart);
      controls.removeEventListener('end', onEnd);
      canvas.removeEventListener('gesturestart', stopGesture);
      canvas.removeEventListener('gesturechange', stopGesture);
      canvas.removeEventListener('touchstart', stopPinch);
      canvas.removeEventListener('touchmove', stopPinch);
      canvas.removeEventListener('wheel', onWheel);
      canvas.removeEventListener('pointerenter', enter);
      canvas.removeEventListener('pointerleave', leave);
      controls.dispose();
      controlsRef.current = null;
    };
  }, [camera, gl, invalidate, reducedMotion, interactive, touchNavigation]);

  // The orbit limit follows the stage size; it only needs to be refreshed, not recreated.
  useEffect(() => {
    if (controlsRef.current) controlsRef.current.maxDistance = maxDistance;
  }, [maxDistance]);

  useEffect(() => {
    if (camera.position.length() < fitDistance) {
      camera.position.normalize().multiplyScalar(fitDistance);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.update();
      invalidate();
    }
  }, [camera, fitDistance, invalidate]);

  // Данные меняются (смена показателя или года): пересчитать, видна ли ещё окрашенная страна.
  useEffect(() => {
    if (!controlsRef.current) return;
    const water = !hasVisibleData(vectors, [camera.position.x, camera.position.y, camera.position.z]);
    if (oceanRef.current !== water) { oceanRef.current = water; live.current.onOcean?.(water); }
  }, [vectors, camera]);

  // Двойное касание: плавное приближение к точке на шаре.
  useEffect(() => {
    if (!controlApi) return undefined;
    controlApi.current = {
      zoomAt(lonLat) {
        const distance = camera.position.length();
        const next = zoomedDistance(distance, 'in', { min: MIN_DISTANCE, max: live.current.maxDistance });
        const point = lonLatToSphere(lonLat, next);
        if (!point) return;
        startFlight(new Vector3(...point), 0.45);
        if (next < DETAIL_DISTANCE) live.current.onZoomDetail?.();
      },
    };
    return () => { controlApi.current = null; };
  }, [controlApi, camera, startFlight]);

  // Самовращение до первого касания; на компьютере замирает под указателем, вне экрана и в фоне не тратит кадры.
  useEffect(() => {
    const canvas = gl.domElement;
    if (typeof IntersectionObserver !== 'function') return undefined;
    const observer = new IntersectionObserver(([entry]) => setVisible(Boolean(entry?.isIntersecting)), { threshold: 0.2 });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [gl]);
  const spinning = Boolean(autoRotate) && !reducedMotion && visible;
  useEffect(() => {
    if (!spinning) return undefined;
    let last = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const controls = controlsRef.current;
      if (!controls || flightRef.current || draggingRef.current || hoveredByMouse.current || document.hidden) return;
      // Камера идёт на запад над поверхностью: страны плывут слева направо, как при вращении Земли.
      camera.position.applyAxisAngle(Y_AXIS, -SPIN_DEGREES_PER_SECOND * dt * Math.PI / 180);
      camera.lookAt(0, 0, 0);
      controls.update();
      invalidate();
    }, SPIN_TICK_MS);
    return () => window.clearInterval(timer);
  }, [spinning, camera, invalidate]);

  useEffect(() => {
    if (!cameraCommand) return;
    live.current.onHover(null);
    const currentDistance = camera.position.length();
    let target = camera.position.clone();
    if (cameraCommand.type === 'focus') {
      const code = normalizePlanetCountryCode(cameraCommand.countryCode);
      const matches = entries.filter((item) => item.code === code && item.focus);
      if (!matches.length) return;
      // Главная суша страны: по ней и считаем размер, и наводим камеру.
      const entry = matches.reduce((best, item) => (geoArea(item.feature) > geoArea(best.feature) ? item : best));
      const distance = focusDistance({ current: currentDistance, fit: fitDistance, min: MIN_DISTANCE, area: geoArea(entry.feature) });
      target = new Vector3(...lonLatToSphere(liftedFocus(entry.focus), distance));
      if (distance < DETAIL_DISTANCE) live.current.onZoomDetail?.();
    } else if (cameraCommand.type === 'reset') {
      const focus = defaultScope === 'europe' ? [15, 47] : homeFocus;
      target = new Vector3(...lonLatToSphere(focus, Math.max(INITIAL_DISTANCE, fitDistance)));
    } else {
      const next = zoomedDistance(currentDistance, cameraCommand.type === 'zoomIn' ? 'in' : 'out', { min: MIN_DISTANCE, max: maxDistance });
      target.normalize().multiplyScalar(next);
      if (next < DETAIL_DISTANCE) live.current.onZoomDetail?.();
    }
    startFlight(target, cameraCommand.instant ? 0 : FLIGHT_SECONDS);
  }, [cameraCommand, entries, camera, defaultScope, fitDistance, maxDistance, homeFocus, startFlight]);

  const introDone = useRef(false);
  useEffect(() => {
    if (!surfaceReady || introDone.current) return;
    introDone.current = true;
    if (cameraCommand) return;
    // The canvas already opened at the offset view, so the turn starts without a jump.
    const distance = camera.position.length();
    const focus = defaultScope === 'europe' ? [15, 47] : homeFocus;
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

function Earth({ textures, budget, entries, locale, mode, valuesByCode, unit, valueDigits, showValues, colorModel, selectedCode, cameraCommand, onHover, onSelect, onReady, onInteract, zoomed, controlApi }) {
  const { invalidate, gl } = useThree();
  const pointerState = useRef(createPlanetPointerState());
  const completedTap = useRef(null);
  const lastTap = useRef(null);
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
  const fineAtlas = Boolean(textures.detail);
  const atlas = useMemo(() => {
    const texture = new CanvasTexture(paintAtlas(entries, {
      mode, valuesByCode, colorModel, width: fineAtlas ? ATLAS_DETAIL_WIDTH : ATLAS_WIDTH,
    }));
    // Premultiplied alpha, raw values: thin low-alpha lines and tiny islands survive filtering and mipmaps
    // (non-premultiplied upload turned their edge texels into black specks); the shader decodes sRGB itself.
    texture.premultiplyAlpha = true;
    texture.colorSpace = NoColorSpace;
    // Mipmaps: thin border lines otherwise sparkle when the sphere is minified on a phone.
    texture.minFilter = LinearMipmapLinearFilter;
    texture.generateMipmaps = true;
    texture.anisotropy = 8;
    return texture;
  }, [entries, mode, valuesByCode, colorModel, fineAtlas]);
  // One mask canvas per atlas; hover and selection repaint it instead of allocating a new texture each time.
  // The mask is repainted and re-uploaded on every hover change, so it stays 2048 wide; the shader blurs its edge lightly
  // (softMask) and the border geometry gets finer from the 10m atlas when the camera is close.
  const highlightWidth = ATLAS_WIDTH;
  const highlight = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = highlightWidth;
    canvas.height = highlightWidth / 2;
    paintHighlight(canvas, entries, selectedCode, hoveredCode);
    const texture = new CanvasTexture(canvas);
    // Coverage data, not colour: sampled raw so the 0.5 crossing stays on the true border.
    texture.colorSpace = NoColorSpace;
    texture.minFilter = LinearMipmapLinearFilter;
    texture.generateMipmaps = true;
    texture.anisotropy = 4;
    return texture;
    // Later selection/hover changes repaint the same canvas in the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries, highlightWidth]);
  useEffect(() => {
    paintHighlight(highlight.image, entries, selectedCode, hoveredCode);
    highlight.needsUpdate = true;
    invalidate();
  }, [highlight, entries, selectedCode, hoveredCode, invalidate]);
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
    highlightTexel: { value: 1 / highlightWidth },
    // In «Data» the base surface calms down so country colours read as one scale.
    dataWash: { value: mode === 'data' ? 1 : 0 },
  }), [textures, atlas, highlight, highlightWidth, mode]);
  // A soft veil of air around the limb: a visible glow along the edge even behind the data colours.
  const atmosphereUniforms = useMemo(() => ({ strength: { value: mode === 'data' ? 0.32 : 0.42 } }), [mode]);
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
      // Любое касание шара останавливает самовращение (раньше только перетаскивание: шар «уезжал» из-под пальца).
      onInteract?.();
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
  }, [gl, onHover, onInteract]);

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
    // Двойное касание приближает шар к точке касания и не считается повторным нажатием («открыть страну»).
    const native = event.nativeEvent;
    const previous = lastTap.current;
    if (previous && native.timeStamp - previous.time < DOUBLE_TAP_MS && Math.hypot(native.clientX - previous.x, native.clientY - previous.y) < 28) {
      lastTap.current = null;
      const point = sphereToLonLat(event.point);
      if (point) controlApi?.current?.zoomAt(point);
      return;
    }
    lastTap.current = { time: native.timeStamp, x: native.clientX, y: native.clientY };
    const entry = hit(event);
    // Суша без страницы в каталоге передаёт своё название: интерфейс отвечает «данных пока нет», а не молчит.
    onSelect(
      entry?.country ? entry.dataCode : null,
      entry && !entry.country ? { name: entry.name, code: entry.code } : null,
    );
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
        {/* toneMapped=false: палитра шара (океан #DCE8F3, суша #E6E3DC, шкала) показывается ровно теми цветами, без кривой ACES. */}
        <shaderMaterial vertexShader={PLANET_VERTEX} fragmentShader={PLANET_FRAGMENT} uniforms={uniforms} toneMapped={false} />
      </mesh>
      <PlanetLabels entries={entries} locale={locale} valuesByCode={valuesByCode} unit={unit} valueDigits={valueDigits} showValues={showValues} selectedCode={selectedCode}
        hoverCode={hoveredCode} compact={budget.sphereSegments[0] <= 64} selectionOnly={!zoomed} />
      <mesh raycast={() => null} renderOrder={1}>
        <sphereGeometry args={[1.035, 64, 40]} />
        <shaderMaterial vertexShader={ATMOSPHERE_VERTEX} fragmentShader={ATMOSPHERE_FRAGMENT} uniforms={atmosphereUniforms}
          transparent depthWrite={false} side={BackSide} />
      </mesh>
      {markerPosition && (
        <mesh position={markerPosition} quaternion={markerRotation} raycast={() => null}>
          <ringGeometry args={[0.01, 0.016, 32]} />
          <meshBasicMaterial color="#ffffff" toneMapped={false} />
          <mesh position={[0, 0, 0.001]} raycast={() => null}>
            <ringGeometry args={[0.0115, 0.014, 32]} />
            <meshBasicMaterial color="#1E3A6E" toneMapped={false} />
          </mesh>
        </mesh>
      )}
    </>
  );
}

function SceneContents({ entries, budget, onError, ...props }) {
  const [wantDetail, setWantDetail] = useState(false);
  const [zoomed, setZoomed] = useState(false);
  const requestDetail = useCallback(() => setWantDetail(true), []);
  const textures = usePlanetTextures(budget, onError, wantDetail);
  return (
    <>
      <PlanetControls entries={entries} onZoomDetail={requestDetail} onZoomState={setZoomed} {...props} />
      {textures && <Earth textures={textures} budget={budget} entries={entries} zoomed={zoomed} {...props} />}
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
export default function PlanetScene({ countries, defaultScope, onError, onReady, interactive = true, touchNavigation = false, startFocus = null, ...props }) {
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
  // Сильное приближение просит самые подробные границы: у «ступенчатой» линии 50m нет вида лучше без 10m.
  const [deepZoom, setDeepZoom] = useState(false);
  const requestDeep = useCallback(() => setDeepZoom(true), []);
  useEffect(() => {
    const wanted = (deepZoom && budget.materialDetail) || planetNeedsFineFeatures(entries, props.selectedCode);
    if (atlasLevel.current >= 2 || !wanted) return undefined;
    let active = true;
    // Microstates and disconnected territories need the complete atlas when focused.
    loadPlanetFeatures('fine').then((fine) => {
      if (active && fine?.length) {
        atlasLevel.current = 2;
        setFeatures(fine);
      }
    });
    return () => { active = false; };
  }, [entries, props.selectedCode, deepZoom, budget]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(preference.matches);
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);
  const [introOffset] = useState(() => (reducedMotion ? [0, 0] : INTRO_OFFSET));
  // Стартовая сторона: где в поле зрения больше всего стран с данными (Америка и Европа), а не «пустая» Африка.
  // Страница может задать свой стартовый вид (главная: Евразия на русском сайте, США на английском); иначе считаем сами.
  const [homeFocus] = useState(() => (Array.isArray(startFocus) && startFocus.length === 2
    ? startFocus : bestStartFocus(entries, props.valuesByCode, { fallback: DEFAULT_FOCUS })));
  const controlApi = useRef(null);
  const initialFocus = defaultScope === 'europe' ? [15, 47] : homeFocus;
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
            homeFocus={homeFocus}
            controlApi={controlApi}
            onZoomDeep={requestDeep}
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
