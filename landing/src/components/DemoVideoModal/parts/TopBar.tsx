import { forwardRef } from 'react';
import { X } from 'lucide-react';
import { useT } from '@/i18n';
import type { Act } from '../useTimeline';

interface Props {
  act: Act;
  onClose: () => void;
}

const actKey: Record<Act, 'listening' | 'incoming' | 'scoring' | 'handover'> = {
  1: 'listening', 2: 'incoming', 3: 'scoring', 4: 'handover',
};

const TopBar = forwardRef<HTMLButtonElement, Props>(function TopBar({ act, onClose }, closeBtnRef) {
  const t = useT();
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
      <div className="flex items-center gap-3 min-w-0">
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
        </span>
        <h2 id="demo-modal-title" className="font-display text-base md:text-lg font-semibold text-white truncate">
          {t.demo.title}
        </h2>
        <span className="hidden md:inline-flex items-center rounded-full bg-white/10 border border-white/15 px-2.5 py-0.5 text-xs font-mono text-white/70">
          {t.demo.acts[actKey[act]]}
        </span>
      </div>
      <button
        ref={closeBtnRef}
        type="button"
        onClick={onClose}
        className="text-white/60 hover:text-white p-1.5 rounded-full hover:bg-white/10 transition-colors"
        aria-label={t.demo.controls.close}
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  );
});

export default TopBar;
