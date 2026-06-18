"use client";

import AutonomousPlatformPro from "@/components/autonomous-platform-pro/autonomous-platform-pro";
import { useAuth } from "@/hooks/useAuth";

export default function AutonomousPlatformPage() {
  useAuth();
  return <AutonomousPlatformPro />;
}
