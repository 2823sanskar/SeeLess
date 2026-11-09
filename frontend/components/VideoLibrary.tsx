'use client';

import React, { useEffect, useState } from 'react';
import { getVideoList, bulkExport } from '@/lib/api';
import Link from 'next/link';

interface VideoSummary {
  id: string;
  batch_id?: string | null;
  original_filename: string;
  duration?: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  current_step?: string | null;
  progress: number;
  description_count: number;
  speech_segment_count: number;
  has_accessible_video: boolean;
  has_audio_description: boolean;
  has_transcript: boolean;
}

interface VideoListResponse {
  items: VideoSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface VideoLibraryProps {
  onExport?: (videoIds: string[]) => void;
}

export default function VideoLibrary({ onExport }: VideoLibraryProps) {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 20;

  useEffect(() => {
    fetchVideos();
  }, [search, statusFilter, page]);

  const fetchVideos = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (statusFilter !== 'ALL') params.set('status', statusFilter);
      params.set('page', page.toString());
      params.set('page_size', pageSize.toString());

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/videos?${params.toString()}`);

      if (!res.ok) {
        throw new Error(`Server error: ${res.status} ${res.statusText}`);
      }

      const data: VideoListResponse = await res.json();
      setVideos(data.items);
      setTotal(data.total);
    } catch (err: any) {
      const message = err.message?.includes('Failed to fetch')
        ? 'Backend server is unavailable. Please start the API server at http://localhost:8000.'
        : err.message || 'Failed to load videos.';
      setError(message);
      setVideos([]);
      setTotal(0);
      console.error('Failed to fetch videos:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleBulkExport = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/videos/bulk-export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_ids: Array.from(selectedIds), export_types: ['vtt', 'srt'] }),
      });
      if (!res.ok) {
        throw new Error(`Export failed: ${res.status} ${res.statusText}`);
      }
      if (onExport) onExport(Array.from(selectedIds));
    } catch (err: any) {
      console.error('Export failed:', err);
      alert(err.message || 'Export failed. Please try again.');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED': return 'bg-emerald-900/50 text-emerald-400 border-emerald-800';
      case 'FAILED': return 'bg-rose-900/50 text-rose-400 border-rose-800';
      case 'PROCESSING': return 'bg-indigo-900/50 text-indigo-400 border-indigo-800';
      default: return 'bg-slate-800/50 text-slate-400 border-slate-700';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search videos..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 placeholder-slate-500"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-200"
        >
          <option value="ALL">All Statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="PROCESSING">Processing</option>
          <option value="UPLOADED">Uploaded</option>
          <option value="FAILED">Failed</option>
        </select>
        {selectedIds.size > 0 && (
          <button
            onClick={handleBulkExport}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm"
          >
            Export {selectedIds.size} selected
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="text-3xl">⏳</div>
          <p className="text-slate-400">Loading...</p>
        </div>
      ) : error ? (
        <div className="text-center py-12">
          <div className="text-3xl mb-2">⚠️</div>
          <p className="text-rose-400">{error}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map((video) => (
            <div
              key={video.id}
              className={`p-4 rounded-xl border ${
                selectedIds.has(video.id)
                  ? 'border-indigo-500 bg-indigo-950/30'
                  : 'bg-slate-900/40 border-slate-800'
              }`}
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={selectedIds.has(video.id)}
                  onChange={() => handleSelect(video.id)}
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-white">{video.original_filename}</h3>
                    <span className={`px-2 py-0.5 text-xs font-semibold rounded ${getStatusColor(video.status)}`}>
                      {video.status}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">
                    {video.duration && <>⏱️ {video.duration.toFixed(1)}s&nbsp;</>}
                    {video.has_accessible_video && <span className="text-emerald-400">✓ Video ready</span>}
                  </div>
                </div>
              </div>
              {video.status === 'COMPLETED' && (
                <Link href={`/result/${video.id}`} className="mt-3 inline-block">
                  <span className="px-3 py-1 rounded bg-slate-800 text-slate-200 text-sm">View Result</span>
                </Link>
              )}
            </div>
          ))}
          {videos.length === 0 && !error && (
            <div className="text-center py-12 col-span-full">
              <h3 className="text-lg font-semibold text-white mb-2">No videos found</h3>
              <p className="text-slate-400">Upload your first video to get started.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
