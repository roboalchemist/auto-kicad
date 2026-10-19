/** Interactive 3D board viewer: the real KiCad GLB (board + copper + parts) rendered with three.js.
 *
 *  The static `pcb render` image stays available as a fallback if the GLB cannot be loaded.
 */

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type Preset = "iso" | "top" | "bottom" | "front" | "back";

const PRESET_DIR: Record<Preset, [number, number, number]> = {
  iso: [1, 0.85, 1],
  top: [0, 1, 0.0001],
  bottom: [0, -1, 0.0001],
  front: [0, 0.12, 1],
  back: [0, 0.12, -1],
};

export function Viewer3D({ design, rev, boardHash, fallbackUrl }: {
  design: string | null;
  rev: string;
  boardHash?: string | null;
  fallbackUrl?: string | null;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    root: THREE.Object3D | null;
    center: THREE.Vector3;
    radius: number;
  } | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  // ---- one-time scene setup. Everything here can throw (no WebGL, lost context, a failing GPU
  // driver); a throw inside an effect unmounts the whole React tree, so fail into the error state.
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    } catch (err) {
      setStatus("error");
      setError(
        `WebGL is not available in this browser (${err instanceof Error ? err.message : String(err)}). ` +
          "The static render below is the fallback.",
      );
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth || 800, host.clientHeight || 600);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 5000);
    camera.position.set(60, 45, 60);

    scene.add(new THREE.HemisphereLight(0xdfe9f5, 0x1b2430, 1.4));
    const key = new THREE.DirectionalLight(0xffffff, 2.1);
    key.position.set(1, 1.6, 1).multiplyScalar(60);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xbcd4ff, 0.9);
    fill.position.set(-1, 0.7, -0.8).multiplyScalar(60);
    scene.add(fill);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.minDistance = 2;
    controls.maxDistance = 3000;

    sceneRef.current = { renderer, scene, camera, controls, root: null, center: new THREE.Vector3(), radius: 20 };

    let raf = 0;
    let contextLost = false;
    const tick = () => {
      if (contextLost) return;
      controls.update();
      try {
        renderer.render(scene, camera);
      } catch {
        // A driver hiccup mid-frame should not kill the app; stop the loop and report it.
        setStatus("error");
        setError("the graphics context stopped responding");
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    tick();

    const onLost = (event: Event) => {
      event.preventDefault();
      contextLost = true;
      cancelAnimationFrame(raf);
      setStatus("error");
      setError("the browser lost the graphics context — switch tabs to reload the 3D view");
    };
    const onRestored = () => {
      contextLost = false;
      setError(null);
      setStatus(sceneRef.current?.root ? "ready" : "loading");
      tick();
    };
    renderer.domElement.addEventListener("webglcontextlost", onLost);
    renderer.domElement.addEventListener("webglcontextrestored", onRestored);

    const resize = () => {
      const w = host.clientWidth || 800;
      const h = host.clientHeight || 600;
      renderer.setSize(w, h);
      camera.aspect = w / Math.max(1, h);
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(host);
    resize();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("webglcontextlost", onLost);
      renderer.domElement.removeEventListener("webglcontextrestored", onRestored);
      controls.dispose();
      disposeScene(scene);
      renderer.dispose();
      // Releasing the context explicitly keeps repeated tab switches under Chrome's limit.
      renderer.forceContextLoss();
      if (renderer.domElement.parentElement === host) host.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
  }, []);

  const frame = (preset: Preset) => {
    const s = sceneRef.current;
    if (!s) return;
    const [x, y, z] = PRESET_DIR[preset];
    const dir = new THREE.Vector3(x, y, z).normalize();
    const distance = Math.max(s.radius / Math.sin((s.camera.fov * Math.PI) / 360) * 1.25, 1);
    s.camera.position.copy(s.center).addScaledVector(dir, distance);
    // Top/bottom look straight down/up the Y axis, so "up" must be the board's north (-Z),
    // otherwise the view comes out mirrored.
    if (preset === "top") s.camera.up.set(0, 0, -1);
    else if (preset === "bottom") s.camera.up.set(0, 0, 1);
    else s.camera.up.set(0, 1, 0);
    s.camera.lookAt(s.center);
    s.controls.target.copy(s.center);
    s.controls.update();
  };

  // ---- load the board model whenever the revision changes
  useEffect(() => {
    const s = sceneRef.current;
    if (!s || !design) return;
    let cancelled = false;
    setStatus("loading");
    setError(null);

    const url = `/api/designs/${design}/rev/${rev}/model.glb${rev === "working" && boardHash ? `?v=${boardHash}` : ""}`;
    new GLTFLoader().load(
      url,
      (gltf) => {
        if (cancelled) {
          disposeScene(gltf.scene);
          return;
        }
        try {
          if (s.root) {
            s.scene.remove(s.root);
            disposeScene(s.root);
          }
          const root = gltf.scene;
          // KiCad's GLB is in metres (glTF convention), so normalise instead of assuming units:
          // centre the board at the origin and scale its largest dimension to 100 scene units.
          // The offset goes on the child so the group's uniform scale moves it too.
          const box = new THREE.Box3().setFromObject(root);
          const size = box.getSize(new THREE.Vector3());
          const center = box.getCenter(new THREE.Vector3());
          const scale = 100 / Math.max(size.x, size.y, size.z, 1e-6);
          if (!Number.isFinite(scale) || scale <= 0) throw new Error("the model has no usable geometry");
          root.position.sub(center);

          const group = new THREE.Group();
          group.add(root);
          group.scale.setScalar(scale);
          group.updateMatrixWorld(true);
          s.scene.add(group);
          s.root = group;

          const sphere = new THREE.Box3().setFromObject(group).getBoundingSphere(new THREE.Sphere());
          s.center.copy(sphere.center);
          s.radius = Math.max(sphere.radius, 1);
          s.controls.minDistance = s.radius * 0.35;
          s.controls.maxDistance = s.radius * 12;
          s.camera.near = Math.max(s.radius / 500, 0.1);
          s.camera.far = s.radius * 60;
          s.camera.updateProjectionMatrix();
          frame("iso");
          setStatus("ready");
        } catch (err) {
          setStatus("error");
          setError(err instanceof Error ? err.message : "could not build the 3D scene");
        }
      },
      undefined,
      (err) => {
        if (cancelled) return;
        setStatus("error");
        setError(err instanceof Error ? err.message : "could not load the 3D model");
      },
    );

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [design, rev, boardHash]);

  return (
    <div className="viewer3d" data-testid="viewer-3d" data-status={status}>
      <div className="viewer3d-host" ref={hostRef} />
      {status === "loading" && <div className="viewer3d-note">Loading 3D model…</div>}
      {status === "error" && (
        <div className="viewer3d-error" data-testid="viewer-3d-error">
          <b>3D model unavailable.</b> {error}
          {fallbackUrl && <img src={fallbackUrl} alt="Static 3D render" />}
        </div>
      )}
      <div className="viewer3d-controls">
        {(["iso", "top", "bottom", "front", "back"] as Preset[]).map((preset) => (
          <button key={preset} data-testid={`viewer3d-${preset}`} onClick={() => frame(preset)}>
            {preset}
          </button>
        ))}
        <span className="viewer3d-hint">drag to orbit · right-drag to pan · scroll to zoom</span>
      </div>
    </div>
  );
}

function disposeScene(root: THREE.Object3D) {
  root.traverse((node) => {
    const mesh = node as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
    const list = Array.isArray(material) ? material : material ? [material] : [];
    for (const m of list) {
      // Textures are not owned by the material's dispose(); drop them explicitly.
      for (const value of Object.values(m)) {
        const texture = value as THREE.Texture | null;
        if (texture && texture.isTexture) texture.dispose();
      }
      m.dispose();
    }
  });
}
