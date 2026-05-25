import { motion, AnimatePresence } from 'framer-motion';
import { Terminal } from 'lucide-react';
import { useT } from '@/i18n';
import { CONSOLE_LINES } from '../demoScript';
import ScoreCard from './ScoreCard';

interface Props {
  elapsedMs: number;
}

export default function RightPane({ elapsedMs }: Props) {
  const t = useT();
  const visibleConsole = CONSOLE_LINES.filter((l) => elapsedMs >= l.appearAt);

  return (
    <div className="col-span-12 md:col-span-5 flex flex-col bg-brand-ink-900/80 min-h-0 border-l border-white/5">
      {/* Console */}
      <div className="border-b border-white/10">
        <div className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono text-white/50">
          <Terminal className="w-3 h-3" />
          <span>ai-console</span>
        </div>
        <div className="px-4 pb-3 space-y-1 font-mono text-xs text-white/70 min-h-[5rem]">
          <AnimatePresence initial={false}>
            {visibleConsole.map((line) => (
              <motion.div
                key={line.key}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25 }}
              >
                {t.demo.console[line.key]}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      {/* Score card area */}
      <div className="p-4 min-h-[12rem]">
        <ScoreCard elapsedMs={elapsedMs} />
      </div>

      {/* Inbox area — filled in Task 9 */}
      <div className="flex-1 px-4 pb-4 text-xs font-mono text-white/30">[inbox — task 9]</div>
    </div>
  );
}
