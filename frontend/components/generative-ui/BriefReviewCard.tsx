"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  AlertTriangle,
  CheckCircle,
  Edit3,
  ChevronRight,
  Sparkles
} from "lucide-react";

interface BriefItem {
  label: string;
  value: string;
  editable: boolean;
  warning?: string;
}

interface BriefReviewCardProps {
  card: {
    card_type: "brief_review";
    title: string;
    subtitle: string;
    business_info: BriefItem[];
    creative_direction: BriefItem[];
    technical_specs: BriefItem[];
    validation_passed: boolean;
    validation_warnings: string[];
    can_proceed: boolean;
    proceed_label: string;
    edit_label: string;
    session_id: string;
    brief_version: number;
  };
  onApprove?: (updates: Record<string, string>) => void;
  onRequestChanges?: (feedback: string) => void;
}

export function BriefReviewCard({
  card,
  onApprove,
  onRequestChanges
}: BriefReviewCardProps) {
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [editingField, setEditingField] = useState<string | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFieldEdit = (label: string, value: string) => {
    setEditedValues(prev => ({ ...prev, [label]: value }));
  };

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      await onApprove?.(editedValues);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRequestChanges = async () => {
    if (!feedback.trim()) return;
    setIsSubmitting(true);
    try {
      await onRequestChanges?.(feedback);
    } finally {
      setIsSubmitting(false);
      setShowFeedback(false);
    }
  };

  const renderSection = (
    title: string,
    items: BriefItem[],
    icon: React.ReactNode
  ) => (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-mono uppercase tracking-wider text-cyan-400">
          {title}
        </h3>
      </div>
      <div className="space-y-2">
        {items.map((item, idx) => (
          <div
            key={idx}
            className={`
              p-3 rounded border transition-all
              ${item.warning
                ? 'border-amber-500/50 bg-amber-500/10'
                : 'border-cyan-500/30 bg-slate-800/50'}
              ${item.editable ? 'hover:border-cyan-400/50 cursor-pointer' : ''}
            `}
            onClick={() => item.editable && setEditingField(item.label)}
          >
            <div className="flex justify-between items-start">
              <span className="text-xs text-slate-400 uppercase tracking-wide">
                {item.label}
              </span>
              {item.editable && (
                <Edit3 className="w-3 h-3 text-slate-500" />
              )}
            </div>

            {editingField === item.label ? (
              <input
                type="text"
                className="w-full mt-1 bg-slate-900 border border-cyan-500 rounded px-2 py-1 text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                defaultValue={editedValues[item.label] || item.value}
                onChange={(e) => handleFieldEdit(item.label, e.target.value)}
                onBlur={() => setEditingField(null)}
                onKeyDown={(e) => e.key === 'Enter' && setEditingField(null)}
                autoFocus
              />
            ) : (
              <p className="text-white text-sm mt-1">
                {editedValues[item.label] || item.value}
              </p>
            )}

            {item.warning && (
              <div className="flex items-start gap-2 mt-2 p-2 bg-amber-500/20 rounded">
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-200">{item.warning}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-2xl mx-auto"
    >
      {/* Cyberpunk HUD Frame */}
      <div className="relative bg-slate-900/95 border border-cyan-500/50 rounded-lg overflow-hidden">
        {/* Scanline effect */}
        <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.1)_50%)] bg-[length:100%_4px]" />

        {/* Header */}
        <div className="relative p-4 border-b border-cyan-500/30 bg-gradient-to-r from-cyan-500/10 to-transparent">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded">
              <FileText className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white font-mono">
                {card.title}
              </h2>
              <p className="text-sm text-slate-400">{card.subtitle}</p>
            </div>
          </div>

          {/* Version badge */}
          <div className="absolute top-4 right-4 px-2 py-1 bg-slate-800 rounded text-xs text-slate-400 font-mono">
            v{card.brief_version}
          </div>
        </div>

        {/* Validation Status */}
        {!card.validation_passed && card.validation_warnings.length > 0 && (
          <div className="p-4 bg-amber-500/10 border-b border-amber-500/30">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium text-amber-400">
                Review Recommended
              </span>
            </div>
            <ul className="space-y-1">
              {card.validation_warnings.map((warning, idx) => (
                <li key={idx} className="text-xs text-amber-200 pl-6">
                  {warning}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Content */}
        <div className="p-4">
          {renderSection(
            "Business Information",
            card.business_info,
            <Sparkles className="w-4 h-4 text-cyan-400" />
          )}

          {renderSection(
            "Creative Direction",
            card.creative_direction,
            <Edit3 className="w-4 h-4 text-purple-400" />
          )}

          {renderSection(
            "Technical Specifications",
            card.technical_specs,
            <FileText className="w-4 h-4 text-emerald-400" />
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-cyan-500/30 bg-slate-800/50">
          <AnimatePresence mode="wait">
            {showFeedback ? (
              <motion.div
                key="feedback"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-3"
              >
                <textarea
                  className="w-full p-3 bg-slate-900 border border-cyan-500/50 rounded text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none"
                  rows={3}
                  placeholder="Describe the changes you'd like..."
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowFeedback(false)}
                    className="flex-1 py-2 px-4 border border-slate-600 rounded text-slate-400 hover:text-white hover:border-slate-500 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleRequestChanges}
                    disabled={!feedback.trim() || isSubmitting}
                    className="flex-1 py-2 px-4 bg-amber-500 text-black font-medium rounded hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isSubmitting ? "Sending..." : "Submit Feedback"}
                  </button>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="actions"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-3"
              >
                <button
                  onClick={() => setShowFeedback(true)}
                  className="flex-1 py-3 px-4 border border-slate-600 rounded text-slate-300 hover:text-white hover:border-slate-500 transition-colors flex items-center justify-center gap-2"
                >
                  <Edit3 className="w-4 h-4" />
                  {card.edit_label}
                </button>
                <button
                  onClick={handleApprove}
                  disabled={!card.can_proceed || isSubmitting}
                  className="flex-1 py-3 px-4 bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-medium rounded hover:from-cyan-400 hover:to-blue-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 group"
                >
                  {isSubmitting ? (
                    "Processing..."
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      {card.proceed_label}
                      <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

export default BriefReviewCard;
