import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { useT } from '@/i18n';
import { SCORE_APPEAR_MS, SCORE_FLY_MS } from '../demoScript';

interface Props {
  elapsedMs: number;
}

export default function ScoreCard({ elapsedMs }: Props) {
  const t = useT();
  if (elapsedMs < SCORE_APPEAR_MS) return null;
  const flying = elapsedMs >= SCORE_FLY_MS;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={
        flying
          ? { opacity: 0, y: -40, scale: 0.7, transition: { duration: 0.5 } }
          : { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } }
      }
      className="rounded-xl border border-brand-blue-400/40 bg-gradient-to-br from-brand-blue-500/15 to-brand-purple-500/10 p-3.5 backdrop-blur-sm"
    >
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-1.5 text-xs font-mono text-brand-blue-300">
          <Sparkles className="w-3 h-3" />
          <span>{t.demo.score.label}</span>
        </div>
        <div className="font-display text-2xl font-bold text-white tabular-nums">92</div>
      </div>
      <dl className="space-y-1.5 text-xs">
        <div className="flex justify-between gap-3">
          <dt className="text-white/50">{t.demo.score.keywords}</dt>
          <dd className="text-white/85 text-right">USDT · cross-border</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-white/50">{t.demo.score.persona}</dt>
          <dd className="text-white/85 text-right">{t.demo.score.personaValue}</dd>
        </div>
        <div>
          <dt className="text-white/50 mb-1">{t.demo.score.suggestion}</dt>
          <dd className="text-white/85 leading-snug bg-white/[0.04] rounded-md px-2 py-1.5 border border-white/5">
            {t.demo.score.suggestionValue}
          </dd>
        </div>
      </dl>
    </motion.div>
  );
}
