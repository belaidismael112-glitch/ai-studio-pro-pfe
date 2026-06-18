"use client";

import React, { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  Bounds,
  Center,
  Environment,
  Html,
  OrbitControls,
  Stars,
  useGLTF,
} from "@react-three/drei";
import * as THREE from "three";

type RegisterEarthShowcase3DProps = {
  modelPath?: string;
};

function EarthModel({
  modelPath = "/models/earth/earth.glb",
}: RegisterEarthShowcase3DProps) {
  const groupRef = useRef<THREE.Group>(null);
  const { gl } = useThree();
  const gltf = useGLTF(modelPath);

  const scene = useMemo(() => {
    const cloned = gltf.scene.clone(true);
    const maxAnisotropy = gl.capabilities.getMaxAnisotropy();

    cloned.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;

      const mesh = child as THREE.Mesh;
      mesh.castShadow = false;
      mesh.receiveShadow = false;
      mesh.frustumCulled = false;

      const materials = Array.isArray(mesh.material)
        ? mesh.material
        : [mesh.material];

      materials.forEach((mat) => {
        const material = mat as THREE.MeshStandardMaterial;
        if (!material) return;

        material.side = THREE.FrontSide;
        material.toneMapped = true;

        // IMPORTANT: keep original earth maps and improve sharpness
        if (material.map) {
          material.map.anisotropy = maxAnisotropy;
          material.map.colorSpace = THREE.SRGBColorSpace;
          material.map.needsUpdate = true;
        }

        if (material.emissiveMap) {
          material.emissiveMap.anisotropy = maxAnisotropy;
          material.emissiveMap.colorSpace = THREE.SRGBColorSpace;
          material.emissiveMap.needsUpdate = true;
        }

        if (material.roughnessMap) {
          material.roughnessMap.anisotropy = maxAnisotropy;
          material.roughnessMap.needsUpdate = true;
        }

        if (material.normalMap) {
          material.normalMap.anisotropy = maxAnisotropy;
          material.normalMap.needsUpdate = true;
        }

        material.roughness = Math.min(material.roughness ?? 0.95, 0.95);
        material.metalness = 0.0;
        material.envMapIntensity = 0.65;
        material.needsUpdate = true;
      });
    });

    return cloned;
  }, [gltf.scene, gl]);

  useFrame((state, delta) => {
    if (!groupRef.current) return;

    // slow realistic rotation
    groupRef.current.rotation.y += delta * 0.12;
    groupRef.current.rotation.x =
      THREE.MathUtils.degToRad(-18) +
      Math.sin(state.clock.elapsedTime * 0.25) * 0.01;
  });

  return (
    <group
      ref={groupRef}
      rotation={[THREE.MathUtils.degToRad(-18), THREE.MathUtils.degToRad(25), 0]}
      scale={1.18}
    >
      <Center>
        <primitive object={scene} />
      </Center>
    </group>
  );
}

function Atmosphere() {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.y += 0.0015;

    const mat = ref.current.material as THREE.MeshBasicMaterial;
    mat.opacity = 0.13 + Math.sin(state.clock.elapsedTime * 0.8) * 0.015;
  });

  return (
    <mesh ref={ref} scale={1.12}>
      <sphereGeometry args={[1, 64, 64]} />
      <meshBasicMaterial
        color="#6fd3ff"
        transparent
        opacity={0.13}
        side={THREE.BackSide}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}

function Loader() {
  return (
    <Html center>
      <div className="rounded-full border border-white/10 bg-black/60 px-4 py-2 text-xs uppercase tracking-[0.22em] text-cyan-100 backdrop-blur-xl">
        Loading earth...
      </div>
    </Html>
  );
}

export default function RegisterEarthShowcase3D({
  modelPath = "/models/earth/earth.glb",
}: RegisterEarthShowcase3DProps) {
  return (
    <div className="relative h-[560px] w-full overflow-hidden rounded-[2.5rem] border border-white/12 bg-black shadow-[0_35px_120px_rgba(0,0,0,0.72)]">
      {/* softer overlay - no red tint */}
      <div className="pointer-events-none absolute inset-0 z-10 rounded-[2.5rem] bg-[radial-gradient(circle_at_50%_18%,rgba(255,255,255,0.05),transparent_24%),radial-gradient(circle_at_20%_30%,rgba(56,189,248,0.08),transparent_28%),radial-gradient(circle_at_80%_70%,rgba(14,165,233,0.06),transparent_28%),linear-gradient(180deg,rgba(0,0,0,0.02),rgba(0,0,0,0.38))]" />

      <div className="pointer-events-none absolute left-6 top-6 z-20 rounded-full border border-white/10 bg-black/45 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-white/75 backdrop-blur-xl">
        Live Earth Core
      </div>

      <div className="pointer-events-none absolute right-6 top-6 z-20 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-100 backdrop-blur-xl">
        Secure Orbit
      </div>

      <div className="pointer-events-none absolute left-1/2 top-[72px] z-20 -translate-x-1/2 rounded-full border border-white/10 bg-black/45 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.26em] text-white/65 backdrop-blur-xl">
        Onboarding Planet
      </div>

      <Canvas
        dpr={[1.5, 2.4]}
        camera={{ position: [0, 0.15, 4.2], fov: 30, near: 0.01, far: 100 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl }) => {
          gl.outputColorSpace = THREE.SRGBColorSpace;
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.0;
        }}
      >
        <color attach="background" args={["#02060d"]} />

        {/* more realistic neutral lighting */}
        <ambientLight intensity={0.18} />

        {/* sunlight */}
        <directionalLight
          position={[-6, 3.5, 5]}
          intensity={4.2}
          color="#fff3cf"
        />

        {/* blue fill */}
        <directionalLight
          position={[4, -1.5, 3]}
          intensity={0.8}
          color="#6cc8ff"
        />

        {/* rim light */}
        <pointLight position={[0, 0, -5]} intensity={0.45} color="#7dd3fc" />

        <Suspense fallback={<Loader />}>
          <Stars
            radius={70}
            depth={32}
            count={1100}
            factor={2.2}
            saturation={0}
            fade
            speed={0.18}
          />

          <Bounds fit clip observe margin={1.08}>
            <group>
              <EarthModel modelPath={modelPath} />
              <Atmosphere />
            </group>
          </Bounds>
<Environment preset="night" />
        </Suspense>

        <OrbitControls
          enablePan={false}
          enableZoom={false}
          autoRotate
          autoRotateSpeed={0.35}
          minPolarAngle={Math.PI / 2.4}
          maxPolarAngle={Math.PI / 1.8}
        />
      </Canvas>

      {/* very soft bloom-like base glow */}
      <div className="pointer-events-none absolute bottom-10 left-1/2 z-20 h-20 w-56 -translate-x-1/2 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-9 left-1/2 z-20 h-8 w-44 -translate-x-1/2 rounded-full border border-cyan-200/10 bg-cyan-200/5" />
    </div>
  );
}

useGLTF.preload("/models/earth/earth.glb");