import * as THREE from '../../node_modules/three/build/three.module.js';
import { OrbitControls } from '../../node_modules/three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from '../../node_modules/three/examples/jsm/loaders/GLTFLoader.js';

const BODY_MODEL_URLS = [
  '/results/fitted/byun/scene/body_visible.glb',
  '/results/neutral-body/byun/body/body.glb',
  '/results/canonical-body/byun/body/body.glb',
  '/results/upright-body/byun/body/body.glb',
  '/results/sam3d-body/byun/body/body.glb',
  '/results/sam3d-body/dancing/body/body.glb',
];
const GARMENT_MODELS = [
  { name: 'top', url: '/results/fitted/byun/scene/top.glb', required: false },
  { name: 'pants', url: '/results/fitted/byun/scene/pants.glb', required: false },
];

const canvas = document.querySelector('#viewer');
const status = document.querySelector('#status');
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: true,
  preserveDrawingBuffer: true,
});

renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.92;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x111313, 7, 18);

const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 0.9;
controls.maxDistance = 7;
controls.enablePan = false;

const keyLight = new THREE.DirectionalLight(0xfff2dc, 2.2);
keyLight.position.set(2.8, 4, 3.2);
scene.add(keyLight);

const fillLight = new THREE.DirectionalLight(0xbdd5ff, 1.25);
fillLight.position.set(-3, 2.2, -2.6);
scene.add(fillLight);

const rimLight = new THREE.DirectionalLight(0xffffff, 1.1);
rimLight.position.set(0, 3, -4);
scene.add(rimLight);

const ambient = new THREE.HemisphereLight(0xf7efe1, 0x27302e, 1.3);
scene.add(ambient);

const floor = createFloor();
scene.add(floor);

let model = null;
let modelBounds = new THREE.Box3();
let modelCenter = new THREE.Vector3(0, 0.9, 0);
let modelSize = new THREE.Vector3(1, 1.8, 1);

loadModel();
resize();
renderer.setAnimationLoop(render);

window.addEventListener('resize', resize);
document.querySelectorAll('[data-view]').forEach((button) => {
  button.addEventListener('click', () => setCameraView(button.dataset.view));
});
document.querySelector('[data-action="reset"]').addEventListener('click', () => {
  fitCamera('front');
});
document.querySelector('[data-action="snapshot"]').addEventListener('click', saveSnapshot);

async function loadModel() {
  setStatus('Loading body');
  const loader = new GLTFLoader();
  const previewRoot = new THREE.Group();
  previewRoot.name = 'fit-preview-root';

  const body = await loadBodyModel(loader);
  if (body.status !== 'loaded') {
    setStatus('Model load failed');
    return;
  }
  const loaded = await Promise.all(GARMENT_MODELS.map((config) => loadSceneModel(loader, config)));

  previewRoot.add(body.scene);
  loaded
    .filter((result) => result.status === 'loaded')
    .forEach((result) => previewRoot.add(result.scene));

  model = previewRoot;
  scene.add(model);
  updateBounds();
  fitCamera('front');
  window.__fitPreviewReady = true;

  const garmentCount = loaded.filter(
    (result) => result.status === 'loaded' && result.name !== 'body',
  ).length;
  setStatus(garmentCount > 0 ? 'Body + sample clothes loaded' : 'Body loaded');
}

async function loadBodyModel(loader) {
  for (const url of BODY_MODEL_URLS) {
    const result = await loadSceneModel(loader, { name: 'body', url, required: false });
    if (result.status === 'loaded') {
      return result;
    }
  }
  return { name: 'body', status: 'failed' };
}

function loadSceneModel(loader, config) {
  return new Promise((resolve) => {
    loader.load(
      config.url,
      (gltf) => {
        const root = gltf.scene;
        root.name = `preview-${config.name}`;
        prepareModel(root, config.name);
        resolve({ ...config, status: 'loaded', scene: root });
      },
      undefined,
      (error) => {
        if (config.required) {
          console.error(error);
        } else {
          console.info(`Optional model skipped: ${config.url}`);
        }
        resolve({ ...config, status: 'failed', error });
      },
    );
  });
}

function prepareModel(root, modelName) {
  root.traverse((object) => {
    if (!object.isMesh) return;
    object.castShadow = false;
    object.receiveShadow = false;
    object.frustumCulled = false;
    if (!object.material) {
      object.material = new THREE.MeshStandardMaterial();
    }
    if (modelName === 'body') {
      object.material = new THREE.MeshStandardMaterial({
        color: 0x94948f,
        roughness: 0.88,
        metalness: 0.0,
        side: THREE.DoubleSide,
      });
    }
    object.material.side = THREE.DoubleSide;
    object.material.roughness = modelName === 'pants' ? 0.68 : 0.78;
    object.material.metalness = 0.0;
    if (modelName === 'body') {
      object.material.roughness = 0.86;
    }
    if (object.material.map) {
      object.material.map.encoding = THREE.sRGBEncoding;
    }
    object.material.transparent = false;
    object.material.depthWrite = true;
    object.material.needsUpdate = true;
  });
}

function updateBounds() {
  modelBounds = new THREE.Box3().setFromObject(model);
  modelBounds.getCenter(modelCenter);
  modelBounds.getSize(modelSize);
  controls.target.copy(modelCenter);
  floor.position.y = modelBounds.min.y - Math.max(modelSize.y * 0.02, 0.02);
  floor.scale.setScalar(Math.max(modelSize.x, modelSize.z, 1.2) * 1.7);
}

function setCameraView(view) {
  fitCamera(view);
}

function fitCamera(view = 'front') {
  const radius = Math.max(modelSize.x, modelSize.y, modelSize.z, 1);
  const distance = radius * 2.25;
  const verticalLift = radius * 0.14;

  const directions = {
    front: new THREE.Vector3(0, 0.04, distance),
    left: new THREE.Vector3(-distance, 0.04, 0),
    back: new THREE.Vector3(0, 0.04, -distance),
  };

  const direction = directions[view] ?? directions.front;
  camera.position.copy(modelCenter).add(direction);
  camera.position.y += verticalLift;
  camera.near = Math.max(distance / 100, 0.01);
  camera.far = distance * 10;
  camera.updateProjectionMatrix();
  controls.target.copy(modelCenter);
  controls.update();
}

function createFloor() {
  const geometry = new THREE.CircleGeometry(1, 96);
  const material = new THREE.MeshBasicMaterial({
    color: 0xebe2cf,
    transparent: true,
    opacity: 0.1,
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

function saveSnapshot() {
  render();
  const link = document.createElement('a');
  link.href = renderer.domElement.toDataURL('image/png');
  link.download = 'fit-preview.png';
  link.click();
}

function resize() {
  const { clientWidth, clientHeight } = canvas.parentElement;
  renderer.setSize(clientWidth, clientHeight, false);
  camera.aspect = clientWidth / clientHeight;
  camera.updateProjectionMatrix();
}

function render() {
  controls.update();
  renderer.render(scene, camera);
}

function setStatus(message) {
  status.textContent = message;
}
