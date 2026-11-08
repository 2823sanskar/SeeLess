export interface VideoUploadResponse {
  video_id: string;
  job_id: string;
  status: string;
  filename: string;
}

export interface ProcessingStatusResponse {
  video_id: string;
  status: string;
  current_step: string;
  progress: number;
  error?: string | null;
}

export interface DescriptionItem {
  id?: string;
  start: number;
  end: number;
  text: string;
  priority: number;
  status: string;
}

export interface SpeechSegmentItem {
  start: number;
  end: number;
  text?: string;
}

export interface VideoResultResponse {
  video_id: string;
  status: string;
  final_video_url?: string | null;
  audio_description_url?: string | null;
  transcript_url?: string | null;
  descriptions: DescriptionItem[];
  speech_segments: SpeechSegmentItem[];
}

