import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import {
  CanvasTexture, Color, InstancedBufferAttribute, InstancedMesh,
  LinearFilter, Matrix4, NoColorSpace, PlaneGeometry, ShaderMaterial, Vector3,
} from 'three';
import { buildPlanetLabels, layoutPlanetLabels, packPlanetLabelAtlas } from '../lib/planetLabels';
import { normalizePlanetCountryCode } from '../lib/planetGeometry';

const MAX_LABELS = 16;
const FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const ATLAS_WIDTH = 2048;
const ATLAS_HEIGHT = 1024;
// Round 6: no plate and no pointer. A name is plain graphite text with a 1 px light halo, standing on its country.
const TAIL_HEIGHT = 0;
const PADDING_X = 6;
const PADDING_Y = 4;
const HALO_WIDTH = 5;

const VERTEX = `
  attribute vec4 labelUv;
  attribute float labelActive;
  varying vec2 vLabelUv;
  varying float vLabelActive;
  void main() {
    vLabelUv = mix(labelUv.xy, labelUv.zw, uv);
    vLabelActive = labelActive;
    vec4 center = modelViewMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
    vec2 size = vec2(length(instanceMatrix[0].xyz), length(instanceMatrix[1].xyz));
    center.xy += position.xy * size;
    gl_Position = projectionMatrix * center;
  }
`;

const FRAGMENT = `
  uniform sampler2D labelMap;
  uniform vec3 ink;
  uniform vec3 paper;
  uniform vec3 selectedInk;
  varying vec2 vLabelUv;
  varying float vLabelActive;
  void main() {
    vec4 mask = texture2D(labelMap, vLabelUv);
    if (mask.a < 0.035) discard;
    // The atlas holds black glyphs over a white halo: the grey level says how much is ink and how much is halo.
    vec3 glyph = vLabelActive > 0.5 ? selectedInk : ink;
    gl_FragColor = vec4(mix(glyph, paper, mask.g), mask.a);
    #include <colorspace_fragment>
  }
`;

/** Opaque panels and system-font text share one atlas and one draw call. */
function createLabelAtlas(labels) {
  const canvas = document.createElement('canvas');
  canvas.width = ATLAS_WIDTH;
  canvas.height = ATLAS_HEIGHT;
  const context = canvas.getContext('2d');
  if (!context) return null;
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.lineJoin = 'round';
  let items = null;
  let fontPixels = 24;
  for (const candidateSize of [24, 22, 20, 18]) {
    const nameSize = candidateSize * 5 / 6;
    items = packPlanetLabelAtlas(labels, (text) => {
      context.font = `500 ${nameSize}px ${FONT_FAMILY}`;
      return context.measureText(text).width;
    }, {
      lineHeight: nameSize + 4, valueLineHeight: candidateSize + 4,
      measureValue: (text) => {
        context.font = `600 ${candidateSize}px ${FONT_FAMILY}`;
        return context.measureText(text).width;
      }, paddingX: PADDING_X, paddingY: PADDING_Y, lineGap: 2, tailHeight: TAIL_HEIGHT,
    });
    fontPixels = candidateSize;
    if (items) break;
  }
  if (!items) return null;
  for (const label of items) {
    const { x, y, width, nameLines, valueLines, nameWidth, nameHeight } = label;
    context.lineWidth = HALO_WIDTH;
    context.strokeStyle = '#fff';
    context.fillStyle = '#000';
    const nameSize = fontPixels * 5 / 6;
    context.font = `500 ${nameSize}px ${FONT_FAMILY}`;
    for (let index = 0; index < nameLines.length; index += 1) {
      const baseline = y + PADDING_Y + index * (nameSize + 4) + (nameSize + 4) / 2;
      context.strokeText(nameLines[index], x + width / 2, baseline);
      context.fillText(nameLines[index], x + width / 2, baseline);
    }
    if (valueLines.length) {
      context.font = `600 ${fontPixels}px ${FONT_FAMILY}`;
      for (let index = 0; index < valueLines.length; index += 1) {
        const baseline = y + PADDING_Y + nameLines.length * (nameSize + 4) + 2 + index * (fontPixels + 4) + (fontPixels + 4) / 2;
        context.strokeText(valueLines[index], x + width / 2, baseline);
        context.fillText(valueLines[index], x + width / 2, baseline);
      }
    }
    const top = 1 - y / ATLAS_HEIGHT;
    label.uv = [x / ATLAS_WIDTH, 1 - (y + label.height) / ATLAS_HEIGHT, (x + width) / ATLAS_WIDTH, top];
    const nameLeft = x + (width - nameWidth) / 2;
    label.uvName = [nameLeft / ATLAS_WIDTH, 1 - (y + nameHeight) / ATLAS_HEIGHT, (nameLeft + nameWidth) / ATLAS_WIDTH, top];
  }
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = NoColorSpace;
  texture.minFilter = LinearFilter;
  texture.magFilter = LinearFilter;
  texture.generateMipmaps = false;
  return { texture, items, fontPixels };
}

function createLabelResources(labels) {
  const atlas = createLabelAtlas(labels);
  if (!atlas) return null;
  const geometry = new PlaneGeometry(1, 1);
  const uv = new InstancedBufferAttribute(new Float32Array(MAX_LABELS * 4), 4);
  const active = new InstancedBufferAttribute(new Float32Array(MAX_LABELS), 1);
  geometry.setAttribute('labelUv', uv);
  geometry.setAttribute('labelActive', active);
  const material = new ShaderMaterial({
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    uniforms: {
      labelMap: { value: atlas.texture },
      ink: { value: new Color('#202A3C') },
      paper: { value: new Color('#FFFFFF') },
      // Выбранная страна подписана глубоким синим: он же цвет кромки подсветки на шаре.
      selectedInk: { value: new Color('#1E3A6E') },
    },
    transparent: true,
    // Explicit hemisphere and whole-label silhouette clipping keeps the glyphs
    // readable; a flat camera-facing quad otherwise intersects the curved Earth.
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
  });
  const mesh = new InstancedMesh(geometry, material, MAX_LABELS);
  mesh.count = 0;
  mesh.frustumCulled = false;
  mesh.raycast = () => null;
  mesh.renderOrder = 20;
  return { ...atlas, geometry, material, mesh, uv, active };
}

// Всё, что лежит поверх шара и не должно закрывать подписи или быть закрыто ими.
const OVERLAY_SELECTOR = '.planet-quick, .planet-camera-controls button, .planet-stage-bottom > *, .planet-minimap, .planet-play-year, .planet-gesture-hint';
const OVERLAY_PAD = 4;

/** Прямоугольники кнопок и чипов в пикселях холста; пусто, если рядом нет оболочки сцены (тесты, встраивание). */
function overlayKeepOut(canvas) {
  const stage = canvas?.closest?.('.planet-stage');
  if (!stage || typeof canvas.getBoundingClientRect !== 'function') return [];
  const origin = canvas.getBoundingClientRect();
  const zones = [];
  stage.querySelectorAll(OVERLAY_SELECTOR).forEach((node) => {
    const box = node.getBoundingClientRect();
    if (!(box.width > 0 && box.height > 0)) return;
    zones.push({
      left: box.left - origin.left - OVERLAY_PAD, right: box.right - origin.left + OVERLAY_PAD,
      top: box.top - origin.top - OVERLAY_PAD, bottom: box.bottom - origin.top + OVERLAY_PAD,
    });
  });
  return zones;
}

/**
 * Geographic labels share one texture and one draw call. This callback only runs
 * on the parent demand frames; it never requests another frame or sets state.
 */
export default function PlanetLabels({ entries, locale = 'ru', valuesByCode, unit = '', valueDigits, showValues = false, selectedCode, hoverCode, compact = false, selectionOnly = false }) {
  const { camera, size, invalidate, gl } = useThree();
  // The metric heading and country card retain the denominator of percentage
  // units; repeating it on every country would obscure the surface.
  const labels = useMemo(() => buildPlanetLabels(entries, {
    locale, valuesByCode, unit: unit.trim().startsWith('%') ? '%' : unit, digits: valueDigits,
  }), [entries, locale, valuesByCode, unit, valueDigits]);
  const resources = useMemo(() => createLabelResources(labels), [labels]);
  const activeResources = useRef(null);
  const scratch = useMemo(() => ({
    point: new Vector3(), normal: new Vector3(), eye: new Vector3(),
    projected: new Vector3(), local: new Vector3(), matrix: new Matrix4(),
  }), []);

  useEffect(() => {
    activeResources.current = resources;
    invalidate();
    return () => { activeResources.current = null; };
  }, [resources, invalidate]);
  useEffect(() => {
    invalidate();
  }, [selectedCode, hoverCode, compact, showValues, selectionOnly, size.width, size.height, invalidate]);
  useEffect(() => () => {
    resources?.mesh.dispose();
    resources?.texture.dispose();
    resources?.geometry.dispose();
    resources?.material.dispose();
  }, [resources]);

  useFrame(() => {
    const current = activeResources.current;
    if (!current || !size.height) return;
    const compactLayout = compact || size.width < 600;
    const fontPixels = compactLayout ? 13 : 14.5;
    const fontScale = fontPixels / current.fontPixels;
    const halfFrustum = Math.tan(camera.fov * Math.PI / 360);
    const selectedKey = normalizePlanetCountryCode(selectedCode);
    const hoverKey = normalizePlanetCountryCode(hoverCode);
    const candidates = current.items.map((label) => {
      // The value is printed only for the selected (or hovered) country; every other name stands alone.
      const full = showValues && label.valueLines.length > 0 && (label.code === selectedKey || label.code === hoverKey);
      scratch.point.set(...label.position);
      scratch.normal.copy(scratch.point).normalize();
      scratch.eye.copy(camera.position).sub(scratch.point).normalize();
      const facing = scratch.normal.dot(scratch.eye);
      scratch.projected.copy(scratch.point).project(camera);
      scratch.local.copy(scratch.point).applyMatrix4(camera.matrixWorldInverse);
      return {
        ...label,
        x: (scratch.projected.x + 1) * size.width / 2,
        y: (1 - scratch.projected.y) * size.height / 2,
        depth: scratch.projected.z,
        facing,
        worldPerPixel: 2 * halfFrustum * -scratch.local.z / size.height,
        full,
        width: (full ? label.width : label.nameWidth) * fontScale,
        height: (full ? label.height : label.nameHeight) * fontScale,
      };
    });
    const keepOut = overlayKeepOut(gl?.domElement);
    scratch.projected.set(0, 0, 0).project(camera);
    const globe = {
      x: (scratch.projected.x + 1) * size.width / 2,
      y: (1 - scratch.projected.y) * size.height / 2,
      radius: size.height / (2 * halfFrustum * Math.sqrt(Math.max(0.0001, camera.position.lengthSq() - 1))),
    };
    const visible = layoutPlanetLabels(candidates, {
      width: size.width, height: size.height,
      cameraDistance: camera.position.length(), selectedCode, hoverCode,
      maxVisible: compactLayout ? 8 : MAX_LABELS,
      selectionOnly,
      centered: true,
      globe,
      keepOut,
    });
    current.mesh.count = visible.length;
    visible.forEach((label, index) => {
      // Move the camera-facing quad upward in screen space, clear of the marker.
      scratch.point.set(...label.position).applyMatrix4(camera.matrixWorldInverse);
      scratch.point.y += (label.y - label.labelY) * label.worldPerPixel;
      scratch.point.x += (label.labelX - label.x) * label.worldPerPixel;
      scratch.point.applyMatrix4(camera.matrixWorld);
      scratch.matrix.makeScale(label.width * label.worldPerPixel, label.height * label.worldPerPixel, 1);
      scratch.matrix.setPosition(scratch.point);
      current.mesh.setMatrixAt(index, scratch.matrix);
      current.uv.setXYZW(index, ...(label.full ? label.uv : label.uvName));
      current.active.setX(index, label.active);
    });
    current.mesh.instanceMatrix.needsUpdate = true;
    current.uv.needsUpdate = true;
    current.active.needsUpdate = true;
  });

  return resources ? <primitive object={resources.mesh} dispose={null} /> : null;
}
