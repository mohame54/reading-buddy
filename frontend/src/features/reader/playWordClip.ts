import type { WordMismatch } from "../../types/api";

let activeClipCleanup: (() => void) | null = null;

export function stopActiveClip(): void {
  activeClipCleanup?.();
  activeClipCleanup = null;
}

export async function playWordClip(
  audio: HTMLAudioElement,
  start: number,
  end: number,
): Promise<boolean> {
  stopActiveClip();
  audio.pause();

  const clipEnd = end > start ? end : start + 0.4;
  audio.currentTime = start;

  const onTime = () => {
    if (audio.currentTime >= clipEnd) {
      audio.pause();
      cleanup();
    }
  };

  const cleanup = () => {
    audio.removeEventListener("timeupdate", onTime);
    if (activeClipCleanup === cleanup) {
      activeClipCleanup = null;
    }
  };

  activeClipCleanup = cleanup;
  audio.addEventListener("timeupdate", onTime);

  try {
    await audio.play();
    return true;
  } catch {
    cleanup();
    return false;
  }
}

export async function playFullPage(audio: HTMLAudioElement): Promise<boolean> {
  stopActiveClip();
  audio.pause();
  audio.currentTime = 0;

  try {
    await audio.play();
    return true;
  } catch {
    return false;
  }
}

export async function playMismatchClip(
  audio: HTMLAudioElement,
  mismatch: Pick<WordMismatch, "start" | "end">,
): Promise<boolean> {
  if (mismatch.start != null && mismatch.end != null) {
    return playWordClip(audio, mismatch.start, mismatch.end);
  }
  return playFullPage(audio);
}

export async function prefetchAudio(url: string): Promise<HTMLAudioElement> {
  const audio = new Audio(url);
  audio.preload = "auto";
  await new Promise<void>((resolve, reject) => {
    const onReady = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error("Failed to load audio"));
    };
    const cleanup = () => {
      audio.removeEventListener("canplaythrough", onReady);
      audio.removeEventListener("error", onError);
    };
    audio.addEventListener("canplaythrough", onReady, { once: true });
    audio.addEventListener("error", onError, { once: true });
    audio.load();
  });
  return audio;
}
