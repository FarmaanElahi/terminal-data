/**
 * Audio synthesis utilities using Web Audio API.
 * Synthesizes sounds dynamically without external assets.
 */

export type AlertSound = "none" | "beep" | "buzzer" | "digital" | "chime" | string;

/**
 * Plays a synthesized alert sound based on the type.
 * @param type The sound profile to play
 */
export const playBeep = (type: AlertSound | null = "beep") => {
  if (!type || type === "none") return;

  try {
    const AudioContextClass = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;

    const ctx = new AudioContextClass();
    const now = ctx.currentTime;

    if (type === "buzzer") {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(150, now);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(now + 0.5);
    } else if (type === "digital") {
      // Multi-beep square wave pattern
      for (let i = 0; i < 3; i++) {
        const t = now + i * 0.1;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "square";
        osc.frequency.setValueAtTime(1200, t);
        gain.gain.setValueAtTime(0.1, t);
        gain.gain.setValueAtTime(0, t + 0.05);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.05);
      }
    } else if (type === "chime") {
      // Harmonic stack for a bell-like chime
      [440, 880, 1320, 1760].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, now);
        gain.gain.setValueAtTime(0.1 / (i + 1), now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 1.2);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(now + 1.2);
      });
    } else {
      // Standard "beep" (default)
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, now);
      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(now + 0.2);
    }
  } catch (e) {
    console.warn("Failed to play synthesized sound:", e);
  }
};
