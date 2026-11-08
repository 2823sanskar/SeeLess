import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize2, Settings } from 'lucide-react';

interface TextSegment {
  start: number;
  end: number;
  text?: string;
}

interface AccessibleVideoPlayerProps {
  videoStreamUrl: string;
  masterStreamUrl?: string;
  descriptions: TextSegment[];
  speechSegments: TextSegment[];
}

export default function AccessibleVideoPlayer({
  videoStreamUrl,
  masterStreamUrl,
  descriptions,
  speechSegments,
}: AccessibleVideoPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [selectedTrack, setSelectedTrack] = useState<'original' | 'ad'>('original');
  const [showControls, setShowControls] = useState(true);

  const videoRef = useRef<HTMLVideoElement>(null);

  const activeStream = selectedTrack === 'ad' && masterStreamUrl ? masterStreamUrl : videoStreamUrl;

  // Sync state when track changes
  useEffect(() => {
    if (videoRef.current) {
      const prevTime = videoRef.current.currentTime;
      videoRef.current.src = activeStream;
      videoRef.current.currentTime = prevTime;
      if (isPlaying) videoRef.current.play();
    }
  }, [selectedTrack, activeStream]);

  const handlePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) videoRef.current.pause();
      else videoRef.current.play();
      setIsPlaying(!isPlaying);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (videoRef.current) videoRef.current.currentTime = time;
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = parseFloat(e.target.value);
    setVolume(vol);
    if (videoRef.current) videoRef.current.volume = vol;
  };

  const currentDescription = descriptions.find(d => currentTime >= d.start && currentTime <= d.end)?.text;
  const currentSubtitle = speechSegments.find(s => currentTime >= s.start && currentTime <= s.end)?.text;

  return (
    <div className="relative w-full max-w-4xl mx-auto bg-black rounded-lg overflow-hidden group">
      <video
        ref={videoRef}
        src={activeStream}
        className="w-full aspect-video"
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Overlays */}
      <div className="absolute top-4 left-4 right-4 flex flex-col gap-2 pointer-events-none">
        {currentSubtitle && (
          <div className="bg-black/70 text-white p-2 rounded text-sm self-center">
            {currentSubtitle}
          </div>
        )}
        {currentDescription && (
          <div className="bg-blue-900/80 text-white p-2 rounded text-sm self-center">
            {currentDescription}
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="absolute bottom-0 w-full bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
        <input
          type="range"
          min="0"
          max={duration}
          value={currentTime}
          onChange={handleSeek}
          className="w-full h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-white mb-4"
        />

        <div className="flex items-center justify-between text-white">
          <div className="flex items-center gap-4">
            <button onClick={handlePlayPause}>
              {isPlaying ? <Pause size={24} /> : <Play size={24} />}
            </button>
            <div className="flex items-center gap-2">
              <button onClick={() => setIsMuted(!isMuted)}>
                {isMuted ? <VolumeX size={20} /> : <Volume2 size={20} />}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={volume}
                onChange={handleVolumeChange}
                className="w-20 accent-white"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => setSelectedTrack(selectedTrack === 'original' ? 'ad' : 'original')}
              className={`px-3 py-1 rounded text-xs font-semibold ${
                selectedTrack === 'ad' ? 'bg-blue-600' : 'bg-gray-700'
              }`}
            >
              {selectedTrack === 'ad' ? 'AD TRACK' : 'ORIGINAL'}
            </button>
            <Settings size={20} />
            <Maximize2 size={20} />
          </div>
        </div>
      </div>
    </div>
  );
}
