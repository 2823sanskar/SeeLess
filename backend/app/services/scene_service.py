import os
from typing import List, Dict, Any
from app.utils.logging_utils import logger
from app.services.extraction_service import extract_metadata

def detect_scenes(video_path: str) -> List[Dict[str, Any]]:
    scenes_result = []
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector

        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=27.0))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        for idx, (start_time, end_time) in enumerate(scene_list):
            scenes_result.append({
                "scene_number": idx + 1,
                "start_time": round(start_time.get_seconds(), 2),
                "end_time": round(end_time.get_seconds(), 2)
            })
    except Exception as e:
        logger.warning(f"PySceneDetect failed or not available ({e}). Applying fallback whole-video or fixed-interval scene.")
        meta = extract_metadata(video_path)
        total_dur = meta.get("duration", 0.0)
        # Create default scenes or single scene
        if total_dur > 0:
            scenes_result.append({
                "scene_number": 1,
                "start_time": 0.0,
                "end_time": round(total_dur, 2)
            })

    if not scenes_result:
        scenes_result = [{
            "scene_number": 1,
            "start_time": 0.0,
            "end_time": 10.0
        }]

    return scenes_result

