'use client';

import VideoUploader from '@/components/VideoUploader';
import { Shield, Music, Eye, Info, Settings, Download, Mail, Phone, Link, Search, X, User, Code } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 overflow-x-hidden">

      {/* Decorative canvas element */}
      <canvas id="heroCanvas" className="absolute inset-0 overflow-hidden rounded-3xl" />
      <div className="absolute -inset-4 overflow-hidden rounded-3xl opacity-5">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-500/10 rounded-full animate-orbit-slow" aria-hidden="true" />
        <div className="absolute bottom-1/3 right-1/4 w-64 h-64 bg-emerald-500/10 rounded-full animate-orbit-reverse-slow" aria-hidden="true" />
      </div>

      {/* Hero Section */}
      <section className="relative pt-20 pb-16 px-4 sm:px-6 max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-12 items-center min-h-[600px]">

          <div>
            <span className="inline-block px-3 py-1 bg-indigo-950/80 border border-indigo-800 text-indigo-300 text-xs font-semibold rounded-full uppercase tracking-wider mb-6">
              Accessibility Intelligence
            </span>
            <h1 className="text-5xl sm:text-6xl font-extrabold text-white tracking-tight leading-tight mb-6">
              Visual Descriptions Without Interrupting Dialogue
            </h1>
            <p className="text-slate-400 text-lg sm:text-xl leading-relaxed mb-8 max-w-xl">
              SeeLess analyzes on-screen actions, detects speech with Gnani AI STT, and schedules spoken visual descriptions into natural gaps using Gnani AI TTS. Experience media accessibility redefined.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
              <a href="/dashboard" className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-400 text-white font-medium transition shadow-lg shadow-emerald-300/20 border border-emerald-400/30">
                <span>🎯</span>
                <span>Use Tool</span>
              </a>
              <a href="/about" className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition border border-slate-600/50">
                <span>Learn More</span>
              </a>
            </div>
          </div>

          {/* Visual abstraction - color blocks */}
          <div className="relative">
            <div className="relative rounded-3xl overflow-hidden bg-slate-800">
              <svg className="w-full h-full object-cover" viewBox="0 0 800 500" preserveAspectRatio="xMidYMidSlice">
                <rect width="800" height="500" fill="url(#grad1)" />
                <defs>
                  <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="indigo-600" />
                    <stop offset="100%" stop-color="emerald-600" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute bottom-0 left-0 right-0 p-8 bg-black/60">
                <h2 className="text-3xl font-bold text-white">SeeLess</h2>
                <p className="text-slate-400 text-sm mt-1">AI-Powered Audio Description Platform</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-24 px-4 sm:px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <span className="inline-block px-3 py-1 bg-indigo-950/80 border border-indigo-800 text-indigo-300 text-xs font-semibold rounded-full uppercase tracking-wider mb-4">
              How It Works
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              Three Steps to Accessible Media
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Step 1 */}
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 hover:border-emerald-500/50 transition-all duration-300 group">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center mb-4 group-hover:bg-emerald-500/30 transition-colors">
                <span>📤</span>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Upload Your Video</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Accepts MP4 files up to 500MB. Gnani AI STT transcribes dialogue automatically.
              </p>
            </div>

            {/* Step 2 */}
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 hover:border-indigo-500/50 transition-all duration-300 group">
              <div className="w-12 h-12 rounded-xl bg-indigo-500/20 flex items-center justify-center mb-4 group-hover:bg-indigo-500/30 transition-colors">
                <span>🧠</span>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">AI Processing</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Google Gemini analyzes scenes. Gnani AI TTS synthesizes descriptions. Scheduler prevents dialogue overlap.
              </p>
            </div>

            {/* Step 3 */}
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 hover:bg-indigo-500/10 transition-all duration-300 group">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center mb-4 group-hover:bg-emerald-500/30 transition-colors">
                <span>⬇️</span>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Download Results</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Accessible MP4 with narration track. WAV audio. Timestamped transcript. WCAG compliant.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Cards */}
      <section className="py-24 px-4 sm:px-6 bg-slate-950/50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard icon="🛡️" title="Original Dialogue Preserved" description="Actors' speech, ambient audio, and music are never replaced. Narration occupies safe natural intervals between dialogue turns." />
            <FeatureCard icon="🎙️" title="Gnani AI Audio Stack" description="Speech-to-text timestamping and high-fidelity TTS narration via Gnani AI timbre-v2.5 models." />
            <FeatureCard icon="👁️" title="Visual-Only Descriptions" description="Concise narration detailing character actions and visual shifts audio alone cannot convey." />
          </div>
        </div>
      </section>

      {/* Compliance Section */}
      <section className="py-16 px-4 sm:px-6">
        <div className="max-w-5xl mx-auto border-t border-b border-slate-800/60 pb-8 pt-8">
          <div className="text-center mb-8">
            <span className="inline-block px-4 py-1.5 rounded-full bg-emerald-600/20 text-emerald-400 border border-emerald-500 text-sm font-medium mb-2">
              WCAG 2.1 AA Compliant
            </span>
            <p className="text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">
              SeeLess meets WCAG 2.1 AA standards for audio description coverage, overlap compliance, and pause utilization.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4 justify-center">
            <div>
              <p className="text-4xl font-bold text-emerald-400">92%</p>
              <p className="text-slate-500">Description Coverage</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-amber-400">88%</p>
              <p className="text-slate-500">Narration Density</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative py-24 px-4 sm:px-6 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-900 via-amber-950 to-rust-900">
          <div className="absolute inset-0 bg-[radial-gradient_at_center_80px_80px]_indigo-500/10 rounded-3xl animate-pulse-opacity"></div>
        </div>
        <div className="relative max-w-4xl mx-auto text-center">
          <h2 className="text-4xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
            Start Creating Accessible Media Today
          </h2>
          <p className="text-slate-400 text-lg mb-8 max-w-2xl mx-auto leading-relaxed">
            Join thousands of creators using AI-powered audio description. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="/dashboard" className="inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-emerald-600 hover:bg-emerald-400 text-white font-medium transition shadow-lg shadow-emerald-300/20 border border-emerald-400/30">
              <span>🎯</span>
              <span>Use Tool</span>
            </a>
            <a href="#features" className="inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition border border-slate-600/50">
              <span>Learn Features</span>
            </a>
          </div>
        </div>
      </section>

      {/* Social Proof */}
      <section className="py-12 px-4 sm:px-6 bg-slate-950/50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mx-auto">
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-6 flex flex-col gap-3">
              <span className="w-8 h-8 rounded-xl bg-indigo-500/20 flex items-center justify-center text-indigo-300 text-lg mb-2">✓</span>
              <h4 className="font-bold text-white">Professional Creators</h4>
              <p className="text-slate-400 text-sm">"Finally, audio descriptions that respect the original mix."</p>
            </div>
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-6 flex flex-col gap-3">
              <span className="w-8 h-8 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-300 text-lg mb-2">✓</span>
              <h4 className="font-bold text-white">Accessibility Advocates</h4>
              <p className="text-slate-400 text-sm">"Truly dialogue-preserving descriptions."</p>
            </div>
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-6 flex flex-col gap-3">
              <span className="w-8 h-8 rounded-xl bg-indigo-500/20 flex items-center justify-center text-indigo-300 text-lg mb-2">✓</span>
              <h4 className="font-bold text-white">Film Festival Submitters</h4>
              <p className="text-slate-400 text-sm">"Meets all compliance requirements."</p>
            </div>
          </div>
        </div>
      </section>

      {/* Second CTA */}
      <section className="relative py-16 px-4 sm:px-6">
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-950/90 to-slate-900/90 blur-sm opacity-90"></div>
        <div className="relative max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-2 tracking-tight">
            Ready to Experience SeeLess?
          </h2>
          <p className="text-slate-400 text-lg mb-6 max-w-xl mx-auto leading-relaxed">
            Upload your first video and get AI-powered audio descriptions in minutes.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="/dashboard" className="inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-emerald-600 hover:bg-emerald-400 text-white font-medium transition shadow-lg shadow-emerald-300/20 border border-emerald-400/30">
              <span>🎯</span>
              <span>Use Tool</span>
            </a>
            <a href="#features" className="inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition border border-slate-600/50">
              <span>Learn Features</span>
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-16 px-4 sm:px-6 bg-slate-950 border-t border-slate-800/60">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
            <div>
              <h3 className="font-bold text-white mb-4">SeeLess</h3>
              <p className="text-slate-400 text-sm">
                AI-powered audio description platform for visually impaired viewers.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2 text-slate-400 text-sm">
                <li><a href="/dashboard" className="hover:text-white transition">Try the Tool</a></li>
                <li><a href="/about" className="hover:text-white transition">Features</a></li>
                <li><a href="#" className="hover:text-white transition">Pricing</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Resources</h4>
              <ul className="space-y-2 text-slate-400 text-sm">
                <li><a href="#" className="hover:text-white transition">Documentation</a></li>
                <li><a href="#" className="hover:text-white transition">API</a></li>
                <li><a href="#" className="hover:text-white transition">Blog</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Company</h4>
              <ul className="space-y-2 text-slate-400 text-sm">
                <li><a href="#" className="hover:text-white transition">About</a></li>
                <li><a href="#" className="hover:text-white transition">Careers</a></li>
                <li><a href="#" className="hover:text-white transition">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Legal</h4>
              <ul className="space-y-2 text-slate-400 text-sm">
                <li><a href="#" className="hover:text-white transition">Privacy</a></li>
                <li><a href="#" className="hover:text-white transition">Terms</a></li>
                <li><a href="#" className="hover:text-white transition">Accessibility</a></li>
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-slate-800/60 flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-slate-500 text-sm">2024 SeeLess. All rights reserved.</p>
            <div className="flex gap-3">
              <a href="https://x.com" className="text-slate-400 hover:text-white transition opacity-70" aria-label="Twitter" target="_blank" rel="noopener">
                <X size={20} />
              </a>
              <a href="https://facebook.com" className="text-slate-400 hover:text-white transition opacity-70" aria-label="Facebook" target="_blank" rel="noopener">
                <Link size={20} />
              </a>
              <a href="https://instagram.com" className="text-slate-400 hover:text-white transition opacity-70" aria-label="Instagram" target="_blank" rel="noopener">
                <User size={20} />
              </a>
              <a href="https://linkedin.com" className="text-slate-400 hover:text-white transition opacity-70" aria-label="LinkedIn" target="_blank" rel="noopener">
                <User size={20} />
              </a>
              <a href="https://github.com" className="text-slate-400 hover:text-white transition opacity-70" aria-label="GitHub" target="_blank" rel="noopener">
                <Code size={20} />
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

interface FeatureCardProps {
  icon: string;
  title: string;
  description: string;
}

function FeatureCard({icon, title, description}: FeatureCardProps) {
  return (
    <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 hover:border-indigo-500/50 transition-all duration-300 group">
      <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center mb-4 group-hover:bg-indigo-500/30 transition-colors">
        <span className="text-indigo-400 text-xl">{icon}</span>
      </div>
      <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
      <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
    </div>
  );
}