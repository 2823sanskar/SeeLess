'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getProcessingStatus } from '@/lib/api';
import ProcessingStatus from '@/components/ProcessingStatus';

export default function ProcessingPage() {
  const params = useParams();
  const router = useRouter();
  const videoId = params?.videoId as string;

  const [status, setStatus] = useState<string>('PENDING');
  const [currentStep, setCurrentStep] = useState<string>('Initializing');
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) return;

    let intervalId: any = null;

    const checkStatus = async () => {
      try {
        const data = await getProcessingStatus(videoId);
        setStatus(data.status);
        setCurrentStep(data.current_step);
        setProgress(data.progress);
        setError(data.error || null);

        if (data.status === 'COMPLETED') {
          clearInterval(intervalId);
          setTimeout(() => {
            router.push(`/result/${videoId}`);
          }, 1500);
        } else if (data.status === 'FAILED') {
          clearInterval(intervalId);
        }
      } catch (err: any) {
        console.error('Status fetch error:', err);
      }
    };

    checkStatus();
    intervalId = setInterval(checkStatus, 2500);

    return () => clearInterval(intervalId);
  }, [videoId, router]);

  return (
    <div className="py-12 space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold text-white">Generating Audio Description</h1>
        <p className="text-slate-400 text-sm">
          Processing video ID <span className="font-mono text-indigo-400">{videoId}</span>
        </p>
      </div>

      <ProcessingStatus
        status={status}
        currentStep={currentStep}
        progress={progress}
        error={error}
      />

      {status === 'FAILED' && (
        <div className="text-center">
          <button
            onClick={() => router.push('/')}
            className="px-6 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm font-medium transition"
          >
            ← Upload another video
          </button>
        </div>
      )}
    </div>
  );
}

