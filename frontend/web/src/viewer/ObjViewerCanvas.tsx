import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";

type CameraPreset = "front" | "angle" | "side" | "back";

type ViewerPhase = "idle" | "loading" | "ready" | "error";

type ViewerStatus = {
  phase: ViewerPhase;
  message: string;
};

type MeshStats = {
  vertices: number;
  faces: number;
};

type ObjViewerCanvasProps = {
  assetUrl: string;
  wireframe: boolean;
  autoRotate: boolean;
  cameraPreset: CameraPreset;
  darkStage: boolean;
  onStatusChange: (status: ViewerStatus) => void;
  onMeshStatsChange: (stats: MeshStats | null) => void;
};

function applyCameraPreset(
  preset: CameraPreset,
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  distance: number,
) {
  const positions: Record<CameraPreset, [number, number, number]> = {
    front: [0, distance * 0.05, distance],
    angle: [distance * 0.72, distance * 0.12, distance * 0.72],
    side: [distance, distance * 0.08, 0],
    back: [0, distance * 0.05, -distance],
  };

  const [x, y, z] = positions[preset];
  camera.position.set(x, y, z);
  controls.target.set(0, 0, 0);
  controls.update();
}

function disposeObject3D(root: THREE.Object3D) {
  root.traverse((child: THREE.Object3D) => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose();

      const { material } = child;
      if (Array.isArray(material)) {
        material.forEach((entry) => entry.dispose());
      } else {
        material.dispose();
      }
    }
  });
}

export function ObjViewerCanvas({
  assetUrl,
  wireframe,
  autoRotate,
  cameraPreset,
  darkStage,
  onStatusChange,
  onMeshStatsChange,
}: ObjViewerCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const meshRootRef = useRef<THREE.Object3D | null>(null);
  const floorGridRef = useRef<THREE.GridHelper | null>(null);
  const materialRefs = useRef<THREE.MeshStandardMaterial[]>([]);
  const frameDistanceRef = useRef(3);

  const stageColors = useMemo(
    () =>
      darkStage
        ? {
            background: "#101417",
            gridPrimary: 0x5f6a72,
            gridSecondary: 0x283038,
          }
        : {
            background: "#f5f1ea",
            gridPrimary: 0xb8b1a7,
            gridSecondary: 0xd8d2c8,
          },
    [darkStage],
  );

  useEffect(() => {
    materialRefs.current.forEach((material) => {
      material.color.set(darkStage ? "#b3c0cc" : "#8f9bab");
      material.needsUpdate = true;
    });
  }, [darkStage]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) {
      return;
    }

    scene.background = new THREE.Color(stageColors.background);

    const grid = floorGridRef.current;
    if (grid) {
      const material = grid.material;
      if (Array.isArray(material)) {
        material[0].color.setHex(stageColors.gridPrimary);
        material[1].color.setHex(stageColors.gridSecondary);
      } else {
        material.color.setHex(stageColors.gridPrimary);
      }
    }
  }, [stageColors]);

  useEffect(() => {
    materialRefs.current.forEach((material) => {
      material.wireframe = wireframe;
      material.needsUpdate = true;
    });
  }, [wireframe]);

  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate;
      controlsRef.current.autoRotateSpeed = 1.6;
    }
  }, [autoRotate]);

  useEffect(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) {
      return;
    }

    applyCameraPreset(cameraPreset, camera, controls, frameDistanceRef.current);
  }, [cameraPreset]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    let animationFrameId = 0;
    let resizeObserver: ResizeObserver | null = null;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(stageColors.background);
    sceneRef.current = scene;

    const width = container.clientWidth || 960;
    const height = container.clientHeight || 720;

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.01, 200);
    camera.position.set(1.8, 0.25, 1.8);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 0.4;
    controls.maxDistance = 12;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 1.6;
    controlsRef.current = controls;

    const ambient = new THREE.HemisphereLight(0xffffff, 0xb0bcc7, 1.6);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.8);
    keyLight.position.set(4, 5, 6);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0xd6e8ff, 0.7);
    rimLight.position.set(-4, 2.5, -5);
    scene.add(rimLight);

    const floorGrid = new THREE.GridHelper(
      6,
      12,
      stageColors.gridPrimary,
      stageColors.gridSecondary,
    );
    scene.add(floorGrid);
    floorGridRef.current = floorGrid;

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      animationFrameId = window.requestAnimationFrame(animate);
    };
    animate();

    resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }

      const { width: nextWidth, height: nextHeight } = entry.contentRect;
      if (nextWidth <= 0 || nextHeight <= 0) {
        return;
      }

      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(nextWidth, nextHeight);
    });

    resizeObserver.observe(container);

    return () => {
      window.cancelAnimationFrame(animationFrameId);
      resizeObserver?.disconnect();
      controls.dispose();

      if (meshRootRef.current) {
        disposeObject3D(meshRootRef.current);
      }

      renderer.dispose();
      container.removeChild(renderer.domElement);
      materialRefs.current = [];
      meshRootRef.current = null;
      floorGridRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    if (!scene || !camera || !controls) {
      return;
    }

    if (!assetUrl) {
      onMeshStatsChange(null);
      onStatusChange({
        phase: "idle",
        message: "OBJ path input 필요",
      });
      return;
    }

    onStatusChange({
      phase: "loading",
      message: "OBJ asset 로딩 중",
    });

    const loader = new OBJLoader();
    let cancelled = false;

    if (meshRootRef.current) {
      scene.remove(meshRootRef.current);
      disposeObject3D(meshRootRef.current);
      meshRootRef.current = null;
      materialRefs.current = [];
    }

    loader.load(
      assetUrl,
      (group: THREE.Group) => {
        if (cancelled) {
          disposeObject3D(group);
          return;
        }

        let vertexCount = 0;
        let faceCount = 0;
        const materials: THREE.MeshStandardMaterial[] = [];

        group.traverse((child: THREE.Object3D) => {
          if (!(child instanceof THREE.Mesh)) {
            return;
          }

          child.geometry.computeVertexNormals();
          const position = child.geometry.getAttribute("position");
          vertexCount += position ? position.count : 0;
          faceCount += position ? Math.floor(position.count / 3) : 0;

          const material = new THREE.MeshStandardMaterial({
            color: darkStage ? "#b3c0cc" : "#8f9bab",
            roughness: 0.88,
            metalness: 0.06,
            wireframe,
          });

          child.material = material;
          child.castShadow = true;
          child.receiveShadow = true;
          materials.push(material);
        });

        materialRefs.current = materials;

        // SAM 3D Body output uses image-style vertical orientation, so the
        // mesh needs an X-axis flip to align with Three.js Y-up world space.
        const orientedRoot = new THREE.Group();
        orientedRoot.rotation.x = Math.PI;
        orientedRoot.add(group);
        orientedRoot.updateMatrixWorld(true);

        const sourceBox = new THREE.Box3().setFromObject(orientedRoot);
        const sourceCenter = sourceBox.getCenter(new THREE.Vector3());
        const sourceSize = sourceBox.getSize(new THREE.Vector3());
        const targetHeight = 2.15;
        const scale = sourceSize.y > 0 ? targetHeight / sourceSize.y : 1;

        orientedRoot.position.sub(sourceCenter);
        orientedRoot.scale.setScalar(scale);

        const scaledBox = new THREE.Box3().setFromObject(orientedRoot);
        const scaledCenter = scaledBox.getCenter(new THREE.Vector3());
        orientedRoot.position.sub(scaledCenter);

        const finalBox = new THREE.Box3().setFromObject(orientedRoot);
        const finalSize = finalBox.getSize(new THREE.Vector3());
        const maxDimension = Math.max(finalSize.x, finalSize.y, finalSize.z, 1);
        const frameDistance = maxDimension * 1.85;
        frameDistanceRef.current = frameDistance;

        if (floorGridRef.current) {
          floorGridRef.current.position.y = finalBox.min.y - 0.02;
        }

        scene.add(orientedRoot);
        meshRootRef.current = orientedRoot;

        camera.near = 0.01;
        camera.far = Math.max(50, frameDistance * 20);
        camera.updateProjectionMatrix();
        applyCameraPreset(cameraPreset, camera, controls, frameDistance);

        onMeshStatsChange({
          vertices: vertexCount,
          faces: faceCount,
        });

        onStatusChange({
          phase: "ready",
          message: "OBJ viewer 준비 완료",
        });
      },
      (event: ProgressEvent<EventTarget>) => {
        if (cancelled || !event.total) {
          return;
        }

        const progress = Math.round((event.loaded / event.total) * 100);
        onStatusChange({
          phase: "loading",
          message: `OBJ asset 로딩 중 ${progress}%`,
        });
      },
      (error: unknown) => {
        if (cancelled) {
          return;
        }

        const message = error instanceof Error ? error.message : "OBJ asset 로드 실패";
        onMeshStatsChange(null);
        onStatusChange({
          phase: "error",
          message,
        });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [assetUrl, cameraPreset, darkStage, onMeshStatsChange, onStatusChange, wireframe]);

  return <div className="viewer-stage" ref={containerRef} />;
}
