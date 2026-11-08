'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  getVideoResult,
  getDownloadUrl,
  getStreamVideoUrl,
  getStreamAudioUrl,
  getStreamTranscriptUrl
} from '@/lib/api';
import { VideoResultResponse } from '@/lib/types';
import AccessibleVideoPlayer from '@/components/AccessibleVideoPlayer';
import DownloadButton from '@/components/DownloadButton';
import ComplianceReport, { ComplianceLevel } from '@/components/ComplianceReport';

interface DescriptionCoverageMetrics {
  totalSegments: number;
  describedSegments: number;
  coverage: number;
}

interface SpeechOverlapMetrics {
  totalSpeechDuration: number;
  overlappingDuration: number;
  overlapPercentage: number;
}

interface PauseUtilizationMetrics {
  totalPauseTime: number;
  totalDuration: number;
  pauseUtilization: number;
}

interface NarrationDensityMetrics {
  totalNarrationWords: number;
  totalAudioDuration: number;
  wordsPerMinute: number;
}

interface ComplianceMetrics {
  descriptionCoverage: DescriptionCoverageMetrics;
  speechOverlap: SpeechOverlapMetrics;
  pauseUtilization: PauseUtilizationMetrics;
  narrationDensity: NarrationDensityMetrics;
  wcagLevel: ComplianceLevel;
}

export default function ResultPage() {
  const params = useParams();
  const router = useRouter();
  const videoId = params?.videoId as string;

  const [result, setResult] = useState<VideoResultResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [complianceScore, setComplianceScore] = useState<number>(0);

  useEffect(() => {
    if (!videoId) return;

    const fetchResult = async () => {
      try {
        setLoading(true);
        const data = await getVideoResult(videoId);
        setResult(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load video result');
      } finally {
        setLoading(false);
      }
    };

    fetchResult();
  }, [videoId]);

  useEffect(() => {
    if (!result) return;

    // Calculate accessibility score based on result data
    let score = 0;

    // Calculate description coverage
    const totalSegments = result.descriptions.length;
    const describedSegments = result.descriptions.filter(d => d.status === 'COMPLETED').length;
    const descriptionCoverage = totalSegments > 0 ? (describedSegments / totalSegments) * 100 : 0;

    // Scoring based on result data
    score += Math.min(40, descriptionCoverage);

    // Score for speech segments presence
    if (result.speech_segments.length > 0) score += 20;

    // Score for available streams
    const availableStreams = [result.final_video_url, result.audio_description_url, result.transcript_url].filter(Boolean).length;
    score += (availableStreams * 10);

    const normalizedScore = Math.min(100, Math.max(0, score));
    setComplianceScore(normalizedScore);
  }, [result]);

  if (loading) {
    return (
      <div className="py-20 text-center space-y-4">
        <div className="text-4xl animate-bounce">⏳</div>
        <p className="text-slate-400">Loading accessible media...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="py-12 max-w-xl mx-auto bg-rose-950/40 border border-rose-800 p-8 rounded-xl text-center space-y-4">
        <h2 className="text-xl font-bold text-rose-300">Result Not Available</h2>
        <p className="text-sm text-slate-400">{error || 'Video result could not be retrieved.'}</p>
        <button
          onClick={() => router.push('/')}
          className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm"
        >
          Return Home
        </button>
      </div>
    );
  }

  const videoStreamUrl = getStreamVideoUrl(videoId);
  const audioStreamUrl = getStreamAudioUrl(videoId);
  const transcriptUrl = getStreamTranscriptUrl(videoId);
  const fullDownloadUrl = getDownloadUrl(videoId);

  // Calculate compliance metrics
  const calculateComplianceMetrics = (): ComplianceMetrics => {
    const descriptionCoverage: DescriptionCoverageMetrics = {
      totalSegments: result.descriptions.length,
      describedSegments: result.descriptions.filter(d => d.status === 'COMPLETED').length,
      coverage: result.descriptions.length > 0 ? (result.descriptions.filter(d => d.status === 'COMPLETED').length / result.descriptions.length) * 100 : 0
    };

    const speechOverlap: SpeechOverlapMetrics = {
      totalSpeechDuration: result.speech_segments.reduce((sum, segment) => sum + (segment.end - segment.start), 0),
      overlappingDuration: 0,
      overlapPercentage: 0
    };

    const pauseUtilization: PauseUtilizationMetrics = {
      totalPauseTime: 0,
      totalDuration: 0,
      pauseUtilization: 0
    };

    const narrationDensity: NarrationDensityMetrics = {
      totalNarrationWords: result.descriptions.reduce((sum, desc) => sum + desc.text.split(' ').length, 0),
      totalAudioDuration: 0,
      wordsPerMinute: 0
    };

    // Determine WCAG level based on compliance score
    let wcagLevel: 'AAA' | 'AA' | 'A' | 'Non-compliant';
    if (complianceScore >= 90) wcagLevel = 'AAA';
    else if (complianceScore >= 70) wcagLevel = 'AA';
    else if (complianceScore >= 40) wcagLevel = 'A';
    else wcagLevel = 'Non-compliant';

    return {
      descriptionCoverage,
      speechOverlap,
      pauseUtilization,
      narrationDensity,
      wcagLevel
    };
  };

  const complianceMetrics = calculateComplianceMetrics();

  return (
    <div className="py-6 space-y-8 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800 rounded">
              ACCESSIBLE OUTPUT READY
            </span>
            <span className="text-xs text-slate-500 font-mono">ID: {videoId}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white mt-1">
            Accessible Video Playback
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <DownloadButton
            label="Download Accessible MP4"
            url={fullDownloadUrl}
            filename={`accessible_${videoId}.mp4`}
            variant="primary"
          />
        </div>
      </div>

      {/* Video Player */}
      <AccessibleVideoPlayer
        videoStreamUrl={videoStreamUrl}
        masterStreamUrl={audioStreamUrl}
        descriptions={result.descriptions}
        speechSegments={result.speech_segments}
      />

      {/* Audio description player & download options */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3">
          <h3 className="font-semibold text-white text-sm flex items-center gap-2">
            <span>🎧</span> Separate Narration Track
          </h3>
          <p className="text-xs text-slate-400">
            Standalone visual description audio track for accessibility devices and screen readers.
          </p>
          <div className="pt-2">
            <DownloadButton
              label="Download Audio Track"
              url={audioStreamUrl}
              filename={`audio_description_${videoId}.wav`}
              icon="🎵"
            />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3">
          <h3 className="font-semibold text-white text-sm flex items-center gap-2">
            <span>📄</span> Dialogue & Timestamp Transcript
          </h3>
          <p className="text-xs text-slate-400">
            Full timestamped transcript extracted from the original audio via Gnani AI STT.
          </p>
          <div className="pt-2">
            <DownloadButton
              label="Download Transcript JSON"
              url={transcriptUrl}
              filename={`transcript_${videoId}.json`}
              icon="📋"
            />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3">
          <h3 className="font-semibold text-white text-sm flex items-center gap-2">
            <span>🚀</span> Process Another Video
          </h3>
          <p className="text-xs text-slate-400">
            Upload another video to generate AI audio descriptions.
          </p>
          <div className="pt-2">
            <button
              onClick={() => router.push('/')}
              className="w-full py-2.5 px-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition border border-slate-700"
            >
              Upload New Video
            </button>
          </div>
        </div>
      </div>

      {/* Generated Descriptions & Speech Segments List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl space-y-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <span>👁️</span> Generated Audio Descriptions ({result.descriptions.length})
          </h3>
          <div className="max-h-60 overflow-y-auto space-y-2 pr-2 text-xs">
            {result.descriptions.length === 0 ? (
              <p className="text-slate-500 italic">No descriptions generated.</p>
            ) : (
              result.descriptions.map((d, i) => (
                <div key={i} className="p-2.5 bg-slate-950 rounded border border-slate-800">
                  <div className="flex justify-between text-indigo-400 font-mono mb-1">
                    <span>{d.start.toFixed(1)}s - {d.end.toFixed(1)}s</span>
                    <span className="text-slate-500 uppercase">{d.status}</span>
                  </div>
                  <p className="text-slate-200">{d.text}</p>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl space-y-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <span>🗣️</span> Dialogue Segments ({result.speech_segments.length})
          </h3>
          <div className="max-h-60 overflow-y-auto space-y-2 pr-2 text-xs">
            {result.speech_segments.length === 0 ? (
              <p className="text-slate-500 italic">No dialogue detected (non-speech audio).</p>
            ) : (
              result.speech_segments.map((s, i) => (
                <div key={i} className="p-2.5 bg-slate-950 rounded border border-slate-800">
                  <div className="text-emerald-400 font-mono mb-1">
                    {s.start.toFixed(1)}s - {s.end.toFixed(1)}s
                  </div>
                  <p className="text-slate-300 italic">"{s.text}"</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Compliance Report */}
      <ComplianceReport
        accessibilityScore={complianceScore}
        wcagLevel={complianceMetrics.wcagLevel}
        descriptionCoverage={complianceMetrics.descriptionCoverage}
        speechOverlap={complianceMetrics.speechOverlap}
        pauseUtilization={complianceMetrics.pauseUtilization}
        narrationDensity={complianceMetrics.narrationDensity}
      />
    </div>
  );
}