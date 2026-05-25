/**
 * Static, tabbed alternative shown when user prefers reduced motion.
 * Renders the same Left/Right panes but pinned to the end-state of
 * the selected act (no raf, no scan, no flying card).
 */
import { MotionConfig } from 'framer-motion';
import { useT } from '@/i18n';
import { ACT_BOUNDARIES, type Act } from '../useTimeline';
import LeftPane from './LeftPane';
import RightPane from './RightPane';

const ACT_END_ELAPSED: Record<Act, number> = {
  1: ACT_BOUNDARIES[1] - 1,
  2: ACT_BOUNDARIES[2] - 1,
  3: ACT_BOUNDARIES[3] - 1,
  4: ACT_BOUNDARIES[4] - 1,
};

const ACTS: Act[] = [1, 2, 3, 4];

interface Props {
  act: Act;
  onActChange: (act: Act) => void;
}

export default function ReducedFallback({ act, onActChange }: Props) {
  const t = useT();
  const elapsed = ACT_END_ELAPSED[act];
  const actKey: Record<Act, 'listening' | 'incoming' | 'scoring' | 'handover'> = {
    1: 'listening', 2: 'incoming', 3: 'scoring', 4: 'handover',
  };

  return (
    <MotionConfig reducedMotion="always">
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-5 py-2.5 border-b border-white/10 flex items-center gap-1 overflow-x-auto">
        <span className="text-xs text-white/50 mr-2 shrink-0">{t.demo.reduced.intro}</span>
        {ACTS.map((a) => (
          <button
            key={a}
            type="button"
            onClick={() => onActChange(a)}
            className={[
              'shrink-0 rounded-full px-3 py-1 text-xs font-mono transition-colors',
              act === a
                ? 'bg-brand-blue-500/20 text-brand-blue-200 border border-brand-blue-400/40'
                : 'text-white/60 hover:text-white border border-transparent hover:bg-white/5',
            ].join(' ')}
          >
            {t.demo.acts[actKey[a]]}
          </button>
        ))}
      </div>
      <div className="flex-1 grid grid-cols-12 gap-px min-h-0">
        <LeftPane elapsedMs={elapsed} />
        <RightPane elapsedMs={elapsed} />
      </div>
    </div>
    </MotionConfig>
  );
}
