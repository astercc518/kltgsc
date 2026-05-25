import { motion } from 'framer-motion';
import { Users } from 'lucide-react';
import { useT } from '@/i18n';
import { SCRIPTED_MESSAGES } from '../demoScript';
import MessageBubble from './MessageBubble';

interface Props {
  elapsedMs: number;
}

export default function LeftPane({ elapsedMs }: Props) {
  const t = useT();
  const visibleMessages = SCRIPTED_MESSAGES.filter((m) => elapsedMs >= m.appearAt);

  return (
    <div className="col-span-12 md:col-span-7 flex flex-col bg-brand-ink-950/60 min-h-0">
      {/* Group rail */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 overflow-x-auto">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="flex items-center gap-2 rounded-full bg-white/[0.04] border border-white/10 px-3 py-1 text-xs text-white/70 shrink-0"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
            </span>
            <Users className="w-3 h-3" />
            <span>{t.demo.groups[`g${i}` as 'g0' | 'g1' | 'g2']}</span>
          </div>
        ))}
      </div>

      {/* Message stream */}
      <div className="flex-1 px-4 py-3 space-y-2 overflow-y-auto min-h-0">
        {visibleMessages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            className="text-xs font-mono text-white/40"
          >
            {t.demo.badge}…
          </motion.div>
        ) : (
          visibleMessages.map((m) => (
            <MessageBubble key={m.id} message={m} elapsedMs={elapsedMs} />
          ))
        )}
      </div>
    </div>
  );
}
