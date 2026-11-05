import VideoUploader from '@/components/VideoUploader';

export default function HomePage() {
  return (
    <div className="space-y-12 py-8">
      <div className="text-center max-w-3xl mx-auto space-y-4">
        <div className="inline-block px-3 py-1 bg-indigo-950/80 border border-indigo-800 text-indigo-300 text-xs font-semibold rounded-full uppercase tracking-wider">
          Accessibility Intelligence
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          Visual Descriptions Without Interrupting Dialogue
        </h1>
        <p className="text-slate-400 text-base sm:text-lg">
          SeeLess analyzes on-screen actions, detects speech with Gnani AI STT, and schedules spoken visual descriptions into natural gaps using Gnani AI TTS.
        </p>
      </div>

      <VideoUploader />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto pt-6 border-t border-slate-900 text-slate-300 text-sm">
        <div className="bg-slate-900/40 p-5 rounded-xl border border-slate-800/60">
          <h3 className="font-semibold text-white mb-2 flex items-center gap-2">
            <span>🛡️</span> Original Dialogue Preserved
          </h3>
          <p className="text-slate-400 text-xs leading-relaxed">
            Actors’ speech, ambient audio, and music are never replaced or summarized. Narration only occupies safe natural intervals.
          </p>
        </div>

        <div className="bg-slate-900/40 p-5 rounded-xl border border-slate-800/60">
          <h3 className="font-semibold text-white mb-2 flex items-center gap-2">
            <span>🎙️</span> Gnani AI Audio Stack
          </h3>
          <p className="text-slate-400 text-xs leading-relaxed">
            Exclusive speech-to-text dialogue timestamping and high-fidelity text-to-speech narration synthesis via Gnani AI.
          </p>
        </div>

        <div className="bg-slate-900/40 p-5 rounded-xl border border-slate-800/60">
          <h3 className="font-semibold text-white mb-2 flex items-center gap-2">
            <span>👁️</span> Visual-Only Descriptions
          </h3>
          <p className="text-slate-400 text-xs leading-relaxed">
            Accurate, concise narration detailing character actions, gestures, and visual shifts that audio alone cannot convey.
          </p>
        </div>
      </div>
    </div>
  );
}

