// components/generative-ui/CompetitorCard.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — COMPETITOR ANALYSIS CARD
// ============================================================================
// Visual: "Vs. Mode" layout with red vs green stats
// Style: Cyberpunk/HUD aesthetic with neon highlights
// ============================================================================

"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  CompetitorAnalysisCard,
  CompetitorStat,
  Advantage,
} from "@/lib/types/generative-ui";
import { cn } from "@/lib/utils";
import {
  Shield,
  Target,
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  ExternalLink,
  Clock,
  AlertCircle,
} from "lucide-react";

interface CompetitorCardProps {
  data: CompetitorAnalysisCard;
  className?: string;
  onViewDetails?: () => void;
}

// ============================================================================
// STAT ROW COMPONENT
// ============================================================================

interface StatRowProps {
  stat: CompetitorStat;
  index: number;
}

const StatRow: React.FC<StatRowProps> = ({ stat, index }) => {
  const getAdvantageStyles = (advantage: Advantage) => {
    switch (advantage) {
      case "us":
        return {
          ourBg: "bg-emerald-500/20 border-emerald-400",
          ourText: "text-emerald-400",
          theirBg: "bg-red-500/10 border-red-400/30",
          theirText: "text-red-400/70",
          icon: <TrendingUp className="w-4 h-4 text-emerald-400" />,
        };
      case "them":
        return {
          ourBg: "bg-red-500/10 border-red-400/30",
          ourText: "text-red-400/70",
          theirBg: "bg-red-500/20 border-red-400",
          theirText: "text-red-400",
          icon: <TrendingDown className="w-4 h-4 text-red-400" />,
        };
      default:
        return {
          ourBg: "bg-slate-500/20 border-slate-400/50",
          ourText: "text-slate-300",
          theirBg: "bg-slate-500/20 border-slate-400/50",
          theirText: "text-slate-300",
          icon: <Minus className="w-4 h-4 text-slate-400" />,
        };
    }
  };

  const styles = getAdvantageStyles(stat.advantage);

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 + 0.2 }}
      className="grid grid-cols-[1fr_2fr_2fr] gap-3 items-center py-3 border-b border-slate-700/50 last:border-b-0"
    >
      {/* Metric Name */}
      <div className="flex items-center gap-2">
        {styles.icon}
        <span className="text-sm font-medium text-slate-300 truncate">
          {stat.metric}
        </span>
      </div>

      {/* Our Value */}
      <div
        className={cn(
          "px-3 py-2 rounded-lg border text-center",
          styles.ourBg,
          "border",
          stat.advantage === "us" && "ring-1 ring-emerald-400/50"
        )}
      >
        <span className={cn("text-sm font-bold", styles.ourText)}>
          {stat.our_value}
        </span>
        {stat.advantage === "us" && stat.delta_percent && (
          <span className="ml-2 text-xs text-emerald-300">
            +{stat.delta_percent.toFixed(0)}%
          </span>
        )}
      </div>

      {/* Their Value */}
      <div
        className={cn(
          "px-3 py-2 rounded-lg border text-center",
          styles.theirBg
        )}
      >
        <span className={cn("text-sm font-medium", styles.theirText)}>
          {stat.their_value}
        </span>
      </div>
    </motion.div>
  );
};

// ============================================================================
// KILL SHOT COMPONENT
// ============================================================================

interface KillShotProps {
  headline: string;
  detail: string;
  proofPoint?: string | null;
}

const KillShotSection: React.FC<KillShotProps> = ({
  headline,
  detail,
  proofPoint,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.5 }}
      className="relative mt-6 p-5 rounded-xl bg-gradient-to-r from-cyan-500/10 via-purple-500/10 to-pink-500/10 border border-cyan-400/30"
    >
      {/* Neon glow effect */}
      <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-cyan-500/5 via-purple-500/5 to-pink-500/5 blur-xl" />

      {/* Corner accents */}
      <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-cyan-400 rounded-tl-lg" />
      <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-cyan-400 rounded-tr-lg" />
      <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-cyan-400 rounded-bl-lg" />
      <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-cyan-400 rounded-br-lg" />

      <div className="relative">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-5 h-5 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
            Kill Shot
          </span>
        </div>

        <h3 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 mb-2">
          {headline}
        </h3>

        <p className="text-sm text-slate-300 leading-relaxed">{detail}</p>

        {proofPoint && (
          <div className="mt-3 flex items-start gap-2 p-2 rounded-lg bg-slate-800/50">
            <Shield className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
            <span className="text-xs text-slate-400">{proofPoint}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const CompetitorCard: React.FC<CompetitorCardProps> = ({
  data,
  className,
  onViewDetails,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "relative overflow-hidden rounded-2xl",
        "bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950",
        "border border-slate-700/50",
        "shadow-2xl shadow-cyan-500/10",
        className
      )}
    >
      {/* Scan line effect */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute inset-0 bg-[linear-gradient(transparent_0%,transparent_50%,rgba(6,182,212,0.03)_50%,transparent_100%)] bg-[length:100%_4px]" />
      </div>

      {/* Header */}
      <div className="relative px-6 py-4 border-b border-slate-700/50 bg-gradient-to-r from-slate-800/50 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Our Logo */}
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <span className="text-xl font-black text-white">A2I</span>
            </div>

            <div className="text-2xl font-bold text-slate-400">VS</div>

            {/* Competitor Logo */}
            <div className="w-12 h-12 rounded-xl bg-slate-700 border border-slate-600 flex items-center justify-center">
              {data.competitor_logo_url ? (
                <img
                  src={data.competitor_logo_url}
                  alt={data.competitor_name}
                  className="w-8 h-8 object-contain"
                />
              ) : (
                <span className="text-lg font-bold text-slate-400">
                  {data.competitor_name.charAt(0)}
                </span>
              )}
            </div>
          </div>

          <div className="text-right">
            <h2 className="text-lg font-bold text-white">
              {data.competitor_name}
            </h2>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Clock className="w-3 h-3" />
              {data.data_freshness}
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="px-6 py-4">
        {/* Header Row */}
        <div className="grid grid-cols-[1fr_2fr_2fr] gap-3 pb-3 mb-2 border-b border-slate-600">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Metric
          </span>
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 text-center">
            Barrios A2I
          </span>
          <span className="text-xs font-semibold uppercase tracking-wider text-red-400 text-center">
            {data.competitor_name}
          </span>
        </div>

        {/* Stat Rows */}
        {data.stats.map((stat, index) => (
          <StatRow key={stat.metric} stat={stat} index={index} />
        ))}
      </div>

      {/* Kill Shot */}
      <div className="px-6 pb-6">
        <KillShotSection
          headline={data.kill_shot.headline}
          detail={data.kill_shot.detail}
          proofPoint={data.kill_shot.proof_point}
        />
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-slate-700/50 bg-slate-900/50">
        <div className="flex items-center justify-between">
          {/* Confidence Score */}
          <div className="flex items-center gap-2">
            <div className="relative w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${data.confidence_score * 100}%` }}
                transition={{ delay: 0.8, duration: 0.5 }}
                className={cn(
                  "absolute inset-y-0 left-0 rounded-full",
                  data.confidence_score >= 0.8
                    ? "bg-emerald-400"
                    : data.confidence_score >= 0.6
                    ? "bg-yellow-400"
                    : "bg-orange-400"
                )}
              />
            </div>
            <span className="text-xs text-slate-400">
              {(data.confidence_score * 100).toFixed(0)}% confidence
            </span>
          </div>

          {/* Sources */}
          {data.sources.length > 0 && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <AlertCircle className="w-3 h-3" />
              {data.sources.length} source{data.sources.length > 1 ? "s" : ""}
            </div>
          )}

          {/* Action Button */}
          {onViewDetails && (
            <button
              onClick={onViewDetails}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 text-xs font-medium hover:bg-cyan-500/20 transition-colors"
            >
              Full Report
              <ExternalLink className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default CompetitorCard;
