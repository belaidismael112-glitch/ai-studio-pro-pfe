"use client";

import React from "react";

export default function RegisterEarthSketchfabShowcase() {
  return (
    <div className="relative mx-auto flex h-[560px] w-[560px] items-center justify-center">
      {/* outer glow */}
      <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle,rgba(59,130,246,0.18)_0%,rgba(168,85,247,0.10)_35%,rgba(0,0,0,0)_70%)] blur-3xl" />

      {/* circular earth container */}
      <div className="relative h-[480px] w-[480px] overflow-hidden rounded-full bg-transparent shadow-[0_25px_80px_rgba(0,0,0,0.45)]">
        <iframe
          title="Earth Sketchfab"
          src="https://sketchfab.com/models/5ce4b1465c83432d9bb7e3c30232c02b/embed?autostart=1&preload=1&transparent=1&ui_infos=0&ui_controls=0&ui_stop=0&ui_hint=0&ui_watermark=0&ui_watermark_link=0&ui_settings=0&ui_help=0&ui_ar=0&ui_inspector=0&ui_annotations=0"
          allow="autoplay; fullscreen; xr-spatial-tracking"
          allowFullScreen
          className="absolute left-1/2 top-1/2 h-[170%] w-[170%] -translate-x-1/2 -translate-y-1/2 border-0"
        />

        {/* subtle vignette */}
        <div className="pointer-events-none absolute inset-0 rounded-full shadow-[inset_0_0_60px_rgba(0,0,0,0.25)]" />
      </div>
    </div>
  );
}