def seconds_to_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def intervals_overlap(start1: float, end1: float, start2: float, end2: float) -> bool:
    return max(start1, start2) < min(end1, end2)

