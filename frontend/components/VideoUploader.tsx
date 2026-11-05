'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadVideo, startProcessing } from '@/lib/api';

export default function VideoUploader() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progressText, setProgressText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (!selected.name.toLowerCase().endsWith('.mp4')) {
        setError('Only MP4 videos are supported.');
        setFile(null);
        return;
      }
      if (selected.size > 500 * 1024 * 1024) {
        setError('File exceeds 500MB size limit.');
        setFile(null);
        return;
      }
      setError(null);
      setFile(selected);
    }
  };

  const handleUploadAndProcess = async () => {
    if (!file) return;

    try {
      setUploading(true);
      setError(null);
      setProgressText('Uploading MP4 video...');

      const uploadRes = await uploadVideo(file);
      setProgressText('Starting AI processing pipeline...');

      await startProcessing(uploadRes.video_id);

      router.push(`/processing/${uploadRes.video_id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to upload video');
      setUploading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl">
      <div className="text-center space-y-2 mb-6">
        <h2 className="text-2xl font-bold tracking-tight text-white">Upload Your Video</h2>
        <p className="text-slate-400 text-sm">
          Select an MP4 video (up to 500MB). Original soundtrack and dialogue are strictly preserved while Gnani AI audio descriptions are generated.
        </p>
      </div>

      <div className="border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-xl p-8 text-center transition cursor-pointer bg-slate-950/40 relative">
        <input
          type="file"
          accept="video/mp4"
          onChange={handleFileChange}
          disabled={uploading}
          className="absolute inset-0 opacity-0 cursor-pointer"
        />
        <div className="space-y-3 pointer-events-none">
          <div className="w-12 h-12 mx-auto rounded-full bg-indigo-950/60 flex items-center justify-center text-indigo-400 border border-indigo-800/50">
            🎬
          </div>
          {file ? (
            <div>
              <p className="text-sm font-medium text-emerald-400 font-mono">{file.name}</p>
              <p className="text-xs text-slate-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-slate-300 font-medium">Click or drag & drop an MP4 file here</p>
              <p className="text-xs text-slate-500">Supports standard MP4 with dialogue and audio</p>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 bg-rose-950/50 border border-rose-800 text-rose-300 rounded-lg text-sm">
          ⚠️ {error}
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <button
          onClick={handleUploadAndProcess}
          disabled={!file || uploading}
          className={`w-full py-3 px-6 rounded-lg font-semibold text-white transition flex items-center justify-center gap-2 ${
            !file || uploading
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-500 shadow-lg shadow-indigo-600/30'
          }`}
        >
          {uploading ? (
            <>
              <span className="animate-spin text-lg">⏳</span>
              <span>{progressText}</span>
            </>
          ) : (
            'Upload & Generate Accessible Video'
          )}
        </button>
      </div>
    </div>
  );
}

