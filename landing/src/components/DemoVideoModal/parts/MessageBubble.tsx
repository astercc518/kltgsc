import { motion } from 'framer-motion';
import { useT } from '@/i18n';
import type { ScriptedMessage } from '../demoScript';
import { SCAN_START_MS, SCAN_END_MS, SCORE_APPEAR_MS } from '../demoScript';

interface Props {
  message: ScriptedMessage;
  elapsedMs: number;
}

export default function MessageBubble({ message, elapsedMs }: Props) {
  const t = useT();
  const sender = t.demo.senders[message.senderKey];
  const text = t.demo.messages[message.messageKey];

  const scanning = message.highIntent && elapsedMs >= SCAN_START_MS && elapsedMs < SCAN_END_MS;
  const scored = message.highIntent && elapsedMs >= SCORE_APPEAR_MS;
  const dimmed = !message.highIntent && elapsedMs >= SCAN_START_MS;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: dimmed ? 0.25 : 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className={[
        'relative rounded-lg px-3 py-2 max-w-[85%] text-sm transition-colors',
        scored ? 'bg-brand-blue-500/10 border border-brand-blue-400/40' : 'bg-white/[0.06] border border-white/10',
      ].join(' ')}
    >
      <div className="flex items-baseline gap-2 mb-0.5">
        <span className="text-xs font-medium text-brand-blue-300">{sender}</span>
      </div>
      <p className="text-white/85 leading-snug">{text}</p>

      {scanning && (
        <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg">
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: '100%' }}
            transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
            className="h-full w-1/3 bg-gradient-to-r from-transparent via-brand-blue-400/40 to-transparent"
          />
        </div>
      )}
    </motion.div>
  );
}
