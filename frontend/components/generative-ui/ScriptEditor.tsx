// components/generative-ui/ScriptEditor.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — SCRIPT PREVIEW/EDITOR CARD
// ============================================================================
// Visual: Minimalist code editor style with action buttons
// Style: Dark IDE aesthetic with syntax highlighting for sections
// ============================================================================

"use client";

import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ScriptPreviewCard,
  ScriptSection,
  SectionType,
} from "@/lib/types/generative-ui";
import { cn } from "@/lib/utils";
import {
  FileText,
  Clock,
  RefreshCw,
  Check,
  X,
  Edit3,
  Copy,
  CheckCircle,
  Play,
  Pause,
  Type,
  Target,
  Sparkles,
  AlertCircle,
} from "lucide-react";

interface ScriptEditorProps {
  data: ScriptPreviewCard;
  className?: string;
  onRegenerate?: () => void;
  onApprove?: () => void;
  onReject?: () => void;
  onEdit?: (newContent: string) => void;
}

// ============================================================================
// SECTION TYPE CONFIG
// ============================================================================

const sectionConfig: Record<
  SectionType,
  { label: string; color: string; icon: React.ReactNode }
> = {
  hook: {
    label: "HOOK",
    color: "text-cyan-400 bg-cyan-400/10 border-cyan-400/30",
    icon: <Sparkles className="w-3 h-3" />,
  },
  problem: {
    label: "PROBLEM",
    color: "text-red-400 bg-red-400/10 border-red-400/30",
    icon: <AlertCircle className="w-3 h-3" />,
  },
  solution: {
    label: "SOLUTION",
    color: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
    icon: <Check className="w-3 h-3" />,
  },
  proof: {
    label: "PROOF",
    color: "text-purple-400 bg-purple-400/10 border-purple-400/30",
    icon: <Target className="w-3 h-3" />,
  },
  cta: {
    label: "CTA",
    color: "text-orange-400 bg-orange-400/10 border-orange-400/30",
    icon: <Play className="w-3 h-3" />,
  },
};

// ============================================================================
// SECTION BLOCK COMPONENT
// ============================================================================

interface SectionBlockProps {
  section: ScriptSection;
  index: number;
  isEditing: boolean;
  onContentChange?: (content: string) => void;
}

const SectionBlock: React.FC<SectionBlockProps> = ({
  section,
  index,
  isEditing,
  onContentChange,
}) => {
  const config = sectionConfig[section.section_type];
  const [localContent, setLocalContent] = useState(section.content);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="relative group"
    >
      {/* Section Label */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border",
            config.color
          )}
        >
          {config.icon}
          {config.label}
        </span>
        {section.duration_seconds && (
          <span className="text-[10px] text-slate-500">
            ~{section.duration_seconds}s
          </span>
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          "relative p-4 rounded-lg bg-slate-800/50 border transition-all",
          isEditing
            ? "border-cyan-400/50 ring-1 ring-cyan-400/20"
            : "border-slate-700/50 hover:border-slate-600/50"
        )}
      >
        {isEditing ? (
          <textarea
            value={localContent}
            onChange={(e) => {
              setLocalContent(e.target.value);
              onContentChange?.(e.target.value);
            }}
            className="w-full bg-transparent text-sm text-slate-200 leading-relaxed resize-none focus:outline-none min-h-[60px]"
            rows={3}
          />
        ) : (
          <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
            {section.content}
          </p>
        )}

        {/* Notes */}
        {section.notes && !isEditing && (
          <div className="mt-3 pt-3 border-t border-slate-700/30">
            <p className="text-xs text-slate-500 italic">{section.notes}</p>
          </div>
        )}

        {/* Line number decoration */}
        <div className="absolute left-0 top-0 bottom-0 w-8 -ml-4 flex flex-col items-center pt-4 opacity-30">
          {section.content.split("\n").map((_, i) => (
            <span key={i} className="text-[10px] text-slate-500 leading-relaxed">
              {index * 10 + i + 1}
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  );
};

// ============================================================================
// STATUS BADGE
// ============================================================================

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const styles = {
    draft: "bg-slate-600/50 text-slate-300 border-slate-500/50",
    pending_approval: "bg-yellow-500/20 text-yellow-400 border-yellow-400/30",
    approved: "bg-emerald-500/20 text-emerald-400 border-emerald-400/30",
    rejected: "bg-red-500/20 text-red-400 border-red-400/30",
  };

  const labels = {
    draft: "Draft",
    pending_approval: "Pending Review",
    approved: "Approved",
    rejected: "Rejected",
  };

  return (
    <span
      className={cn(
        "px-2 py-1 text-xs font-semibold rounded-md border",
        styles[status as keyof typeof styles] || styles.draft
      )}
    >
      {labels[status as keyof typeof labels] || status}
    </span>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const ScriptEditor: React.FC<ScriptEditorProps> = ({
  data,
  className,
  onRegenerate,
  onApprove,
  onReject,
  onEdit,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [editedSections, setEditedSections] = useState<Record<number, string>>(
    {}
  );

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(data.full_script);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [data.full_script]);

  const handleSaveEdit = () => {
    const newContent = data.sections
      .map((s, i) => editedSections[i] || s.content)
      .join("\n\n");
    onEdit?.(newContent);
    setIsEditing(false);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "relative overflow-hidden rounded-2xl",
        "bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950",
        "border border-slate-700/50",
        "shadow-2xl shadow-slate-950/50",
        className
      )}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700/50 bg-slate-800/30">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            {/* File Icon */}
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <FileText className="w-5 h-5 text-white" />
            </div>

            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                {data.title}
                <StatusBadge status={data.status} />
              </h2>
              <div className="flex items-center gap-4 mt-1 text-xs text-slate-400">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {data.format} format
                </span>
                <span className="flex items-center gap-1">
                  <Type className="w-3 h-3" />
                  {data.word_count} words
                </span>
                <span className="flex items-center gap-1">
                  <Play className="w-3 h-3" />
                  ~{data.estimated_duration_seconds}s
                </span>
              </div>
            </div>
          </div>

          {/* Revision Badge */}
          <div className="text-xs text-slate-500">
            v{data.revision_number}
          </div>
        </div>
      </div>

      {/* Metadata Bar */}
      <div className="px-6 py-3 border-b border-slate-700/30 bg-slate-800/20 flex items-center gap-4 overflow-x-auto">
        <div className="flex items-center gap-2 text-xs text-slate-400 whitespace-nowrap">
          <span className="text-slate-500">Platform:</span>
          <span className="font-medium text-slate-300 capitalize">
            {data.target_platform}
          </span>
        </div>
        <div className="w-px h-4 bg-slate-700" />
        <div className="flex items-center gap-2 text-xs text-slate-400 whitespace-nowrap">
          <span className="text-slate-500">Tone:</span>
          <span className="font-medium text-slate-300 capitalize">
            {data.tone}
          </span>
        </div>
        {data.target_persona && (
          <>
            <div className="w-px h-4 bg-slate-700" />
            <div className="flex items-center gap-2 text-xs text-slate-400 whitespace-nowrap">
              <span className="text-slate-500">Persona:</span>
              <span className="font-medium text-slate-300">
                {data.target_persona}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Script Content */}
      <div className="p-6 space-y-4 max-h-[400px] overflow-y-auto">
        {data.sections.map((section, index) => (
          <SectionBlock
            key={`${section.section_type}-${index}`}
            section={section}
            index={index}
            isEditing={isEditing}
            onContentChange={(content) =>
              setEditedSections((prev) => ({ ...prev, [index]: content }))
            }
          />
        ))}
      </div>

      {/* Action Bar */}
      <div className="px-6 py-4 border-t border-slate-700/50 bg-slate-900/70">
        <div className="flex items-center justify-between">
          {/* Left Actions */}
          <div className="flex items-center gap-2">
            {/* Copy Button */}
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-700/50 text-slate-300 text-xs font-medium hover:bg-slate-700 transition-colors"
            >
              {copied ? (
                <>
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  Copy
                </>
              )}
            </button>

            {/* Edit Toggle */}
            {data.can_edit && (
              <button
                onClick={() => {
                  if (isEditing) {
                    handleSaveEdit();
                  } else {
                    setIsEditing(true);
                  }
                }}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors",
                  isEditing
                    ? "bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30"
                    : "bg-slate-700/50 text-slate-300 hover:bg-slate-700"
                )}
              >
                <Edit3 className="w-3.5 h-3.5" />
                {isEditing ? "Save" : "Edit"}
              </button>
            )}
          </div>

          {/* Right Actions */}
          <div className="flex items-center gap-2">
            <AnimatePresence mode="wait">
              {isEditing ? (
                <motion.button
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  onClick={() => {
                    setIsEditing(false);
                    setEditedSections({});
                  }}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-700/50 text-slate-300 text-xs font-medium hover:bg-slate-700 transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                  Cancel
                </motion.button>
              ) : (
                <>
                  {/* Regenerate */}
                  {data.can_regenerate && onRegenerate && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      onClick={onRegenerate}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-500/20 text-purple-400 text-xs font-medium hover:bg-purple-500/30 transition-colors border border-purple-400/30"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      Regenerate
                    </motion.button>
                  )}

                  {/* Reject */}
                  {onReject && data.status === "pending_approval" && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      onClick={onReject}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/30 transition-colors border border-red-400/30"
                    >
                      <X className="w-3.5 h-3.5" />
                      Reject
                    </motion.button>
                  )}

                  {/* Approve */}
                  {data.can_approve && onApprove && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      onClick={onApprove}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-xs font-semibold hover:from-emerald-400 hover:to-cyan-400 transition-colors shadow-lg shadow-emerald-500/20"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Approve
                    </motion.button>
                  )}
                </>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ScriptEditor;
