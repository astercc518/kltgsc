/**
 * Timeline script for DemoVideoModal.
 *
 * Each entry's `appearAt` is the ms offset when it should mount.
 * `highIntent: true` flags messages that get scanned + scored by AI
 * in act 3 — keep this in sync with the act boundaries.
 */
export const DURATION_MS = 75_000;

export interface ScriptedMessage {
  id: string;
  /** ms when bubble starts appearing. */
  appearAt: number;
  groupIdx: 0 | 1 | 2;
  senderKey: 's0' | 's1' | 's2' | 's3' | 's4' | 's5' | 's6' | 's7';
  messageKey: 'm0' | 'm1' | 'm2' | 'm3' | 'm4' | 'm5' | 'm6' | 'm7';
  highIntent?: boolean;
}

/** Messages flow during acts 2-3 (15s - 55s). */
export const SCRIPTED_MESSAGES: ScriptedMessage[] = [
  { id: 'msg-0', appearAt: 15_500, groupIdx: 0, senderKey: 's0', messageKey: 'm0' },
  { id: 'msg-1', appearAt: 17_500, groupIdx: 1, senderKey: 's1', messageKey: 'm1' },
  { id: 'msg-2', appearAt: 20_000, groupIdx: 2, senderKey: 's2', messageKey: 'm2' },
  { id: 'msg-3', appearAt: 23_000, groupIdx: 0, senderKey: 's3', messageKey: 'm3', highIntent: true },
  { id: 'msg-4', appearAt: 26_500, groupIdx: 1, senderKey: 's4', messageKey: 'm4' },
  { id: 'msg-5', appearAt: 28_500, groupIdx: 2, senderKey: 's5', messageKey: 'm5' },
  { id: 'msg-6', appearAt: 31_000, groupIdx: 1, senderKey: 's6', messageKey: 'm6', highIntent: true },
  { id: 'msg-7', appearAt: 33_500, groupIdx: 0, senderKey: 's7', messageKey: 'm7' },
];

export interface ConsoleLine {
  appearAt: number;
  key: 'line1' | 'line2' | 'line3' | 'line4';
}

export const CONSOLE_LINES: ConsoleLine[] = [
  { appearAt: 1_000,  key: 'line1' },
  { appearAt: 3_000,  key: 'line2' },
  { appearAt: 21_000, key: 'line3' },
  { appearAt: 42_000, key: 'line4' },
];

/** When the AI scan line sweeps over high-intent messages (act 3). */
export const SCAN_START_MS = 36_000;
export const SCAN_END_MS = 40_000;
/** When the score card pops up. */
export const SCORE_APPEAR_MS = 40_500;
/** When the score card "flies" into the inbox. */
export const SCORE_FLY_MS = 55_000;
/** When sales avatar + typing reply appears. */
export const SALES_TYPING_MS = 60_000;
/** Acts 2-4 ramp the "msg rate" KPI from 0 → 12. */
export function kpiRate(elapsedMs: number): number {
  if (elapsedMs < 15_000) return 0;
  const t = Math.min((elapsedMs - 15_000) / 20_000, 1);
  return Math.round(t * 12);
}

export function kpiCaptured(elapsedMs: number): number {
  return elapsedMs >= SCORE_FLY_MS ? 1 : 0;
}
