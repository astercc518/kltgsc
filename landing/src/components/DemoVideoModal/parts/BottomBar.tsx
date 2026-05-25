import { Pause, Play, RotateCcw } from 'lucide-react';
import { useT } from '@/i18n';
import { ACT_BOUNDARIES } from '../useTimeline';
import { kpiRate, kpiCaptured, DURATION_MS } from '../demoScript';

interface Props {
  elapsedMs: number;
  paused: boolean;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
}

export default function BottomBar({ elapsedMs, paused, onPause, onResume, onRestart }: Props) {
  const t = useT();
  const rate = kpiRate(elapsedMs);
  const captured = kpiCaptured(elapsedMs);

  return (
    <div className="border-t border-white/10 px-5 py-3 flex items-center gap-5 bg-black/30">
      {/* KPIs */}
      <div className="flex items-center gap-5 text-xs font-mono text-white/70">
        <div>
          <span className="text-white/40">{t.demo.kpi.rate} </span>
          <span className="text-white tabular-nums">{rate}{t.demo.kpi.rateUnit}</span>
        </div>
        <div>
          <span className="text-white/40">{t.demo.kpi.captured} </span>
          <span className="text-white tabular-nums">{captured}</span>
        </div>
      </div>

      {/* Segmented progress (4 acts) */}
      <div className="flex-1 flex items-center gap-1">
        {[0, 1, 2, 3].map((i) => {
          const start = ACT_BOUNDARIES[i];
          const end = ACT_BOUNDARIES[i + 1];
          const segProgress = Math.max(0, Math.min(1, (elapsedMs - start) / (end - start)));
          return (
            <div key={i} className="flex-1 h-1 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-blue-500 to-brand-purple-500 transition-[width] duration-100"
                style={{ width: `${segProgress * 100}%` }}
              />
            </div>
          );
        })}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-1">
        {paused ? (
          elapsedMs >= DURATION_MS ? (
            <button
              type="button"
              onClick={onRestart}
              aria-label={t.demo.controls.restart}
              className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onResume}
              aria-label={t.demo.controls.resume}
              className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <Play className="w-4 h-4" />
            </button>
          )
        ) : (
          <button
            type="button"
            onClick={onPause}
            aria-label={t.demo.controls.pause}
            className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Pause className="w-4 h-4" />
          </button>
        )}
        {!(paused && elapsedMs >= DURATION_MS) && (
          <button
            type="button"
            onClick={onRestart}
            aria-label={t.demo.controls.restart}
            className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
