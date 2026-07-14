"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type CameraStatus = "idle" | "requesting" | "ready" | "denied" | "unsupported" | "error";

interface UseCameraResult {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  status: CameraStatus;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
  /** Grabs the current video frame as a JPEG data URL, or null if not ready. */
  capture: () => string | null;
}

/**
 * Wraps the browser MediaDevices API for the attendance photo capture flow.
 * Prefers the rear camera on mobile devices and surfaces permission /
 * hardware errors as readable status instead of throwing.
 */
export function useCamera(): UseCameraResult {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [status, setStatus] = useState<CameraStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const start = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setStatus("unsupported");
      setError("Camera access isn't supported in this browser.");
      return;
    }

    setStatus("requesting");
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        // "ideal" constraints are a preference, not a requirement, so this
        // degrades gracefully on cameras/browsers that can't hit it — it
        // never throws OverconstrainedError the way a required constraint
        // would. Requesting a larger frame gives OCR (added in a later
        // milestone) more detail to work with once it lands.
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStatus("ready");
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setStatus("denied");
        setError("Camera permission was denied. Enable camera access for this site and try again.");
      } else if (name === "NotFoundError" || name === "OverconstrainedError") {
        setStatus("error");
        setError("No usable camera was found on this device.");
      } else {
        setStatus("error");
        setError("Couldn't access the camera. Please try again.");
      }
    }
  }, []);

  const capture = useCallback((): string | null => {
    const video = videoRef.current;
    if (!video || video.readyState < video.HAVE_CURRENT_DATA || !video.videoWidth) {
      return null;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext("2d");
    if (!context) return null;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.92);
  }, []);

  // Always release the camera when the component using this hook unmounts.
  useEffect(() => stop, [stop]);

  return { videoRef, status, error, start, stop, capture };
}
