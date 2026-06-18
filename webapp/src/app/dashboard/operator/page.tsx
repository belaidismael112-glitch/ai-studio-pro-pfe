"use client";

import AIStudioOperatorLive from "@/components/ai-operator/ai-studio-operator-live";
import { useAuth } from "@/hooks/useAuth";

export default function OperatorPage() {
  useAuth();
  return <AIStudioOperatorLive />;
}
