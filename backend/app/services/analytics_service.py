"""
analytics_service.py
--------------------
Compliance analytics functions for accessibility metrics.
Computes WCAG/CVAA coverage, narration density, and overall scores.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from app.models import Description, SpeechSegment, Video, NarrationClip


@dataclass
class DescriptionCoverageMetrics:
    """Description vs speech coverage percentages."""
    description_coverage: float  # Percentage of video covered by descriptions
    speech_coverage: float  # Percentage of video covered by speech
    total_descriptions_count: int
    total_speech_segments_count: int
    duration: float


@dataclass
class PauseUtilizationMetrics:
    """Speech-to-pause utilization ratios."""
    speech_time: float  # Total speech duration in seconds
    pause_time: float  # Total non-speech (pause/background) duration in seconds
    speech_to_pause_ratio: float  # Ratio of speech to pause time
    pause_efficiency: float  # Percentage of video that is pause/background


@dataclass
class DialogueOverlapMetrics:
    """Dialogue overlap analysis for accessibility."""
    overlap_percentage: float  # Percentage of time with overlapping dialogue
    max_concurrent_speeches: int  # Maximum number of simultaneous speech events
    overlap_events: int  # Count of overlapping segments


@dataclass
class NarrationDensityMetrics:
    """Narration density metrics."""
    descriptions_per_minute: float
    total_descriptions: int
    duration_minutes: float
    words_per_description: float


@dataclass
class AccessibilityScoreMetrics:
    """Composite WCAG/CVAA accessibility score."""
    wcag_compliance: float  # 0.0-1.0 WCAG compliance score
    cvaa_compliance: float  # 0.0-1.0 CVAA compliance score
    overall_score: float  # Weighted composite score
    score_breakdown: Dict[str, float]  # Individual component scores


@dataclass
class ComplianceScorecard:
    """Complete compliance scorecard for a video."""
    video_id: str
    video_title: str
    duration_seconds: float
    generated_at: datetime
    description_coverage: DescriptionCoverageMetrics
    pause_utilization: PauseUtilizationMetrics
    dialogue_overlap: DialogueOverlapMetrics
    narration_density: NarrationDensityMetrics
    accessibility_score: AccessibilityScoreMetrics


def calculate_description_coverage(
    db: Session,
    video_id: str,
    video_duration: Optional[float] = None,
) -> DescriptionCoverageMetrics:
    """
    Compute description vs speech coverage percentages.

    Returns metrics showing what percentage of the video is covered by
    audio descriptions vs speech segments.
    """
    if video_duration is None or video_duration <= 0:
        video = db.query(Video).filter(Video.id == video_id).first()
        video_duration = video.duration if video and video.duration else 0.0

    descriptions = db.query(Description).filter(Description.video_id == video_id).all()
    speech_segments = db.query(SpeechSegment).filter(SpeechSegment.video_id == video_id).all()

    if video_duration <= 0:
        return DescriptionCoverageMetrics(
            description_coverage=0.0,
            speech_coverage=0.0,
            total_descriptions_count=len(descriptions),
            total_speech_segments_count=len(speech_segments),
            duration=video_duration,
        )

    total_desc_time = 0.0
    for d in descriptions:
        segment_time = d.end_time - d.start_time
        if segment_time > 0:
            total_desc_time += segment_time

    total_speech_time = 0.0
    for s in speech_segments:
        segment_time = s.end_time - s.start_time
        if segment_time > 0:
            total_speech_time += segment_time

    desc_coverage = min(100.0, (total_desc_time / video_duration) * 100.0)
    speech_coverage = min(100.0, (total_speech_time / video_duration) * 100.0)

    return DescriptionCoverageMetrics(
        description_coverage=round(desc_coverage, 2),
        speech_coverage=round(speech_coverage, 2),
        total_descriptions_count=len(descriptions),
        total_speech_segments_count=len(speech_segments),
        duration=video_duration,
    )


def calculate_pause_utilization(
    db: Session,
    video_id: str,
    video_duration: Optional[float] = None,
) -> PauseUtilizationMetrics:
    """
    Compute speech-to-pause ratios.

    Calculates what percentage of the video is speech vs non-speech (pause/background).
    """
    if video_duration is None or video_duration <= 0:
        video = db.query(Video).filter(Video.id == video_id).first()
        video_duration = video.duration if video and video.duration else 0.0

    speech_segments = db.query(SpeechSegment).filter(SpeechSegment.video_id == video_id).all()

    if video_duration <= 0:
        return PauseUtilizationMetrics(
            speech_time=0.0,
            pause_time=0.0,
            speech_to_pause_ratio=0.0,
            pause_efficiency=0.0,
        )

    total_speech_time = 0.0
    for s in speech_segments:
        segment_time = s.end_time - s.start_time
        if segment_time > 0:
            total_speech_time += segment_time

    pause_time = max(0.0, video_duration - total_speech_time)
    ratio = total_speech_time / pause_time if pause_time > 0 else float('inf') if total_speech_time > 0 else 0.0

    pause_efficiency = (pause_time / video_duration) * 100.0 if video_duration > 0 else 0.0

    return PauseUtilizationMetrics(
        speech_time=round(total_speech_time, 3),
        pause_time=round(pause_time, 3),
        speech_to_pause_ratio=round(ratio, 3),
        pause_efficiency=round(pause_efficiency, 2),
    )


def calculate_dialogue_overlap(
    db: Session,
    video_id: str,
) -> DialogueOverlapMetrics:
    """
    Compute dialogue overlap percentages.

    For proper accessibility, this should be 0% as overlapping speech
    makes it difficult for audio description placement.
    """
    speech_segments = db.query(SpeechSegment).filter(SpeechSegment.video_id == video_id).all()

    if len(speech_segments) < 2:
        return DialogueOverlapMetrics(
            overlap_percentage=0.0,
            max_concurrent_speeches=0,
            overlap_events=0,
        )

    sorted_segments = sorted(speech_segments, key=lambda s: s.start_time)

    overlap_time = 0.0
    overlap_events = 0
    max_concurrent = 1
    current_start = sorted_segments[0].start_time

    def segment_end(segments: List[SpeechSegment]) -> float:
        return min(s.end_time for s in segments)

    for i in range(len(sorted_segments) - 1):
        for j in range(i + 1, len(sorted_segments)):
            s1 = sorted_segments[i]
            s2 = sorted_segments[j]
            if s2.start_time >= s1.end_time:
                break
            overlap_start = max(s1.start_time, s2.start_time)
            overlap_end = min(s1.end_time, s2.end_time)
            if overlap_end > overlap_start:
                overlap_time += (overlap_end - overlap_start)
                overlap_events += 1

            active = [s for s in sorted_segments
                      if s.start_time <= s2.start_time < s.end_time]
            max_concurrent = max(max_concurrent, len(active))

    video = db.query(Video).filter(Video.id == video_id).first()
    video_duration = video.duration if video and video.duration else 1.0

    overlap_percentage = (overlap_time / video_duration) * 100.0 if video_duration > 0 else 0.0

    return DialogueOverlapMetrics(
        overlap_percentage=round(overlap_percentage, 2),
        max_concurrent_speeches=max_concurrent,
        overlap_events=overlap_events,
    )


def calculate_narration_density(
    db: Session,
    video_id: str,
) -> NarrationDensityMetrics:
    """
    Compute narration density - descriptions per minute.

    Measures how many audio descriptions are generated per minute of video,
    with word count and words per description metrics.
    """
    descriptions = db.query(Description).filter(Description.video_id == video_id).all()
    narration_clips = db.query(NarrationClip).filter(
        NarrationClip.description_id.in_([d.id for d in descriptions])
    ).all()

    video = db.query(Video).filter(Video.id == video_id).first()
    video_duration = video.duration if video and video.duration else 0.0

    if video_duration <= 0:
        return NarrationDensityMetrics(
            descriptions_per_minute=0.0,
            total_descriptions=len(descriptions),
            duration_minutes=0.0,
            words_per_description=0.0,
        )

    duration_minutes = video_duration / 60.0
    descriptions_per_min = len(descriptions) / duration_minutes

    total_words = 0
    for d in descriptions:
        word_count = len(d.text.split()) if d.text else 0
        total_words += word_count

    words_per_desc = total_words / len(descriptions) if descriptions else 0.0

    return NarrationDensityMetrics(
        descriptions_per_minute=round(descriptions_per_min, 2),
        total_descriptions=len(descriptions),
        duration_minutes=round(duration_minutes, 2),
        words_per_description=round(words_per_desc, 2),
    )


def calculate_accessibility_score(
    db: Session,
    video_id: str,
) -> AccessibilityScoreMetrics:
    """
    Compute composite WCAG/CVAA compliance score.

    Combines multiple metrics into a single accessibility score:
    - WCAG 2.1 AA compliance (1.2.1 Audio-only and 1.2.3 Audio Description)
    - CVAA compliance (2.4.4 Link Purpose and audio description requirements)
    """
    desc_coverage = calculate_description_coverage(db, video_id)
    pause_util = calculate_pause_utilization(db, video_id)
    overlap = calculate_dialogue_overlap(db, video_id)
    narration = calculate_narration_density(db, video_id)

    video = db.query(Video).filter(Video.id == video_id).first()
    video_duration = video.duration if video and video.duration else 0.0

    desc_coverage_score = min(1.0, desc_coverage.description_coverage / 100.0)

    if video_duration and video_duration > 0:
        ideal_desc_density = 0.8
        min_desc_density = 0.3
        raw_density = narration.descriptions_per_minute
        density_score = min(1.0, max(0.0, (raw_density - min_desc_density) / (ideal_desc_density - min_desc_density)))
        density_score = min(1.0, density_score)
    else:
        density_score = 0.5

    overlap_penalty = max(0.0, 1.0 - (overlap.overlap_percentage / 10.0))
    if overlap.overlap_percentage > 20.0:
        overlap_penalty = 0.0

    pause_score = min(1.0, pause_util.pause_efficiency / 50.0)

    wcag_components = [desc_coverage_score, density_score, overlap_penalty]
    wcag_score = sum(wcag_components) / len(wcag_components) if wcag_components else 0.0

    cvaa_components = [overlap_penalty, pause_score]
    cvaa_score = sum(cvaa_components) / len(cvaa_components) if cvaa_components else 0.0

    overall = (wcag_score * 0.6) + (cvaa_score * 0.4)

    score_breakdown = {
        "description_coverage": desc_coverage_score,
        "narration_density": density_score,
        "overlap_compliance": overlap_penalty,
        "pause_efficiency": pause_score,
    }

    return AccessibilityScoreMetrics(
        wcag_compliance=round(wcag_score, 3),
        cvaa_compliance=round(cvaa_score, 3),
        overall_score=round(overall, 3),
        score_breakdown={k: round(v, 3) for k, v in score_breakdown.items()},
    )


def generate_compliance_scorecard(
    db: Session,
    video_id: str,
) -> ComplianceScorecard:
    """
    Generate complete compliance scorecard for a video.

    Combines all accessibility metrics into a comprehensive scorecard.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")

    description_coverage = calculate_description_coverage(db, video_id, video.duration)
    pause_utilization = calculate_pause_utilization(db, video_id, video.duration)
    dialogue_overlap = calculate_dialogue_overlap(db, video_id)
    narration_density = calculate_narration_density(db, video_id)
    accessibility_score = calculate_accessibility_score(db, video_id)

    return ComplianceScorecard(
        video_id=video_id,
        video_title=video.original_filename,
        duration_seconds=video.duration or 0.0,
        generated_at=datetime.utcnow(),
        description_coverage=description_coverage,
        pause_utilization=pause_utilization,
        dialogue_overlap=dialogue_overlap,
        narration_density=narration_density,
        accessibility_score=accessibility_score,
    )


def generate_compliance_report_json(
    db: Session,
    video_id: str,
) -> Dict[str, Any]:
    """
    Generate JSON compliance report for a video.

    Returns a dictionary suitable for API response with all metrics.
    """
    scorecard = generate_compliance_scorecard(db, video_id)

    return {
        "video_id": scorecard.video_id,
        "video_title": scorecard.video_title,
        "duration_seconds": scorecard.duration_seconds,
        "generated_at": scorecard.generated_at.isoformat() + "Z",
        "description_coverage": asdict(scorecard.description_coverage),
        "pause_utilization": asdict(scorecard.pause_utilization),
        "dialogue_overlap": asdict(scorecard.dialogue_overlap),
        "narration_density": asdict(scorecard.narration_density),
        "accessibility_score": asdict(scorecard.accessibility_score),
    }


def generate_compliance_report_pdf_context(
    db: Session,
    video_id: str,
) -> Dict[str, Any]:
    """
    Generate PDF context data for compliance report.

    Returns structured data for rendering a PDF compliance report.
    """
    scorecard = generate_compliance_scorecard(db, video_id)

    return {
        "title": "Accessibility Compliance Report",
        "video_info": {
            "id": scorecard.video_id,
            "title": scorecard.video_title,
            "duration": f"{scorecard.duration_seconds:.1f}s",
            "generated_at": scorecard.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
        "summary": {
            "accessibility_score": scorecard.accessibility_score.overall_score,
            "wcag_compliance": scorecard.accessibility_score.wcag_compliance,
            "cvaa_compliance": scorecard.accessibility_score.cvaa_compliance,
            "status": "PASS" if scorecard.accessibility_score.overall_score >= 0.7 else "NEEDS_IMPROVEMENT",
        },
        "metrics": {
            "description_coverage": {
                "coverage_percent": scorecard.description_coverage.description_coverage,
                "speech_percent": scorecard.description_coverage.speech_coverage,
                "description_count": scorecard.description_coverage.total_descriptions_count,
                "speech_segment_count": scorecard.description_coverage.total_speech_segments_count,
            },
            "pause_utilization": {
                "speech_time_seconds": scorecard.pause_utilization.speech_time,
                "pause_time_seconds": scorecard.pause_utilization.pause_time,
                "speech_to_pause_ratio": scorecard.pause_utilization.speech_to_pause_ratio,
                "pause_efficiency_percent": scorecard.pause_utilization.pause_efficiency,
            },
            "dialogue_overlap": {
                "overlap_percent": scorecard.dialogue_overlap.overlap_percentage,
                "max_concurrent_speeches": scorecard.dialogue_overlap.max_concurrent_speeches,
                "overlap_events": scorecard.dialogue_overlap.overlap_events,
            },
            "narration_density": {
                "descriptions_per_minute": scorecard.narration_density.descriptions_per_minute,
                "total_descriptions": scorecard.narration_density.total_descriptions,
                "duration_minutes": scorecard.narration_density.duration_minutes,
                "words_per_description": scorecard.narration_density.words_per_description,
            },
        },
        "breakdown": {
            "wcag_components": {
                "description_coverage": scorecard.accessibility_score.score_breakdown.get("description_coverage", 0),
                "narration_density": scorecard.accessibility_score.score_breakdown.get("narration_density", 0),
                "overlap_compliance": scorecard.accessibility_score.score_breakdown.get("overlap_compliance", 0),
            },
            "cvaa_components": {
                "overlap_compliance": scorecard.accessibility_score.score_breakdown.get("overlap_compliance", 0),
                "pause_efficiency": scorecard.accessibility_score.score_breakdown.get("pause_efficiency", 0),
            },
        },
        "recommendations": _generate_recommendations(scorecard),
    }


def _generate_recommendations(scorecard: ComplianceScorecard) -> List[str]:
    """Generate actionable recommendations based on scorecard metrics."""
    recommendations = []

    if scorecard.description_coverage.description_coverage < 30.0:
        recommendations.append(
            "Increase audio description coverage to at least 30% of video duration "
            "for WCAG 2.1 AA compliance."
        )

    if scorecard.accessibility_score.score_breakdown.get("narration_density", 0) < 0.5:
        recommendations.append(
            "Add more audio descriptions to improve narration density. "
            "Ideal range: 0.3-0.8 descriptions per minute."
        )

    if scorecard.dialogue_overlap.overlap_percentage > 5.0:
        recommendations.append(
            f"Reduce dialogue overlap ({scorecard.dialogue_overlap.overlap_percentage:.1f}%). "
            "Overlapping speech makes audio description placement challenging for users."
        )

    if scorecard.narration_density.words_per_description < 10.0:
        recommendations.append(
            "Consider expanding description detail. "
            f"Current average is {scorecard.narration_density.words_per_description:.0f} words per description."
        )

    if not recommendations:
        recommendations.append(
            "Video meets accessibility requirements. "
            "Continue monitoring narration quality and placement."
        )

    return recommendations