"use client";

import React, { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  Bounds,
  Center,
  ContactShadows,
  Environment,
  Float,
  Html,
  OrbitControls,
  useGLTF,
} from "@react-three/drei";
import * as THREE from "three";

type LoginCosmicShowcaseProps = {
  modelPath?: string;
};

function RealisticCosmicCell({
  modelPath = "/models/login-globe/cosmic_cell.glb",
}: LoginCosmicShowcaseProps) {
  const groupRef = useRef<THREE.Group>(null);
  const gltf = useGLTF(modelPath);

  const scene = useMemo(() => {
    const cloned = gltf.scene.clone(true);

    cloned.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;

      const mesh = child as THREE.Mesh;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.frustumCulled = false;

      const materials = Array.isArray(mesh.material)
        ? mesh.material
        : [mesh.material];

      materials.forEach((mat) => {
        const material = mat as THREE.MeshStandardMaterial;
        if (!material) return;

        // IMPORTANT:
        // Keep the original texture/material and do not override the model color.
        material.side = THREE.DoubleSide;
        material.toneMapped = true;

        // If a glass shell exists, keep it lighter so details stay visible.
        if (material.transparent || material.opacity < 1) {
          material.transparent = true;
          material.opacity = Math.min(material.opacity || 0.28, 0.24);
          material.depthWrite = false;
          material.roughness = 0.12;
          material.metalness = 0.05;
        } else {
          // Keep the material closer to realism, not cartoon.
          material.roughness = Math.min(material.roughness ?? 0.55, 0.55);
          material.metalness = Math.max(material.metalness ?? 0.05, 0.08);
        }

        material.needsUpdate = true;
      });
    });

    return cloned;
  }, [gltf.scene]);

  useFrame((state, delta) => {
    if (!groupRef.current) return;

    groupRef.current.rotation.y += delta * 0.16;
    groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.35) * 0.045;
    groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 0.7) * 0.04;
  });

  return (
    <Float speed={0.75} rotationIntensity={0.06} floatIntensity={0.15}>
      <group ref={groupRef} rotation={[0.08, -0.25, 0]}>
        <Center>
          <primitive object={scene} />
        </Center>
      </group>
    </Float>
  );
}

function Loader() {
  return (
    <Html center>
      <div className="rounded-full border border-white/10 bg-black/70 px-4 py-2 text-xs uppercase tracking-[0.24em] text-cyan-100 backdrop-blur-xl">
        Loading cosmic core...
      </div>
    </Html>
  );
}

export default function BrainTorusShowcase3D({
  modelPath = "/models/login-globe/cosmic_cell.glb",
}: LoginCosmicShowcaseProps) {
  return (
    <div className="relative h-[560px] w-full overflow-hidden rounded-[2.5rem] border border-white/12 bg-black shadow-[0_35px_120px_rgba(0,0,0,0.75)]">
      {/* glass overlay */}
      <div className="pointer-events-none absolute inset-0 z-10 rounded-[2.5rem] bg-[radial-gradient(circle_at_50%_38%,rgba(34,211,238,0.12),transparent_32%),radial-gradient(circle_at_50%_78%,rgba(217,70,239,0.14),transparent_36%),linear-gradient(180deg,rgba(0,0,0,0.02),rgba(0,0,0,0.60))]" />

      <div className="pointer-events-none absolute left-6 top-6 z-20 rounded-full border border-white/10 bg-black/45 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-white/75 backdrop-blur-xl">
        Live cosmic core
      </div>

      <div className="pointer-events-none absolute right-6 top-6 z-20 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-100 backdrop-blur-xl">
        Secure orbit
      </div>

      <div className="pointer-events-none absolute left-1/2 top-[72px] z-20 -translate-x-1/2 rounded-full border border-white/10 bg-white/[0.045] px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.26em] text-white/55 backdrop-blur-xl">
        Hologram Access
      </div>

      <Canvas
        shadows
        dpr={[1, 1.85]}
        camera={{
          position: [0, 0.12, 4.7],
          fov: 39,
          near: 0.01,
          far: 200,
        }}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: "high-performance",
        }}
        onCreated={({ gl }) => {
          gl.outputColorSpace = THREE.SRGBColorSpace;
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.08;
          gl.shadowMap.enabled = true;
          gl.shadowMap.type = THREE.PCFSoftShadowMap;
        }}
      >
        <color attach="background" args={["#000000"]} />

        {/* soft lights */}
        <ambientLight intensity={0.45} />

        <directionalLight
          position={[4, 5, 6]}
          intensity={2.5}
          color="#ffffff"
          castShadow
        />

        <spotLight
          position={[0, 4, 4.5]}
          angle={0.45}
          penumbra={0.65}
          intensity={3.8}
          color="#ffffff"
          castShadow
        />

        <pointLight position={[-3.4, 1.6, 2.8]} intensity={2.8} color="#d946ef" />
        <pointLight position={[3.2, -1.2, 2.6]} intensity={3.1} color="#22d3ee" />
        <pointLight position={[0, -2.2, 3.5]} intensity={1.8} color="#8b5cf6" />

        <Suspense fallback={<Loader />}>
          <Bounds fit clip observe margin={1.05}>
            <RealisticCosmicCell modelPath={modelPath} />
          </Bounds>
<ContactShadows
            position={[0, -2.05, 0]}
            opacity={0.34}
            scale={5.4}
            blur={2.9}
            far={4.8}
          />

          <Environment preset="city" />
        </Suspense>

        <OrbitControls
          enablePan={false}
          enableZoom={false}
          autoRotate
          autoRotateSpeed={0.25}
          minPolarAngle={Math.PI / 2.75}
          maxPolarAngle={Math.PI / 1.75}
        />
      </Canvas>

      <div className="pointer-events-none absolute bottom-8 left-1/2 z-20 h-20 w-64 -translate-x-1/2 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-9 left-1/2 z-20 h-8 w-48 -translate-x-1/2 rounded-full border border-cyan-200/15 bg-cyan-200/5" />
    </div>
  );
}

useGLTF.preload("/models/login-globe/cosmic_cell.glb");