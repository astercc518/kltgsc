import { motion } from 'framer-motion';
import { Inbox } from 'lucide-react';
import { useT } from '@/i18n';
import { SCORE_FLY_MS, SALES_TYPING_MS } from '../demoScript';

interface Props {
  elapsedMs: number;
}

export default function InboxItem({ elapsedMs }: Props) {
  const t = useT();
  if (elapsedMs < SCORE_FLY_MS) {
    return (
      <div className="flex items-center gap-2 text-xs font-mono text-white/30">
        <Inbox className="w-3 h-3" />
        <span>inbox · empty</span>
      </div>
    );
  }

  const typing = elapsedMs >= SALES_TYPING_MS;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs font-mono text-white/60">
        <div className="flex items-center gap-1.5">
          <Inbox className="w-3 h-3" />
          <span>inbox</span>
        </div>
        <motion.span
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 18 }}
          className="inline-flex items-center justify-center min-w-[1.25rem] h-5 rounded-full bg-brand-blue-500 text-white text-[10px] font-bold px-1.5"
        >
          +1
        </motion.span>
      </div>

      <motion.div
        initial={{ opacity: 0, y: -16, scale: 0.92 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="rounded-xl border border-white/10 bg-white/[0.04] p-3"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-brand-blue-300">{t.demo.senders.s3}</span>
          <span className="text-[10px] font-mono text-brand-blue-400 bg-brand-blue-500/15 border border-brand-blue-400/30 rounded-full px-1.5">
            {t.demo.score.label} 92
          </span>
        </div>
        <p className="text-xs text-white/70 leading-snug mb-3">
          {t.demo.messages.m3}
        </p>

        {typing && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="border-t border-white/10 pt-2.5 mt-2.5"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-5 h-5 rounded-full bg-gradient-to-br from-brand-blue-500 to-brand-purple-500 grid place-items-center text-[10px] font-bold text-white">A</div>
              <span className="text-xs font-medium text-white/80">{t.demo.handover.salesName}</span>
              <motion.span
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.4, repeat: Infinity }}
                className="text-[10px] font-mono text-white/40"
              >
                typing…
              </motion.span>
            </div>
            <p className="text-xs text-white/70 leading-snug pl-7">
              {t.demo.handover.salesReply}
            </p>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
