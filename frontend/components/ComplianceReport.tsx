'use client';

import React from 'react';

export interface DescriptionCoverageMetrics {
  totalSegments: number;
  describedSegments: number;
  coverage: number;
}

export interface SpeechOverlapMetrics {
  totalSpeechDuration: number;
  overlappingDuration: number;
  overlapPercentage: number;
}

export interface PauseUtilizationMetrics {
  totalPauseTime: number;
  totalDuration: number;
  pauseUtilization: number;
}

export interface NarrationDensityMetrics {
  totalNarrationWords: number;
  totalAudioDuration: number;
  wordsPerMinute: number;
}

export type ComplianceLevel = 'AAA' | 'AA' | 'A' | 'Non-compliant';

export interface ComplianceReportProps {
  accessibilityScore: number;
  descriptionCoverage: DescriptionCoverageMetrics;
  speechOverlap: SpeechOverlapMetrics;
  pauseUtilization: PauseUtilizationMetrics;
  narrationDensity: NarrationDensityMetrics;
  wcagLevel: ComplianceLevel;
}

function getComplianceBadgeClass(level: 'AAA' | 'AA' | 'A' | 'Non-compliant'): string {
  switch (level) {
    case 'AAA':
      return 'bg-emerald-600/20 text-emerald-400 border-emerald-500';
    case 'AA':
      return 'bg-indigo-600/20 text-indigo-400 border-indigo-500';
    case 'A':
      return 'bg-amber-600/20 text-amber-400 border-amber-500';
    case 'Non-compliant':
      return 'bg-rose-600/20 text-rose-400 border-rose-500';
    default:
      return 'bg-slate-600/20 text-slate-400 border-slate-500';
  }
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-emerald-400';
  if (score >= 60) return 'text-indigo-400';
  if (score >= 40) return 'text-amber-400';
  return 'text-rose-400';
}

export function ComplianceReport({
  accessibilityScore,
  descriptionCoverage,
  speechOverlap,
  pauseUtilization,
  narrationDensity,
  wcagLevel,
}: ComplianceReportProps) {
  const scoreColor = getScoreColor(accessibilityScore);
  const badgeClass = getComplianceBadgeClass(wcagLevel);

  // Determine description coverage label
  const coverageLabel = descriptionCoverage.coverage >= 80
    ? 'Excellent'
    : descriptionCoverage.coverage >= 60
    ? 'Good'
    : descriptionCoverage.coverage >= 40
    ? 'Fair'
    : 'Poor';

  // Determine speech overlap label
  const overlapLabel = speechOverlap.overlapPercentage <= 10
    ? 'Low'
    : speechOverlap.overlapPercentage <= 25
    ? 'Moderate'
    : 'High';

  // Determine pause utilization label
  const pauseLabel = pauseUtilization.pauseUtilization >= 15
    ? 'Good'
    : pauseUtilization.pauseUtilization >= 10
    ? 'Moderate'
    : 'Low';

  // Determine narration density label
  const densityLabel = narrationDensity.wordsPerMinute >= 150
    ? 'High'
    : narrationDensity.wordsPerMinute >= 100
    ? 'Moderate'
    : 'Light';

  return (
    <div className="bg-slate-950/50 border border-slate-800 rounded-2xl p-6 mb-6 backdrop-blur-sm">
      <h2 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
        <span className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-sm text-white font-bold">C</span>
        Compliance Scorecard
      </h2>

      {/* Accessibility Score */}
      <div className="mb-6">
        <div className="flex justify-between text-sm text-slate-400 mb-2">
          <span>Accessibility Score</span>
          <span className={`font-bold ${scoreColor}`}>{accessibilityScore}</span>
        </div>
        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${scoreColor} bg-indigo-600`}
            style={{ width: `${accessibilityScore}%` }}
          />
        </div>
        <p className="text-xs text-slate-500 mt-2">
          {accessibilityScore}% accessibility compliance
        </p>
      </div>

      {/* Compliance Level Badge */}
      <div className="mb-6">
        <div className={`px-4 py-1.5 rounded-full ${badgeClass} text-sm font-medium flex items-center gap-2`}>
          <span className={`w-2 h-2 rounded-full ${wcagLevel === 'AAA' ? 'bg-emerald-400' : wcagLevel === 'AA' ? 'bg-indigo-400' : wcagLevel === 'A' ? 'bg-amber-400' : 'bg-rose-400'}`}></span>
          <span>{wcagLevel} compliant</span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        {/* Description Coverage */}
        <div>
          <div className="text-xs text-slate-400 mb-1">Description Coverage</div>
          <div className="flex justify-between text-sm font-medium">
            <span>{descriptionCoverage.coverage}%</span>
            <span className="text-slate-500">{coverageLabel}</span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden mt-1">
            <div
              className={`h-full rounded-full ${descriptionCoverage.coverage >= 80 ? 'bg-emerald-500' : descriptionCoverage.coverage >= 60 ? 'bg-indigo-500' : descriptionCoverage.coverage >= 40 ? 'bg-amber-500' : 'bg-rose-500'} transition-all duration-500`}
              style={{ width: `${descriptionCoverage.coverage}%` }}
            />
          </div>
        </div>

        {/* Speech Overlap */}
        <div>
          <div className="text-xs text-slate-400 mb-1">Speech Overlap</div>
          <div className="flex justify-between text-sm font-medium">
            <span>{speechOverlap.overlapPercentage}%</span>
            <span className="text-slate-500">{overlapLabel}</span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden mt-1">
            <div
              className={`h-full rounded-full transition-all duration-500 ${speechOverlap.overlapPercentage <= 10 ? 'bg-emerald-500' : speechOverlap.overlapPercentage <= 25 ? 'bg-amber-500' : 'bg-rose-500'}`}
              style={{ width: `${speechOverlap.overlapPercentage}%` }}
            />
          </div>
        </div>

        {/* Pause Utilization */}
        <div>
          <div className="text-xs text-slate-400 mb-1">Pause Utilization</div>
          <div className="flex justify-between text-sm font-medium">
            <span>{pauseUtilization.pauseUtilization}%</span>
            <span className="text-slate-500">{pauseLabel}</span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden mt-1">
            <div
              className={`h-full rounded-full transition-all duration-500 ${pauseUtilization.pauseUtilization >= 15 ? 'bg-emerald-500' : pauseUtilization.pauseUtilization >= 10 ? 'bg-amber-500' : 'bg-rose-500'}`}
              style={{ width: `${pauseUtilization.pauseUtilization}%` }}
            />
          </div>
        </div>

        {/* Narration Density */}
        <div>
          <div className="text-xs text-slate-400 mb-1">Narration Density</div>
          <div className="flex justify-between text-sm font-medium">
            <span>{narrationDensity.wordsPerMinute} wpm</span>
            <span className="text-slate-500">{densityLabel}</span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden mt-1">
            <div
              className={`h-full rounded-full transition-all duration-500 ${narrationDensity.wordsPerMinute >= 150 ? 'bg-rose-500' : narrationDensity.wordsPerMinute >= 100 ? 'bg-amber-500' : 'bg-emerald-500'}`}
              style={{ width: `${Math.min(narrationDensity.wordsPerMinute, 200) / 200 * 100}%` }}
            />
          </div>
        </div>

      </div>

      {/* WCAG Summary */}
      <div className="mt-6 pt-6 border-t border-slate-800">
        <h3 className="text-sm font-bold text-white mb-3">WCAG Compliance Summary</h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className={`p-2 rounded ${badgeClass}`}>
            <div className="font-medium text-white">Perceivable</div>
            <div className="text-slate-400">✓ Available</div>
          </div>
          <div className={`p-2 rounded ${badgeClass}`}>
            <div className="font-medium text-white">Operable</div>
            <div className="text-slate-400">✓ Available</div>
          </div>
          <div className={`p-2 rounded ${badgeClass}`}>
            <div className="font-medium text-white">Understandable</div>
            <div className="text-slate-400">✓ Available</div>
          </div>
          <div className={`p-2 rounded ${badgeClass}`}>
            <div className="font-medium text-white">Robust</div>
            <div className="text-slate-400">✓ Available</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Default export for convenience
export default ComplianceReport;