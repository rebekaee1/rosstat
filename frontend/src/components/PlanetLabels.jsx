import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import {
  CanvasTexture, Color, InstancedBufferAttribute, InstancedMesh,
  LinearFilter, Matrix4, NoColorSpace, PlaneGeometry, ShaderMaterial, Vector3,
} from 'three';
import { buildPlanetLabels, layoutPlanetLabels, packPlanetLabelAtlas } from '../lib/planetLabels';

const MAX_LABELS = 16;
const FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const ATLAS_WIDTH = 2048;
const ATLAS_HEIGHT = 1024;

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
  uniform vec3 line;
  uniform vec3 selectedLine;
  varying vec2 vLabelUv;
  varying float vLabelActive;
  void main() {
    vec4 mask = texture2D(labelMap, vLabelUv);
    if (mask.a < 0.035) discard;
    // Gray glyphs encode ink coverage; red pixels encode only the panel border.
    vec3 panel = mix(ink, paper, mask.g);
    vec3 border = vLabelActive > 0.5 ? selectedLine : line;
    panel = mix(panel, border, clamp(mask.r - mask.g, 0.0, 1.0));
    gl_FragColor = vec4(panel, mask.a);
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
      }, paddingX: 12, paddingY: 8, lineGap: 4,
    });
    fontPixels = candidateSize;
    if (items) break;
  }
  if (!items) return null;
  for (const label of items) {
    const { x, y, width, height, nameLines, valueLines } = label;
    context.beginPath();
    context.roundRect(x + 1, y + 1, width - 2, height - 2, 10);
    context.fillStyle = '#fff';
    context.fill();
    context.strokeStyle = '#f00';
    context.lineWidth = 2;
    context.stroke();
    const nameSize = fontPixels * 5 / 6;
    context.font = `500 ${nameSize}px ${FONT_FAMILY}`;
    context.fillStyle = '#151515';
    for (let index = 0; index < nameLines.length; index += 1) {
      const baseline = y + 8 + index * (nameSize + 4) + (nameSize + 4) / 2;
      context.fillText(nameLines[index], x + width / 2, baseline);
    }
    if (valueLines.length) {
      context.font = `600 ${fontPixels}px ${FONT_FAMILY}`;
      context.fillStyle = '#000';
      for (let index = 0; index < valueLines.length; index += 1) {
        const baseline = y + 8 + nameLines.length * (nameSize + 4) + 4 + index * (fontPixels + 4) + (fontPixels + 4) / 2;
        context.fillText(valueLines[index], x + width / 2, baseline);
      }
    }
    label.uv = [x / ATLAS_WIDTH, 1 - (y + height) / ATLAS_HEIGHT, (x + width) / ATLAS_WIDTH, 1 - y / ATLAS_HEIGHT];
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
      line: { value: new Color('#D3C4A3') },
      selectedLine: { value: new Color('#80642F') },
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

/**
 * Geographic labels share one texture and one draw call. This callback only runs
 * on the parent demand frames; it never requests another frame or sets state.
 */
export default function PlanetLabels({ entries, locale = 'ru', valuesByCode, unit = '', showValues = false, selectedCode, hoverCode, compact = false }) {
  const { camera, size, invalidate } = useThree();
  // The metric heading and country card retain the denominator of percentage
  // units; repeating it on every country would obscure the surface.
  const labels = useMemo(() => buildPlanetLabels(entries, {
    locale, valuesByCode, unit: unit.trim().startsWith('%') ? '%' : unit,
  }), [entries, locale, valuesByCode, unit]);
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
  }, [selectedCode, hoverCode, compact, showValues, size.width, size.height, invalidate]);
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
    const candidates = current.items.map((label) => {
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
        width: label.width * fontScale,
        height: label.height * fontScale,
      };
    });
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
      valuesOnly: showValues,
      globe,
    });
    current.mesh.count = visible.length;
    visible.forEach((label, index) => {
      // Move the camera-facing quad upward in screen space, clear of the marker.
      scratch.point.set(...label.position).applyMatrix4(camera.matrixWorldInverse);
      scratch.point.y += (label.y - label.labelY) * label.worldPerPixel;
      scratch.point.applyMatrix4(camera.matrixWorld);
      scratch.matrix.makeScale(label.width * label.worldPerPixel, label.height * label.worldPerPixel, 1);
      scratch.matrix.setPosition(scratch.point);
      current.mesh.setMatrixAt(index, scratch.matrix);
      current.uv.setXYZW(index, ...label.uv);
      current.active.setX(index, label.active);
    });
    current.mesh.instanceMatrix.needsUpdate = true;
    current.uv.needsUpdate = true;
    current.active.needsUpdate = true;
  });

  return resources ? <primitive object={resources.mesh} dispose={null} /> : null;
}
