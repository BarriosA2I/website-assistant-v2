// components/progress/ProgressIndicator.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v3.0 — PROGRESS INDICATOR
// ============================================================================
// Shows 4-card completion progress for commercial brief creation
// ============================================================================

"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  User,
  Target,
  FileText,
  TrendingUp,
  Check,
  Circle,
  Loader2,
} from "lucide-react";

// =============================================================================
// TYPES
// =============================================================================

type CardStatus = "missing" | "partial" | "complete";

interface CardProgress {
  persona: CardStatus;
  competitor: CardStatus;
  script: CardStatus;
  roi: CardStatus;
  complete_count: number;
  all_complete: boolean;
}

interface ProgressIndicatorProps {
  progress: CardProgress;
  variant?: "compact" | "expanded";
  className?: string;
}

// =============================================================================
// CARD CONFIG
// =============================================================================

const CARD_CONFIG = [
  { key: "persona", label: "Persona", shortLabel: "P", icon: User, color: "purple" },
  { key: "competitor", label: "Competitor", shortLabel: "C", icon: Target, color: "red" },
  { key: "script", label: "Script", shortLabel: "S", icon: FileText, color: "cyan" },
  { key: "roi", label: "ROI", shortLabel: "R", icon: TrendingUp, color: "emerald" },
] as const;

const COLOR_MAP = {
  purple: {
    bg: "bg-purple-500/20",
    border: "border-purple-500/30",
    text: "text-purple-400",
    glow: "shadow-purple-500/20",
  },
  red: {
    bg: "bg-red-500/20",
    border: "border-red-500/30",
    text: "text-red-400",
    glow: "shadow-red-500/20",
  },
  cyan: {
    bg: "bg-cyan-500/20",
    border: "border-cyan-500/30",
    text: "text-cyan-400",
    glow: "shadow-cyan-500/20",
  },
  emerald: {
    bg: "bg-emerald-500/20",
    border: "border-emerald-500/30",
    text: "text-emerald-400",
    glow: "shadow-emerald-500/20",
  },
};

// =============================================================================
// COMPACT VARIANT
// =============================================================================

const CompactIndicator: React.FC<{ progress: CardProgress; className?: string }> = ({
  progress,
  className,
}) => {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      {CARD_CONFIG.map((card) => {
        const status = progress[card.key as keyof CardProgress] as CardStatus;
        const colors = COLOR_MAP[card.color];
        
        return (
          <motion.div
            key={card.key}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className={cn(
              "w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold",
              "transition-all duration-300",
              status === "complete" && [colors.bg, colors.text, "shadow-sm", colors.glow],
              status === "partial" && ["bg-slate-700", "text-slate-400", "animate-pulse"],
              status === "missing" && ["bg-slate-800", "text-slate-600"]
            )}
            title={`${card.label}: ${status}`}
          >
            {status === "complete" ? (
              <Check className="w-3 h-3" />
            ) : status === "partial" ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              card.shortLabel
            )}
          </motion.div>
        );
      })}
      
      {/* Counter */}
      <span className="ml-2 text-xs text-slate-500">
        {progress.complete_count}/4
      </span>
    </div>
  );
};

// =============================================================================
// EXPANDED VARIANT
// =============================================================================

const ExpandedIndicator: React.FC<{ progress: CardProgress; className?: string }> = ({
  progress,
  className,
}) => {
  return (
    <div className={cn("space-y-2", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-300">
          Commercial Brief Progress
        </span>
        <span
          className={cn(
            "text-sm font-bold",
            progress.all_complete ? "text-emerald-400" : "text-cyan-400"
          )}
        >
          {progress.complete_count}/4 Complete
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
        <motion.div
          className={cn(
            "h-full rounded-full",
            progress.all_complete
              ? "bg-gradient-to-r from-emerald-500 to-cyan-500"
              : "bg-gradient-to-r from-purple-500 to-cyan-500"
          )}
          initial={{ width: 0 }}
          animate={{ width: `${(progress.complete_count / 4) * 100}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>

      {/* Card items */}
      <div className="grid grid-cols-4 gap-2">
        {CARD_CONFIG.map((card) => {
          const status = progress[card.key as keyof CardProgress] as CardStatus;
          const colors = COLOR_MAP[card.color];
          const Icon = card.icon;
          
          return (
            <motion.div
              key={card.key}
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className={cn(
                "p-3 rounded-xl flex flex-col items-center gap-1.5",
                "border transition-all duration-300",
                status === "complete" && [
                  colors.bg,
                  colors.border,
                  "shadow-sm",
                  colors.glow,
                ],
                status === "partial" && [
                  "bg-slate-800/50",
                  "border-slate-700",
                  "animate-pulse",
                ],
                status === "missing" && [
                  "bg-slate-900/50",
                  "border-slate-800",
                ]
              )}
            >
              <div
                className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center",
                  status === "complete" && colors.text,
                  status === "partial" && "text-slate-400",
                  status === "missing" && "text-slate-600"
                )}
              >
                {status === "complete" ? (
                  <Check className="w-4 h-4" />
                ) : status === "partial" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
              </div>
              <span
                className={cn(
                  "text-[10px] font-medium",
                  status === "complete" && colors.text,
                  status === "partial" && "text-slate-400",
                  status === "missing" && "text-slate-600"
                )}
              >
                {card.label}
              </span>
            </motion.div>
          );
        })}
      </div>

      {/* Status message */}
      {progress.all_complete ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-2"
        >
          <span className="text-sm text-emerald-400">
            ✨ All cards complete! Ready for checkout.
          </span>
        </motion.div>
      ) : (
        <div className="text-center py-1">
          <span className="text-xs text-slate-500">
            {getNextCardMessage(progress)}
          </span>
        </div>
      )}
    </div>
  );
};

function getNextCardMessage(progress: CardProgress): string {
  if (progress.persona !== "complete") return "Next: Define your target persona";
  if (progress.competitor !== "complete") return "Next: Analyze your competition";
  if (progress.script !== "complete") return "Next: Create your script";
  if (progress.roi !== "complete") return "Next: Calculate your ROI";
  return "";
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  progress,
  variant = "compact",
  className,
}) => {
  if (variant === "compact") {
    return <CompactIndicator progress={progress} className={className} />;
  }
  
  return <ExpandedIndicator progress={progress} className={className} />;
};

// =============================================================================
// FLOATING PROGRESS BADGE
// =============================================================================

interface FloatingProgressBadgeProps {
  progress: CardProgress;
  onClick?: () => void;
  className?: string;
}

export const FloatingProgressBadge: React.FC<FloatingProgressBadgeProps> = ({
  progress,
  onClick,
  className,
}) => {
  if (progress.complete_count === 0) return null;

  return (
    <motion.button
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0, opacity: 0 }}
      onClick={onClick}
      className={cn(
        "fixed bottom-24 right-6 z-40",
        "px-4 py-2 rounded-full",
        "bg-slate-900/95 border border-slate-700",
        "shadow-lg backdrop-blur-sm",
        "flex items-center gap-2",
        "hover:border-cyan-500/50 transition-colors",
        className
      )}
    >
      <CompactIndicator progress={progress} />
      
      {progress.all_complete && (
        <motion.span
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="text-xs text-emerald-400 font-medium ml-2"
        >
          Ready!
        </motion.span>
      )}
    </motion.button>
  );
};

// =============================================================================
// EXPORTS
// =============================================================================

export default ProgressIndicator;
export type { CardProgress, CardStatus };
