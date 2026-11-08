'use client';

import React, { useState } from 'react';
import VideoLibrary from '@/components/VideoLibrary';
import VideoBatchUploader from '@/components/VideoBatchUploader';
import Link from 'next/link';

export default function DashboardPage() {
  const [view, setView] = useState<'library' | 'upload'>('library');

  return (
    <div className="py-6 space-y-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Workspace Dashboard</h1>
          <p className="text-slate-400 mt-1">Manage your video library and process new content</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setView(view === 'library' ? 'upload' : 'library')}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium"
          >
            {view === 'library' ? 'New Upload' : 'View Library'}
          </button>
          <Link
            href="/"
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium"
          >
            Home
          </Link>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        {view === 'upload' ? (
          <VideoBatchUploader />
        ) : (
          <VideoLibrary />
        )}
      </div>
    </div>
  );
}
