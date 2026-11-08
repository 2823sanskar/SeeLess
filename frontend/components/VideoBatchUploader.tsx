'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

interface BatchUploadResponse {
  batch_id: string;
  total_uploaded: number;
  videos: {
    video_id: string;
    job_id: string;
    filename: string;
    status: string;
    duration?: number | null;
  }[];
}

interface VideoBatchUploaderProps {
  batchId?: string;
}

export default function VideoBatchUploader({ batchId }: VideoBatchUploaderProps) {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [batchResponse, setBatchResponse] = useState<BatchUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const fileArray = Array.from(e.target.files);
      const validFiles = fileArray.filter(f => 
        f.name.toLowerCase().endsWith('.mp4') && f.size <= 500 * 1024 * 1024
      );
      if (validFiles.length !== fileArray.length) {
        setError('Some files were skipped (must be MP4 under 500MB)');
      }
      setFiles(prev => [...prev, ...validFiles].slice(0, 10)); // Max 10 files
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      formData.append('auto_process', 'true');

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/videos/batch-upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await res.json() as BatchUploadResponse;
      setBatchResponse(data);

      // Navigate to processing view for first video as example
      if (data.videos.length > 0) {
        router.push(`/processing/${data.videos[0].video_id}`);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to upload');
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="w-full max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl">
      <div className="text-center space-y-2 mb-6">
        <h2 className="text-2xl font-bold tracking-tight text-white">Batch Upload Videos</h2>
        <p className="text-slate-400 text-sm">
          Upload multiple MP4 videos (up to 10 files, each under 500MB). All will be queued for processing.
        </p>
      </div>

      <div className="border-2 border-dashed border-slate-700 rounded-xl p-8 text-center mb-4">
        <input
          type="file"
          accept="video/mp4"
          multiple
          onChange={handleFileChange}
          disabled={uploading}
          className="w-full text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer disabled:opacity-50"
        />
      </div>

      {files.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Selected Files ({files.length})</h3>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {files.map((file, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-slate-950 rounded border border-slate-800">
                <div>
                  <p className="text-sm text-white">{file.name}</p>
                  <p className="text-xs text-slate-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                </div>
                <button
                  onClick={() => removeFile(idx)}
                  disabled={uploading}
                  className="text-slate-400 hover:text-rose-400"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-rose-950/50 border border-rose-800 text-rose-300 rounded-lg text-sm">
          ⚠️ {error}
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={files.length === 0 || uploading}
        className={`w-full py-3 px-6 rounded-lg font-semibold text-white transition ${
          files.length === 0 || uploading
            ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
            : 'bg-indigo-600 hover:bg-indigo-500 shadow-lg'
        }`}
      >
        {uploading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin">⏳</span>
            Uploading videos...
          </span>
        ) : (
          'Upload Batch & Process'
        )}
      </button>

      {batchResponse && (
        <div className="mt-6 p-4 bg-emerald-950/20 border border-emerald-800 rounded-lg">
          <h3 className="text-emerald-400 font-semibold mb-2">Batch Upload Complete</h3>
          <p className="text-sm text-slate-300">
            Successfully queued {batchResponse.total_uploaded} videos (ID: {batchResponse.batch_id.slice(0, 8)}...)
          </p>
        </div>
      )}
    </div>
  );
}
