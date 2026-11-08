import {
  VideoUploadResponse,
  ProcessingStatusResponse,
  VideoResultResponse
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function uploadVideo(file: File): Promise<VideoUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/api/videos/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }

  return res.json();
}

export async function startProcessing(videoId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/videos/${videoId}/process`, {
    method: 'POST',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to start processing' }));
    throw new Error(err.detail || 'Failed to start processing');
  }

  return res.json();
}

export async function getProcessingStatus(videoId: string): Promise<ProcessingStatusResponse> {
  const res = await fetch(`${API_BASE}/api/videos/${videoId}/status`);

  if (!res.ok) {
    throw new Error('Failed to fetch status');
  }

  return res.json();
}

export async function getVideoResult(videoId: string): Promise<VideoResultResponse> {
  const res = await fetch(`${API_BASE}/api/videos/${videoId}/result`);

  if (!res.ok) {
    throw new Error('Failed to fetch result');
  }

  return res.json();
}

export function getDownloadUrl(videoId: string): string {
  return `${API_BASE}/api/videos/${videoId}/download`;
}

export function getStreamVideoUrl(videoId: string): string {
  return `${API_BASE}/api/videos/${videoId}/stream/video`;
}

export function getStreamAudioUrl(videoId: string): string {
  return `${API_BASE}/api/videos/${videoId}/stream/audio`;
}

export function getStreamTranscriptUrl(videoId: string): string {
  return `${API_BASE}/api/videos/${videoId}/stream/transcript`;
}

// Phase 6: Batch Upload
export async function uploadBatchVideos(files: File[]): Promise<any> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const res = await fetch(`${API_BASE}/api/videos/batch-upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Batch upload failed' }));
    throw new Error(err.detail || 'Batch upload failed');
  }

  return res.json();
}

// Phase 6: Video Library
export async function getVideoList(
  search?: string,
  status?: string,
  page: number = 1,
  pageSize: number = 20
): Promise<any> {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (status) params.set('status', status);
  params.set('page', page.toString());
  params.set('page_size', pageSize.toString());

  const res = await fetch(`${API_BASE}/api/videos?${params.toString()}`);

  if (!res.ok) {
    throw new Error('Failed to fetch video list');
  }

  return res.json();
}

// Phase 6: Bulk Export
export async function bulkExport(videoIds: string[], exportTypes: string[]): Promise<any> {
  const res = await fetch(`${API_BASE}/api/videos/bulk-export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ video_ids: videoIds, export_types: exportTypes }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Bulk export failed' }));
    throw new Error(err.detail || 'Bulk export failed');
  }

  return res.json();
}

