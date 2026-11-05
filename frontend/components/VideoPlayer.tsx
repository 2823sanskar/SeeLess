'use client';

import React from 'react';

interface VideoPlayerProps {
  src: string;
  poster?: string;
}

export default function VideoPlayer({ src, poster }: VideoPlayerProps) {
  return (
    <div className="w-full rounded-xl overflow-hidden bg-black shadow-2xl border border-slate-800">
      <video
        controls
        playsInline
        preload="metadata"
        className="w-full aspect-video max-h-[540px] mx-auto object-contain bg-black"
        poster={poster}
      >
        <source src={src} type="video/mp4" />
        Your browser does not support HTML5 video playback.
      </video>
    </div>
  );
}

