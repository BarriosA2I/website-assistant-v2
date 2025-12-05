// components/generative-ui/DynamicCard.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — DYNAMIC CARD ROUTER
// ============================================================================
// Purpose: Routes render_card payloads to the correct React component
// Usage: <DynamicCard card={message.render_card} />
// ============================================================================

"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RenderCard,
  CardType,
  isCompetitorCard,
  isPersonaCard,
  isScriptCard,
  isROICard,
  isPricingCard,
  isTrendCard,
  isBriefReviewCard,
  isOrderTrackingCard,
} from "@/lib/types/generative-ui";
import { CompetitorCard } from "./CompetitorCard";
import { PersonaCard } from "./PersonaCard";
import { ScriptEditor } from "./ScriptEditor";
import { ROICalculator } from "./ROICalculator";
import { BriefReviewCard } from "./BriefReviewCard";
import { OrderTrackingCard } from "./OrderTrackingCard";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

// ============================================================================
// TYPES
// ============================================================================

interface DynamicCardProps {
  card: RenderCard;
  className?: string;
  // Action handlers
  onCompetitorDetails?: () => void;
  onPersonaExpand?: () => void;
  onScriptRegenerate?: () => void;
  onScriptApprove?: () => void;
  onScriptReject?: () => void;
  onScriptEdit?: (content: string) => void;
  onROICTA?: () => void;
  // v3.0 handlers
  onBriefApprove?: (updates: Record<string, string>) => void;
  onBriefRequestChanges?: (feedback: string) => void;
  onOrderDownload?: () => void;
}

// ============================================================================
// FALLBACK COMPONENT
// ============================================================================

const UnknownCard: React.FC<{ type: string }> = ({ type }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    className="p-6 rounded-2xl bg-slate-800/50 border border-yellow-500/30"
  >
    <div className="flex items-center gap-3">
      <AlertTriangle className="w-5 h-5 text-yellow-400" />
      <div>
        <p className="text-sm font-medium text-yellow-400">Unknown Card Type</p>
        <p className="text-xs text-slate-400 mt-1">
          Card type "{type}" is not yet supported. Please update the frontend.
        </p>
      </div>
    </div>
  </motion.div>
);

// ============================================================================
// PLACEHOLDER COMPONENTS (for Pricing and Trend cards)
// ============================================================================

const PricingComparisonCard: React.FC<{ data: any; className?: string }> = ({
  data,
  className,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className={cn(
      "p-6 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950",
      "border border-slate-700/50",
      className
    )}
  >
    <h3 className="text-lg font-bold text-white mb-4">{data.title}</h3>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {data.tiers?.map((tier: any, index: number) => (
        <div
          key={tier.name}
          className={cn(
            "p-4 rounded-xl border",
            tier.is_recommended
              ? "bg-cyan-500/10 border-cyan-400/50"
              : "bg-slate-800/50 border-slate-700"
          )}
        >
          {tier.is_recommended && (
            <span className="text-xs font-bold text-cyan-400 uppercase">
              Recommended
            </span>
          )}
          <h4 className="text-xl font-bold text-white mt-2">{tier.name}</h4>
          <div className="text-2xl font-black text-emerald-400 my-2">
            ${tier.price}
            <span className="text-sm font-normal text-slate-400">
              /{tier.period === "monthly" ? "mo" : tier.period}
            </span>
          </div>
          <ul className="space-y-1">
            {tier.features?.slice(0, 5).map((feature: string, i: number) => (
              <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                {feature}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  </motion.div>
);

const MarketTrendCard: React.FC<{ data: any; className?: string }> = ({
  data,
  className,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className={cn(
      "p-6 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950",
      "border border-slate-700/50",
      className
    )}
  >
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-lg font-bold text-white">{data.title}</h3>
      <span
        className={cn(
          "px-2 py-1 rounded-md text-xs font-bold",
          data.trend_direction === "up"
            ? "bg-emerald-500/20 text-emerald-400"
            : data.trend_direction === "down"
            ? "bg-red-500/20 text-red-400"
            : "bg-slate-500/20 text-slate-400"
        )}
      >
        {data.trend_direction === "up" ? "↑" : data.trend_direction === "down" ? "↓" : "→"}{" "}
        {data.trend_percent.toFixed(1)}%
      </span>
    </div>
    
    <div className="h-32 flex items-end gap-1">
      {data.data_points?.map((point: any, index: number) => (
        <div
          key={index}
          className="flex-1 bg-gradient-to-t from-cyan-500 to-cyan-400 rounded-t opacity-70 hover:opacity-100 transition-opacity"
          style={{
            height: `${(point.value / Math.max(...data.data_points.map((p: any) => p.value))) * 100}%`,
          }}
        />
      ))}
    </div>
    
    <p className="text-sm text-slate-300 mt-4">{data.insight}</p>
    <p className="text-xs text-cyan-400 mt-2">{data.recommendation}</p>
  </motion.div>
);

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const DynamicCard: React.FC<DynamicCardProps> = ({
  card,
  className,
  onCompetitorDetails,
  onPersonaExpand,
  onScriptRegenerate,
  onScriptApprove,
  onScriptReject,
  onScriptEdit,
  onROICTA,
  onBriefApprove,
  onBriefRequestChanges,
  onOrderDownload,
}) => {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={card.type}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.3 }}
        className={cn("w-full max-w-2xl", className)}
      >
        {isCompetitorCard(card) && (
          <CompetitorCard
            data={card}
            onViewDetails={onCompetitorDetails}
          />
        )}

        {isPersonaCard(card) && (
          <PersonaCard
            data={card}
            onExpand={onPersonaExpand}
          />
        )}

        {isScriptCard(card) && (
          <ScriptEditor
            data={card}
            onRegenerate={onScriptRegenerate}
            onApprove={onScriptApprove}
            onReject={onScriptReject}
            onEdit={onScriptEdit}
          />
        )}

        {isROICard(card) && (
          <ROICalculator
            data={card}
            onCTAClick={onROICTA}
          />
        )}

        {isPricingCard(card) && (
          <PricingComparisonCard data={card} />
        )}

        {isTrendCard(card) && (
          <MarketTrendCard data={card} />
        )}

        {isBriefReviewCard(card) && (
          <BriefReviewCard
            card={card as any}
            onApprove={onBriefApprove}
            onRequestChanges={onBriefRequestChanges}
          />
        )}

        {isOrderTrackingCard(card) && (
          <OrderTrackingCard
            card={card as any}
            onDownload={onOrderDownload}
          />
        )}

        {/* Fallback for unknown types */}
        {!isCompetitorCard(card) &&
          !isPersonaCard(card) &&
          !isScriptCard(card) &&
          !isROICard(card) &&
          !isPricingCard(card) &&
          !isTrendCard(card) &&
          !isBriefReviewCard(card) &&
          !isOrderTrackingCard(card) && <UnknownCard type={(card as any).type} />}
      </motion.div>
    </AnimatePresence>
  );
};

export default DynamicCard;
