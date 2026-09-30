import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import {
  CanvasTexture, Color, InstancedBufferAttribute, InstancedMesh,
  LinearFilter, Matrix4, NoColorSpace, PlaneGeometry, ShaderMaterial, Vector3,
} from 'three';
import { buildPlanetLabels, layoutPlanetLabels, packPlanetLabelAtlas } from '../lib/planetLabels';

const MAX_LABELS = 24;
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
  uniform vec3 selectedInk;
  uniform vec3 hoverInk;
  uniform vec3 halo;
  varying vec2 vLabelUv;
  varying float vLabelActive;
  void main() {
    vec4 mask = texture2D(labelMap, vLabelUv);
    if (mask.a < 0.035) discard;
    vec3 textInk = vLabelActive > 1.5 ? selectedInk : vLabelActive > 0.5 ? hoverInk : ink;
    gl_FragColor = vec4(mix(textInk, halo, mask.r), mask.a);
    #include <colorspace_fragment>
  }
`;

/** System-font text mask; the atlas is shared by every visible instance. */
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
  let fontPixels = 20;
  for (const candidateSize of [20, 18, 16]) {
    context.font = `600 ${candidateSize}px ${FONT_FAMILY}`;
    items = packPlanetLabelAtlas(labels, (text) => context.measureText(text).width, { lineHeight: candidateSize + 4 });
    fontPixels = candidateSize;
    if (items) break;
  }
  if (!items) return null;
  for (const label of items) {
    const { x, y, width, height, lines } = label;
    for (let index = 0; index < lines.length; index += 1) {
      const baseline = y + 4 + index * (fontPixels + 4) + (fontPixels + 4) / 2;
      context.lineWidth = 3;
      context.strokeStyle = '#fff';
      context.strokeText(lines[index], x + width / 2, baseline);
      context.fillStyle = '#000';
      context.fillText(lines[index], x + width / 2, baseline);
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
      selectedInk: { value: new Color('#AD8A48') },
      hoverInk: { value: new Color('#80642F') },
      halo: { value: new Color('#FFFFFF') },
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
export default function PlanetLabels({ entries, locale = 'ru', selectedCode, hoverCode, compact = false }) {
  const { camera, size, invalidate } = useThree();
  const labels = useMemo(() => buildPlanetLabels(entries, { locale }), [entries, locale]);
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
  }, [selectedCode, hoverCode, compact, size.width, size.height, invalidate]);
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
    const fontPixels = compactLayout ? 11.5 : 13;
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
      maxVisible: compactLayout ? 12 : MAX_LABELS,
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
