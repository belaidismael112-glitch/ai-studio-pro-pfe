"use client";

import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  Float,
  Html,
  PresentationControls,
  useAnimations,
  useGLTF,
} from "@react-three/drei";

type RegisterBeingRobot3DProps = {
  activeField: "name" | "email" | "password" | "confirmPassword" | null;
  success?: boolean;
  isLoading?: boolean;
};

const MODEL_PATH = "/models/ben-robot/ben_treasure_planet.glb";

export function RegisterBeingRobot3D({
  activeField,
  success = false,
  isLoading = false,
}: RegisterBeingRobot3DProps) {
  return (
    <div className="relative hidden h-[620px] w-full max-w-[540px] items-center justify-center overflow-hidden rounded-[2.4rem] border border-white/10 bg-black/45 shadow-[0_35px_120px_rgba(0,0,0,0.72)] backdrop-blur-2xl lg:flex">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(34,211,238,0.12),transparent_32%),radial-gradient(circle_at_52%_85%,rgba(217,70,239,0.12),transparent_40%)]" />
      <div className="absolute inset-0 opacity-[0.045] [background-image:linear-gradient(rgba(255,255,255,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:44px_44px]" />

      <div className="pointer-events-none absolute inset-0">
        <span className="absolute left-[18%] top-[18%] h-1 w-1 rounded-full bg-white/70 shadow-[0_0_12px_rgba(255,255,255,0.8)]" />
        <span className="absolute left-[72%] top-[19%] h-1 w-1 rounded-full bg-cyan-100/70 shadow-[0_0_14px_rgba(34,211,238,0.8)]" />
        <span className="absolute left-[82%] top-[42%] h-1.5 w-1.5 rounded-full bg-white/80 shadow-[0_0_16px_rgba(255,255,255,0.9)]" />
        <span className="absolute left-[16%] top-[62%] h-1 w-1 rounded-full bg-fuchsia-100/70 shadow-[0_0_14px_rgba(217,70,239,0.8)]" />
        <span className="absolute left-[66%] top-[72%] h-1 w-1 rounded-full bg-white/60 shadow-[0_0_10px_rgba(255,255,255,0.7)]" />
      </div>

      <div className="pointer-events-none absolute right-12 top-16 h-px w-32 rotate-[-28deg] bg-gradient-to-r from-transparent via-cyan-200/80 to-transparent opacity-70 shadow-[0_0_18px_rgba(34,211,238,0.75)] animate-[registerMeteorOne_4.6s_ease-in-out_infinite]" />
      <div className="pointer-events-none absolute right-4 top-28 h-px w-24 rotate-[-28deg] bg-gradient-to-r from-transparent via-fuchsia-200/70 to-transparent opacity-60 shadow-[0_0_16px_rgba(217,70,239,0.65)] animate-[registerMeteorTwo_6.2s_ease-in-out_infinite]" />

      <div className="absolute left-6 top-5 z-20 rounded-full border border-white/10 bg-black/35 px-4 py-2 text-[10px] uppercase tracking-[0.24em] text-white/70 backdrop-blur-xl">
        Live Onboarding Bot
      </div>

      <div className="absolute right-6 top-5 z-20 rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-4 py-2 text-[10px] uppercase tracking-[0.24em] text-cyan-100/75 backdrop-blur-xl">
        Drag control
      </div>

      <Canvas
        shadows
        camera={{ position: [0, 1.12, 7.05], fov: 30 }}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: "high-performance",
        }}
        className="relative z-10"
      >
        <color attach="background" args={["#000000"]} />

        <ambientLight intensity={1.18} />
        <directionalLight position={[3, 5, 4]} intensity={1.75} castShadow />

        <pointLight
          position={[-3.2, 2.4, 3.2]}
          intensity={2.25}
          color="#22d3ee"
        />

        <pointLight
          position={[3.2, 2.2, 3.2]}
          intensity={2.0}
          color={success ? "#34d399" : "#d946ef"}
        />

        <spotLight
          position={[0, 6, 4]}
          angle={0.42}
          penumbra={0.8}
          intensity={2.35}
          color="#ffffff"
          castShadow
        />

        <Suspense
          fallback={
            <Html center>
              <div className="rounded-xl border border-white/10 bg-black/55 px-4 py-2 text-sm text-white/70 backdrop-blur-xl">
                Loading 3D robot...
              </div>
            </Html>
          }
        >
          <PresentationControls
            global
            cursor
            speed={1.15}
            zoom={0.86}
            rotation={[0, 0, 0]}
            polar={[-0.25, 0.25]}
            azimuth={[-0.75, 0.75]}
            config={{ mass: 2.2, tension: 230 }}
            snap={{ mass: 2.2, tension: 150 }}
          >
            <Float speed={1.75} rotationIntensity={0.09} floatIntensity={0.28}>
              <RegisterRobotModel
                activeField={activeField}
                success={success}
                isLoading={isLoading}
              />
            </Float>
          </PresentationControls>

          <SpaceDust success={success} />

          <Environment preset="city" />

          <ContactShadows
            position={[0, -1.45, 0]}
            opacity={0.16}
            scale={4.4}
            blur={2.8}
            far={4}
            color={success ? "#34d399" : "#22d3ee"}
          />
        </Suspense>
      </Canvas>

      <AtmosphericBottomFX success={success} />

      <style jsx global>{`
        @keyframes registerMeteorOne {
          0% {
            transform: translate3d(40px, -25px, 0) rotate(-28deg);
            opacity: 0;
          }
          18% {
            opacity: 0.85;
          }
          48% {
            transform: translate3d(-120px, 70px, 0) rotate(-28deg);
            opacity: 0;
          }
          100% {
            opacity: 0;
          }
        }

        @keyframes registerMeteorTwo {
          0% {
            transform: translate3d(30px, -18px, 0) rotate(-28deg);
            opacity: 0;
          }
          28% {
            opacity: 0.75;
          }
          58% {
            transform: translate3d(-105px, 62px, 0) rotate(-28deg);
            opacity: 0;
          }
          100% {
            opacity: 0;
          }
        }

        @keyframes registerNebulaPulse {
          0%,
          100% {
            transform: translateX(-50%) scale(1);
            opacity: 0.48;
          }
          50% {
            transform: translateX(-50%) scale(1.08);
            opacity: 0.78;
          }
        }

        @keyframes registerNebulaFloat {
          0%,
          100% {
            transform: translateX(-50%) translateY(0px);
            opacity: 0.38;
          }
          50% {
            transform: translateX(-50%) translateY(-8px);
            opacity: 0.68;
          }
        }

        @keyframes registerTwinkleSoft {
          0%,
          100% {
            opacity: 0.35;
            transform: scale(1);
          }
          50% {
            opacity: 1;
            transform: scale(1.25);
          }
        }
      `}</style>
    </div>
  );
}

function RegisterRobotModel({
  activeField,
  success,
  isLoading,
}: {
  activeField: "name" | "email" | "password" | "confirmPassword" | null;
  success: boolean;
  isLoading: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Object3D | null>(null);
  const leftEyeRef = useRef<THREE.Object3D | null>(null);
  const rightEyeRef = useRef<THREE.Object3D | null>(null);

  const { scene, animations } = useGLTF(MODEL_PATH);
  const { actions } = useAnimations(animations, groupRef);

  const normalizedScene = useMemo(() => {
    const clone = scene.clone(true);

    clone.traverse((object: any) => {
      const name = `${object.name || ""}`.toLowerCase();

      if (object.isMesh) {
        object.castShadow = true;
        object.receiveShadow = true;

        if (object.material) {
          const material = object.material.clone();

          if ("metalness" in material) {
            material.metalness = Math.max(material.metalness || 0, 0.18);
          }

          if ("roughness" in material) {
            material.roughness = Math.min(material.roughness ?? 0.6, 0.5);
          }

          object.material = material;
        }
      }

      if (
        !headRef.current &&
        (name.includes("head") || name.includes("neck") || name.includes("face"))
      ) {
        headRef.current = object;
      }

      if (
        !leftEyeRef.current &&
        (name.includes("lefteye") ||
          name.includes("eye_l") ||
          name.includes("eye.left") ||
          name.includes("left_eye"))
      ) {
        leftEyeRef.current = object;
      }

      if (
        !rightEyeRef.current &&
        (name.includes("righteye") ||
          name.includes("eye_r") ||
          name.includes("eye.right") ||
          name.includes("right_eye"))
      ) {
        rightEyeRef.current = object;
      }
    });

    clone.updateMatrixWorld(true);

    const box = new THREE.Box3().setFromObject(clone);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();

    box.getSize(size);
    box.getCenter(center);

    const maxAxis = Math.max(size.x, size.y, size.z) || 1;
    const scale = 1.98 / maxAxis;

    clone.position.sub(center);
    clone.scale.setScalar(scale);

    return clone;
  }, [scene]);

  useEffect(() => {
    const actionList = Object.values(actions || {}) as any[];

    if (!actionList.length) return;

    actionList.forEach((action) => {
      if (!action) return;

      action.reset().fadeIn(0.35).play();
      action.timeScale = success ? 1.15 : isLoading ? 0.95 : 0.72;
    });

    return () => {
      actionList.forEach((action) => action?.fadeOut(0.25));
    };
  }, [actions, isLoading, success]);

  useFrame((state) => {
    const time = state.clock.elapsedTime;
    const mouseX = state.mouse.x;
    const mouseY = state.mouse.y;

    const targetRotationY =
      success
        ? Math.sin(time * 0.8) * 0.42
        : activeField === "name"
        ? -0.5
        : activeField === "email"
        ? -0.7
        : activeField === "password" || activeField === "confirmPassword"
        ? -0.62
        : Math.sin(time * 0.45) * 0.22;

    const targetRotationX =
      activeField === "password" || activeField === "confirmPassword"
        ? 0.12
        : activeField === "email"
        ? -0.02
        : Math.sin(time * 0.38) * 0.035;

    if (groupRef.current) {
      groupRef.current.position.y = THREE.MathUtils.lerp(
        groupRef.current.position.y,
        Math.sin(time * 1.15) * 0.055,
        0.05
      );

      groupRef.current.rotation.y = THREE.MathUtils.lerp(
        groupRef.current.rotation.y,
        targetRotationY,
        0.045
      );

      groupRef.current.rotation.x = THREE.MathUtils.lerp(
        groupRef.current.rotation.x,
        targetRotationX,
        0.04
      );

      const pulse = success
        ? Math.sin(time * 5) * 0.018
        : isLoading
        ? Math.sin(time * 4) * 0.012
        : 0;

      groupRef.current.scale.setScalar(1 + pulse);
    }

    if (headRef.current) {
      headRef.current.rotation.y = THREE.MathUtils.lerp(
        headRef.current.rotation.y,
        activeField ? -0.24 : mouseX * 0.18,
        0.07
      );

      headRef.current.rotation.x = THREE.MathUtils.lerp(
        headRef.current.rotation.x,
        activeField === "password" || activeField === "confirmPassword"
          ? 0.15
          : -mouseY * 0.08,
        0.07
      );
    }

    const eyeScaleY =
      activeField === "password" || activeField === "confirmPassword"
        ? 0.16
        : 1;

    [leftEyeRef.current, rightEyeRef.current].forEach((eye) => {
      if (!eye) return;

      eye.scale.y = THREE.MathUtils.lerp(eye.scale.y, eyeScaleY, 0.12);

      eye.rotation.y = THREE.MathUtils.lerp(
        eye.rotation.y,
        activeField ? -0.08 : mouseX * 0.12,
        0.08
      );

      eye.rotation.x = THREE.MathUtils.lerp(
        eye.rotation.x,
        activeField === "password" || activeField === "confirmPassword"
          ? 0.16
          : -mouseY * 0.08,
        0.08
      );
    });
  });

  return (
    <group ref={groupRef} position={[0, -0.36, 0]}>
      <primitive object={normalizedScene} />
    </group>
  );
}

function SpaceDust({ success }: { success: boolean }) {
  return null;
}

function AtmosphericBottomFX({ success }: { success: boolean }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 h-[180px] overflow-hidden">
      <div
        className={`absolute left-1/2 bottom-2 h-[90px] w-[360px] -translate-x-1/2 rounded-full blur-3xl animate-[registerNebulaPulse_8s_ease-in-out_infinite] ${
          success ? "bg-emerald-400/12" : "bg-cyan-400/10"
        }`}
      />

      <div className="absolute left-[48%] bottom-4 h-[110px] w-[260px] -translate-x-1/2 rounded-full bg-fuchsia-500/10 blur-3xl animate-[registerNebulaFloat_10s_ease-in-out_infinite]" />

      <div className="absolute left-1/2 bottom-12 h-px w-[230px] -translate-x-1/2 bg-gradient-to-r from-transparent via-cyan-200/35 to-transparent blur-[1px]" />

      <div className="absolute inset-x-0 bottom-0 h-28 bg-[radial-gradient(circle_at_50%_100%,rgba(34,211,238,0.08),transparent_42%),radial-gradient(circle_at_50%_100%,rgba(217,70,239,0.06),transparent_55%)]" />

      <span className="absolute left-[16%] bottom-[52px] h-1 w-1 rounded-full bg-white/70 shadow-[0_0_10px_rgba(255,255,255,0.8)] animate-[registerTwinkleSoft_3.5s_ease-in-out_infinite]" />

      <span className="absolute left-[28%] bottom-[118px] h-1 w-1 rounded-full bg-cyan-200/70 shadow-[0_0_10px_rgba(34,211,238,0.8)] animate-[registerTwinkleSoft_4.2s_ease-in-out_infinite]" />

      <span className="absolute right-[21%] bottom-[78px] h-1.5 w-1.5 rounded-full bg-fuchsia-200/70 shadow-[0_0_12px_rgba(217,70,239,0.8)] animate-[registerTwinkleSoft_4.8s_ease-in-out_infinite]" />
    </div>
  );
}

useGLTF.preload(MODEL_PATH);