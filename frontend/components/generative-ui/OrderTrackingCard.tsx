"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Package,
  CreditCard,
  FileCheck,
  Cog,
  Truck,
  CheckCircle,
  AlertCircle,
  Download,
  ExternalLink,
  Clock,
  Zap
} from "lucide-react";

interface OrderPhase {
  id: string;
  name: string;
  status: "pending" | "active" | "completed" | "failed";
  started_at?: string;
  completed_at?: string;
  details?: string;
}

interface OrderTrackingCardProps {
  card: {
    card_type: "order_tracking";
    order_id: string;
    order_number: string;
    status: string;
    status_label: string;
    status_description: string;
    progress_percent: number;
    current_phase: string;
    phases: OrderPhase[];
    created_at: string;
    estimated_completion?: string;
    actual_completion?: string;
    video_url?: string;
    video_thumbnail?: string;
    download_expires_at?: string;
    can_cancel: boolean;
    can_download: boolean;
    support_url: string;
    session_id: string;
    last_updated: string;
  };
  onDownload?: () => void;
}

const phaseIcons: Record<string, React.ReactNode> = {
  payment: <CreditCard className="w-4 h-4" />,
  brief: <FileCheck className="w-4 h-4" />,
  production: <Cog className="w-4 h-4" />,
  delivery: <Truck className="w-4 h-4" />,
};

export function OrderTrackingCard({ card, onDownload }: OrderTrackingCardProps) {
  const [showConfetti, setShowConfetti] = useState(false);

  // Trigger confetti when delivered
  useEffect(() => {
    if (card.status === "delivered" && !showConfetti) {
      setShowConfetti(true);
      // Simple confetti effect using CSS animation instead of canvas-confetti
      // This avoids the need for an additional dependency
    }
  }, [card.status, showConfetti]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "text-emerald-400 border-emerald-400";
      case "active":
        return "text-cyan-400 border-cyan-400";
      case "failed":
        return "text-red-400 border-red-400";
      default:
        return "text-slate-500 border-slate-600";
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getTimeRemaining = () => {
    if (!card.estimated_completion) return null;
    const est = new Date(card.estimated_completion);
    const now = new Date();
    const diff = est.getTime() - now.getTime();
    if (diff <= 0) return "Any moment now...";
    const minutes = Math.ceil(diff / 60000);
    return `~${minutes} min remaining`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="w-full max-w-md"
    >
      {/* Cyberpunk HUD Container */}
      <div className="relative bg-slate-900/95 border border-cyan-500/50 rounded-lg overflow-hidden">
        {/* Animated border glow */}
        <div className="absolute inset-0 rounded-lg bg-gradient-to-r from-cyan-500/20 via-purple-500/20 to-cyan-500/20 animate-pulse" />

        {/* Scanline overlay */}
        <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.1)_50%)] bg-[length:100%_4px] z-10" />

        {/* Header */}
        <div className="relative p-4 border-b border-cyan-500/30 z-20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative">
                <Package className="w-6 h-6 text-cyan-400" />
                {card.status === "production_active" && (
                  <motion.div
                    className="absolute -top-1 -right-1 w-3 h-3 bg-cyan-400 rounded-full"
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ repeat: Infinity, duration: 1 }}
                  />
                )}
              </div>
              <div>
                <p className="text-xs text-slate-400 font-mono">
                  {card.order_number}
                </p>
                <h3 className="text-sm font-bold text-white">
                  {card.status_label}
                </h3>
              </div>
            </div>

            {/* Live indicator */}
            <div className="flex items-center gap-2 px-2 py-1 bg-slate-800 rounded">
              <motion.div
                className="w-2 h-2 bg-emerald-400 rounded-full"
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ repeat: Infinity, duration: 2 }}
              />
              <span className="text-xs text-slate-400 font-mono">LIVE</span>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="relative px-4 py-3 z-20">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs text-slate-400">Progress</span>
            <span className="text-xs font-mono text-cyan-400">
              {card.progress_percent}%
            </span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-cyan-500 to-purple-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${card.progress_percent}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
          {getTimeRemaining() && (
            <div className="flex items-center gap-1 mt-2">
              <Clock className="w-3 h-3 text-slate-500" />
              <span className="text-xs text-slate-500">{getTimeRemaining()}</span>
            </div>
          )}
        </div>

        {/* Phase Timeline */}
        <div className="relative px-4 py-3 z-20">
          <div className="space-y-3">
            {card.phases.map((phase, idx) => (
              <div key={phase.id} className="flex items-start gap-3 relative">
                {/* Icon */}
                <div
                  className={`
                    flex items-center justify-center w-8 h-8 rounded-full border-2
                    ${getStatusColor(phase.status)}
                    ${phase.status === "active" ? "bg-cyan-500/20" : "bg-transparent"}
                  `}
                >
                  {phase.status === "completed" ? (
                    <CheckCircle className="w-4 h-4" />
                  ) : phase.status === "failed" ? (
                    <AlertCircle className="w-4 h-4" />
                  ) : phase.status === "active" ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                    >
                      <Cog className="w-4 h-4" />
                    </motion.div>
                  ) : (
                    phaseIcons[phase.id] || <Zap className="w-4 h-4" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-sm font-medium ${
                        phase.status === "pending"
                          ? "text-slate-500"
                          : "text-white"
                      }`}
                    >
                      {phase.name}
                    </span>
                    {phase.completed_at && (
                      <span className="text-xs text-slate-500 font-mono">
                        {formatTime(phase.completed_at)}
                      </span>
                    )}
                  </div>
                  {phase.details && (
                    <p className="text-xs text-slate-400 mt-0.5">
                      {phase.details}
                    </p>
                  )}
                </div>

                {/* Connector line */}
                {idx < card.phases.length - 1 && (
                  <div
                    className={`absolute left-[0.9rem] top-8 w-0.5 h-6 ${
                      phase.status === "completed"
                        ? "bg-emerald-500/50"
                        : "bg-slate-700"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Delivery Section (when complete) */}
        <AnimatePresence>
          {card.status === "delivered" && card.video_url && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="relative z-20"
            >
              <div className="p-4 border-t border-emerald-500/30 bg-emerald-500/10">
                {/* Thumbnail */}
                {card.video_thumbnail && (
                  <div className="relative mb-3 rounded overflow-hidden">
                    <img
                      src={card.video_thumbnail}
                      alt="Video preview"
                      className="w-full h-32 object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                    <div className="absolute bottom-2 left-2 flex items-center gap-1 text-xs text-white">
                      <CheckCircle className="w-3 h-3 text-emerald-400" />
                      Ready for download
                    </div>
                  </div>
                )}

                {/* Download Button */}
                <button
                  onClick={onDownload}
                  disabled={!card.can_download}
                  className="w-full py-3 px-4 bg-gradient-to-r from-emerald-500 to-cyan-500 text-white font-medium rounded hover:from-emerald-400 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Download Your Commercial
                </button>

                {card.download_expires_at && (
                  <p className="text-xs text-slate-400 text-center mt-2">
                    Link expires{" "}
                    {new Date(card.download_expires_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Footer */}
        <div className="relative p-3 border-t border-cyan-500/20 bg-slate-800/50 z-20">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">
              Last updated: {formatTime(card.last_updated)}
            </span>
            <a
              href={card.support_url}
              className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
            >
              Need help?
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default OrderTrackingCard;
