// components/generative-ui/PersonaCard.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — PERSONA CARD
// ============================================================================
// Visual: ID Card style with avatar, income progress bar, pain points
// Style: Cyberpunk/HUD aesthetic with holographic effects
// ============================================================================

"use client";

import React from "react";
import { motion } from "framer-motion";
import { PersonaCard as PersonaCardType, PainPoint, Severity } from "@/lib/types/generative-ui";
import { cn } from "@/lib/utils";
import {
  User,
  Briefcase,
  Building2,
  DollarSign,
  AlertTriangle,
  Target,
  ShieldAlert,
  Clock,
  ChevronRight,
  Sparkles,
} from "lucide-react";

interface PersonaCardProps {
  data: PersonaCardType;
  className?: string;
  onExpand?: () => void;
}

// ============================================================================
// SEVERITY BADGE
// ============================================================================

const SeverityBadge: React.FC<{ severity: Severity }> = ({ severity }) => {
  const styles = {
    low: "bg-blue-500/20 text-blue-400 border-blue-400/30",
    medium: "bg-yellow-500/20 text-yellow-400 border-yellow-400/30",
    high: "bg-orange-500/20 text-orange-400 border-orange-400/30",
    critical: "bg-red-500/20 text-red-400 border-red-400/30",
  };

  return (
    <span
      className={cn(
        "px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full border",
        styles[severity]
      )}
    >
      {severity}
    </span>
  );
};

// ============================================================================
// PAIN POINT ROW
// ============================================================================

interface PainPointRowProps {
  painPoint: PainPoint;
  index: number;
}

const PainPointRow: React.FC<PainPointRowProps> = ({ painPoint, index }) => {
  const severityColors = {
    low: "border-l-blue-400",
    medium: "border-l-yellow-400",
    high: "border-l-orange-400",
    critical: "border-l-red-400",
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 + 0.3 }}
      className={cn(
        "p-3 rounded-r-lg bg-slate-800/50 border-l-2",
        severityColors[painPoint.severity]
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-slate-200">
            {painPoint.title}
          </h4>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed">
            {painPoint.description}
          </p>
        </div>
        <SeverityBadge severity={painPoint.severity} />
      </div>
    </motion.div>
  );
};

// ============================================================================
// AUTHORITY BADGE
// ============================================================================

const AuthorityBadge: React.FC<{ authority: string }> = ({ authority }) => {
  const config = {
    none: { label: "No Authority", color: "bg-slate-600 text-slate-300" },
    influence: { label: "Influencer", color: "bg-blue-600 text-blue-100" },
    approve: { label: "Approver", color: "bg-purple-600 text-purple-100" },
    final_decision: { label: "Decision Maker", color: "bg-emerald-600 text-emerald-100" },
  };

  const { label, color } = config[authority as keyof typeof config] || config.none;

  return (
    <span className={cn("px-2 py-1 text-xs font-semibold rounded-md", color)}>
      {label}
    </span>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const PersonaCard: React.FC<PersonaCardProps> = ({
  data,
  className,
  onExpand,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "relative overflow-hidden rounded-2xl",
        "bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/50",
        "border border-slate-700/50",
        "shadow-2xl shadow-indigo-500/10",
        className
      )}
    >
      {/* Holographic shimmer effect */}
      <div className="absolute inset-0 pointer-events-none opacity-30">
        <div className="absolute inset-0 bg-gradient-to-br from-transparent via-indigo-500/10 to-transparent" />
      </div>

      {/* ID Card Header - Avatar Section */}
      <div className="relative px-6 pt-6 pb-4">
        <div className="flex items-start gap-5">
          {/* Avatar */}
          <div className="relative">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 p-0.5 shadow-lg shadow-indigo-500/30">
              <div className="w-full h-full rounded-xl bg-slate-900 flex items-center justify-center overflow-hidden">
                {data.avatar_url ? (
                  <img
                    src={data.avatar_url}
                    alt={data.persona_name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <User className="w-10 h-10 text-slate-400" />
                )}
              </div>
            </div>
            {/* Online indicator */}
            <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 border-2 border-slate-900 flex items-center justify-center">
              <Sparkles className="w-3 h-3 text-white" />
            </div>
          </div>

          {/* Identity Info */}
          <div className="flex-1">
            <h2 className="text-xl font-bold text-white mb-1">
              {data.persona_name}
            </h2>
            <div className="flex items-center gap-2 text-sm text-slate-300 mb-2">
              <Briefcase className="w-4 h-4 text-indigo-400" />
              {data.title}
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Building2 className="w-3 h-3" />
              {data.company_type}
            </div>
          </div>
        </div>

        {/* Quick Stats Row */}
        <div className="grid grid-cols-3 gap-3 mt-5">
          <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              Age Range
            </div>
            <div className="text-sm font-semibold text-white">{data.age_range}</div>
          </div>
          <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              Timeline
            </div>
            <div className="text-sm font-semibold text-white">{data.buying_timeline}</div>
          </div>
          <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              Authority
            </div>
            <AuthorityBadge authority={data.budget_authority} />
          </div>
        </div>
      </div>

      {/* Income Range with Progress Bar */}
      <div className="px-6 py-4 border-t border-slate-700/30">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium text-slate-300">
              Income Range
            </span>
          </div>
          <span className="text-sm font-bold text-emerald-400">
            {data.income_range}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="relative h-3 bg-slate-700 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${data.income_percentile * 100}%` }}
            transition={{ delay: 0.5, duration: 0.8, ease: "easeOut" }}
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-emerald-500 to-cyan-400 rounded-full"
          />
          {/* Glowing effect */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.6 }}
            transition={{ delay: 1 }}
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-emerald-400 to-cyan-300 rounded-full blur-sm"
            style={{ width: `${data.income_percentile * 100}%` }}
          />
        </div>
        <div className="text-xs text-slate-500 mt-1 text-right">
          Top {((1 - data.income_percentile) * 100).toFixed(0)}% income bracket
        </div>
      </div>

      {/* Pain Points */}
      <div className="px-6 py-4 border-t border-slate-700/30">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-4 h-4 text-orange-400" />
          <span className="text-sm font-semibold text-slate-200">
            Top Pain Points
          </span>
        </div>

        <div className="space-y-2">
          {data.pain_points.slice(0, 3).map((painPoint, index) => (
            <PainPointRow key={painPoint.title} painPoint={painPoint} index={index} />
          ))}
        </div>
      </div>

      {/* Goals & Objections */}
      <div className="px-6 py-4 border-t border-slate-700/30 grid grid-cols-2 gap-4">
        {/* Goals */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Goals
            </span>
          </div>
          <ul className="space-y-1.5">
            {data.goals.slice(0, 3).map((goal, index) => (
              <motion.li
                key={goal}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: index * 0.1 + 0.5 }}
                className="flex items-start gap-2 text-xs text-slate-300"
              >
                <ChevronRight className="w-3 h-3 text-cyan-400 mt-0.5 flex-shrink-0" />
                {goal}
              </motion.li>
            ))}
          </ul>
        </div>

        {/* Objections */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="w-4 h-4 text-red-400" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Objections
            </span>
          </div>
          <ul className="space-y-1.5">
            {data.objections.slice(0, 3).map((objection, index) => (
              <motion.li
                key={objection}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: index * 0.1 + 0.6 }}
                className="flex items-start gap-2 text-xs text-slate-300"
              >
                <ChevronRight className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
                {objection}
              </motion.li>
            ))}
          </ul>
        </div>
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-slate-700/30 bg-slate-900/50">
        <div className="flex items-center justify-between">
          {/* Confidence */}
          <div className="flex items-center gap-2">
            <div className="relative w-20 h-2 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${data.confidence_score * 100}%` }}
                transition={{ delay: 0.8, duration: 0.5 }}
                className="absolute inset-y-0 left-0 bg-indigo-400 rounded-full"
              />
            </div>
            <span className="text-xs text-slate-400">
              {(data.confidence_score * 100).toFixed(0)}% match
            </span>
          </div>

          {/* Expand Button */}
          {onExpand && (
            <button
              onClick={onExpand}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 text-xs font-medium hover:bg-indigo-500/20 transition-colors"
            >
              Full Profile
              <ChevronRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default PersonaCard;
