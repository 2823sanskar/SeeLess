from typing import List, Dict, Any, Tuple
from app.utils.logging_utils import logger
from app.utils.timestamp_utils import intervals_overlap

def estimate_speech_duration(text: str, words_per_minute: int = 150) -> float:
    words = len(text.strip().split())
    # Base calculation + 0.3s pause buffer
    duration = (words / (words_per_minute / 60.0)) + 0.3
    return max(1.0, round(duration, 2))

def find_available_gap(
    requested_start: float,
    required_duration: float,
    speech_intervals: List[Dict[str, float]],
    scheduled_clips: List[Dict[str, float]],
    video_duration: float,
    max_delay: float = 12.0
) -> Tuple[bool, float, float]:
    """
    Finds a gap starting at or after requested_start that does not overlap speech intervals or other scheduled narration.
    """
    # Combine all occupied intervals
    occupied = []
    for sp in speech_intervals:
        occupied.append((sp["start"], sp["end"]))
    for clip in scheduled_clips:
        occupied.append((clip["scheduled_start"], clip["scheduled_end"]))
        
    occupied.sort(key=lambda x: x[0])
    
    current_time = max(0.0, requested_start)
    search_limit = min(video_duration, requested_start + max_delay)
    
    while current_time + required_duration <= video_duration and current_time <= search_limit:
        candidate_end = current_time + required_duration
        
        # Check collision with any occupied block
        conflict = False
        for occ_start, occ_end in occupied:
            if intervals_overlap(current_time, candidate_end, occ_start, occ_end):
                conflict = True
                # Jump past the conflicting block
                current_time = occ_end + 0.1  # 100ms safety buffer
                break
                
        if not conflict:
            if candidate_end <= video_duration:
                return True, round(current_time, 2), round(candidate_end, 2)
            else:
                break
                
    return False, 0.0, 0.0

def schedule_narration_clips(
    descriptions: List[Dict[str, Any]],
    protected_speech_intervals: List[Dict[str, float]],
    video_duration: float
) -> Dict[str, Any]:
    """
    Schedules narration descriptions around protected speech intervals deterministically.
    Rule 1: Never overlap dialogue.
    Rule 2: Prefer natural gaps.
    Rule 3: Use original event timing or push slightly forward.
    Rule 4: Prioritize important events.
    """
    logger.info(f"Scheduling {len(descriptions)} descriptions against {len(protected_speech_intervals)} protected speech intervals.")

    # Sort descriptions by priority descending, then by start time
    sorted_descriptions = sorted(descriptions, key=lambda x: (-x.get("priority", 0.5), x["start"]))

    scheduled = []
    omitted = []

    # Keep track of accepted clips chronologically
    placed_clips: List[Dict[str, Any]] = []

    for desc in sorted_descriptions:
        desc_id = desc.get("id", "desc")
        text = desc.get("text", "")
        start_req = desc.get("start", 0.0)
        
        # Check boundaries
        if start_req >= video_duration:
            omitted.append({
                "description_id": desc_id,
                "text": text,
                "status": "omitted",
                "reason": "Requested start is beyond video duration"
            })
            continue

        estimated_dur = estimate_speech_duration(text)
        
        found, sch_start, sch_end = find_available_gap(
            requested_start=start_req,
            required_duration=estimated_dur,
            speech_intervals=protected_speech_intervals,
            scheduled_clips=placed_clips,
            video_duration=video_duration,
            max_delay=15.0
        )

        if found:
            clip_entry = {
                "description_id": desc_id,
                "text": text,
                "priority": desc.get("priority", 0.5),
                "scheduled_start": sch_start,
                "scheduled_end": sch_end,
                "estimated_duration": estimated_dur,
                "status": "scheduled"
            }
            placed_clips.append(clip_entry)
            scheduled.append(clip_entry)
        else:
            omitted.append({
                "description_id": desc_id,
                "text": text,
                "status": "omitted",
                "reason": "No suitable narration gap without overlapping speech"
            })

    # Sort final scheduled clips chronologically
    scheduled.sort(key=lambda x: x["scheduled_start"])

    return {
        "scheduled": scheduled,
        "omitted": omitted
    }

def validate_clip_placement(
    scheduled_start: float,
    actual_duration: float,
    speech_intervals: List[Dict[str, float]],
    video_duration: float
) -> Tuple[bool, float, float]:
    """
    Revalidates placement using actual TTS duration.
    """
    scheduled_end = round(scheduled_start + actual_duration, 2)
    if scheduled_end > video_duration:
        return False, scheduled_start, scheduled_end
        
    for sp in speech_intervals:
        if intervals_overlap(scheduled_start, scheduled_end, sp["start"], sp["end"]):
            return False, scheduled_start, scheduled_end
            
    return True, scheduled_start, scheduled_end

