'use client';

import React from 'react';

interface DownloadButtonProps {
  label: string;
  url: string;
  filename?: string;
  variant?: 'primary' | 'secondary';
  icon?: string;
}

export default function DownloadButton({
  label,
  url,
  filename,
  variant = 'secondary',
  icon = '⬇️'
}: DownloadButtonProps) {
  return (
    <a
      href={url}
      download={filename}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition ${
        variant === 'primary'
          ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30'
          : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
      }`}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </a>
  );
}

