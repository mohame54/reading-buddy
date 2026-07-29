export function playWordClip(
  audio: HTMLAudioElement,
  start: number,
  end: number,
): void {
  audio.currentTime = start;
  void audio.play();
  const onTime = () => {
    if (audio.currentTime >= end) {
      audio.pause();
      audio.removeEventListener("timeupdate", onTime);
    }
  };
  audio.addEventListener("timeupdate", onTime);
}

export function playFullPage(audio: HTMLAudioElement): void {
  audio.currentTime = 0;
  void audio.play();
}

export async function prefetchAudio(url: string): Promise<HTMLAudioElement> {
  const audio = new Audio(url);
  audio.preload = "auto";
  await new Promise<void>((resolve, reject) => {
    audio.addEventListener("canplaythrough", () => resolve(), { once: true });
    audio.addEventListener("error", () => reject(new Error("Failed to load audio")), {
      once: true,
    });
    audio.load();
  });
  return audio;
}
