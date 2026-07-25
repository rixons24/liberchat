"use client";

import { useEffect, useState } from "react";

export default function MediaViewer({ media, onClose }) {
  const [viewCount, setViewCount] = useState(1);

  useEffect(() => {
    // heartbeat while viewer is open — keeps the session alive server-side
    const interval = setInterval(() => {
      fetch(`/api/media/${media.id}/heartbeat`, { method: "POST" });
    }, 20000);
    return () => clearInterval(interval);
  }, [media.id]);

  const handleReplay = () => {
    setViewCount((c) => c + 1);
    // client re-triggers playback; server increments view_count on its side too
    fetch(`/api/media/${media.id}/view`, { method: "POST" });
  };

  const handleClose = async () => {
    await fetch(`/api/media/${media.id}/end-session`, { method: "POST" });
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-ink flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <span className="label text-muted">
          {media.type.toUpperCase()} / VIEWED {viewCount}×
        </span>
        <button onClick={handleClose} className="btn-danger">
          Close — deletes on exit
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center p-6">
        {media.type === "image" && (
          <img src={media.signedUrl} alt="" className="max-h-full max-w-full" />
        )}
        {media.type === "video" && (
          <video src={media.signedUrl} controls autoPlay onEnded={handleReplay} className="max-h-full max-w-full" />
        )}
        {media.type === "audio" && (
          <audio src={media.signedUrl} controls autoPlay onEnded={handleReplay} className="w-full max-w-sm" />
        )}
      </div>

      <div className="px-4 py-3 border-t border-line">
        <span className="label text-muted">This content deletes permanently when you leave this screen.</span>
      </div>
    </div>
  );
}
