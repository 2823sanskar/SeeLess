'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { getProcessingStatus } from '@/lib/api';

interface ProcessingStatusProps {
  videoId?: string;
  status?: string;
  currentStep?: string;
  progress?: number;
  error?: string | null;
}

const STAGES = [
  { label: 'Video uploaded', minProgress: 0 },
  { label: 'Extracting media', minProgress: 10 },
  { label: 'Detecting scenes', minProgress: 25 },
  { label: 'Analyzing audio (Gnani STT)', minProgress: 40 },
  { label: 'Analyzing visual events', minProgress: 55 },
  { label: 'Generating descriptions', minProgress: 65 },
  { label: 'Scheduling narration', minProgress: 75 },
  { label: 'Generating speech (Gnani TTS)', minProgress: 85 },
  { label: 'Assembling audio & video', minProgress: 92 },
  { label: 'Quality checks', minProgress: 96 },
  { label: 'Completed', minProgress: 100 },
];

export default function ProcessingStatus({
  videoId,
  status: propStatus,
  currentStep: propCurrentStep,
  progress: propProgress,
  error: propError,
}: ProcessingStatusProps) {
  const [internalStatus, setStatus] = React.useState<string>(propStatus || 'PENDING');
  const [internalCurrentStep, setCurrentStep] = React.useState<string>(propCurrentStep || '');
  const [internalProgress, setProgress] = React.useState<number>(propProgress || 0);
  const [internalError, setError] = React.useState<string | null>(propError || null);
  const router = useRouter();

  const status = propStatus !== undefined ? propStatus : internalStatus;
  const currentStep = propCurrentStep !== undefined ? propCurrentStep : internalCurrentStep;
  const progress = propProgress !== undefined ? propProgress : internalProgress;
  const error = propError !== undefined ? propError : internalError;

  React.useEffect(() => {
    if (!videoId) return;
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const data = await getProcessingStatus(videoId);
        if (cancelled) return;
        setStatus(data.status);
        setCurrentStep(data.current_step);
        setProgress(data.progress);
        setError(data.error || null);
        if (data.status === 'COMPLETED') {
          router.push(`/result/${videoId}`);
        }
      } catch (e:any) {
        if (cancelled) return;
        setError(e.message || 'Failed to fetch status');
      }
    };
    // Initial fetch
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [videoId, router]);
  const isFailed = status === 'FAILED';
  const isCompleted = status === 'COMPLETED';

  return (
    <div className="w-full max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Accessible Pipeline Status</h2>
          <p className="text-sm text-slate-400 mt-1">{currentStep || 'Initializing pipeline...'}</p>
        </div>
        <div className="text-right">
          <span className="text-2xl font-black text-indigo-400">{progress}%</span>
          <p className="text-xs font-semibold tracking-wider uppercase text-slate-500">{status}</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ${
            isFailed
              ? 'bg-rose-600'
              : isCompleted
              ? 'bg-emerald-500'
              : 'bg-indigo-600 animate-pulse'
          }`}
          style={{ width: `${Math.max(progress, 5)}%` }}
        />
      </div>

      {error && (
        <div className="p-4 bg-rose-950/60 border border-rose-800 text-rose-300 rounded-lg text-sm">
          <h4 className="font-bold mb-1">Processing Error Encountered:</h4>
          <p className="font-mono text-xs whitespace-pre-wrap">{error}</p>
        </div>
      )}

      {/* Stage Breakdown Checklist */}
      <div className="space-y-2 pt-4 border-t border-slate-800">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Pipeline Milestones
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
          {STAGES.map((s, idx) => {
            const isDone = progress >= s.minProgress && !isFailed;
            const isCurrent = progress >= s.minProgress && (idx === STAGES.length - 1 || progress < STAGES[idx + 1].minProgress) && !isFailed;

            return (
              <div
                key={s.label}
                className={`flex items-center gap-2 p-2 rounded border ${
                  isCurrent
                    ? 'border-indigo-500 bg-indigo-950/30 text-indigo-300 font-medium'
                    : isDone
                    ? 'border-slate-800 bg-slate-950/40 text-emerald-400'
                    : 'border-transparent text-slate-500'
                }`}
              >
                <span>{isDone ? '✓' : isCurrent ? '⏳' : '○'}</span>
                <span>{s.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

