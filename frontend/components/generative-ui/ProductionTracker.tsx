// components/generative-ui/ProductionTracker.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v3.0 — PRODUCTION TRACKER
// ============================================================================
// Real-time video production progress with WebSocket updates
// ============================================================================

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  Play,
  Loader2,
  Check,
  Clock,
  Zap,
  Film,
  Mic,
  Wand2,
  Sparkles,
  Download,
  ExternalLink,
  AlertCircle,
} from "lucide-react";

// =============================================================================
// TYPES
// =============================================================================

interface ProductionPhase {
  id: string;
  name: string;
  icon: React.ReactNode;
  status: "pending" | "active" | "complete" | "error";
  duration?: number;
}

interface ProductionTrackerProps {
  sessionId: string;
  initialPhase?: string;
  initialProgress?: number;
  videoUrl?: string;
  deliveryToken?: string;
  onComplete?: (videoUrl: string) => void;
  className?: string;
}

// =============================================================================
// PRODUCTION PHASES
// =============================================================================

const PRODUCTION_PHASES: Omit<ProductionPhase, "status">[] = [
  { id: "business_intel", name: "Analyzing Brief", icon: <Zap className="w-4 h-4" /> },
  { id: "story_creation", name: "Crafting Story", icon: <Sparkles className="w-4 h-4" /> },
  { id: "video_prompt", name: "Designing Visuals", icon: <Wand2 className="w-4 h-4" /> },
  { id: "video_generation", name: "Generating Video", icon: <Film className="w-4 h-4" /> },
  { id: "voiceover", name: "Recording Voice", icon: <Mic className="w-4 h-4" /> },
  { id: "assembly", name: "Final Assembly", icon: <Play className="w-4 h-4" /> },
  { id: "quality_check", name: "Quality Check", icon: <Check className="w-4 h-4" /> },
];

// =============================================================================
// PHASE ITEM COMPONENT
// =============================================================================

interface PhaseItemProps {
  phase: ProductionPhase;
  index: number;
  isLast: boolean;
}

const PhaseItem: React.FC<PhaseItemProps> = ({ phase, index, isLast }) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="flex items-start gap-3"
    >
      {/* Icon & connector */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "w-10 h-10 rounded-xl flex items-center justify-center",
            "transition-all duration-300",
            phase.status === "complete" && "bg-emerald-500/20 text-emerald-400",
            phase.status === "active" && "bg-cyan-500/20 text-cyan-400",
            phase.status === "pending" && "bg-slate-800 text-slate-500",
            phase.status === "error" && "bg-red-500/20 text-red-400"
          )}
        >
          {phase.status === "active" ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : phase.status === "complete" ? (
            <Check className="w-4 h-4" />
          ) : phase.status === "error" ? (
            <AlertCircle className="w-4 h-4" />
          ) : (
            phase.icon
          )}
        </div>
        
        {/* Connector line */}
        {!isLast && (
          <div
            className={cn(
              "w-0.5 h-8 mt-1",
              phase.status === "complete" ? "bg-emerald-500/50" : "bg-slate-700"
            )}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pt-2">
        <p
          className={cn(
            "text-sm font-medium",
            phase.status === "complete" && "text-emerald-400",
            phase.status === "active" && "text-cyan-400",
            phase.status === "pending" && "text-slate-500",
            phase.status === "error" && "text-red-400"
          )}
        >
          {phase.name}
        </p>
        
        {phase.status === "active" && (
          <p className="text-xs text-slate-500 mt-0.5">
            In progress...
          </p>
        )}
        
        {phase.status === "complete" && phase.duration && (
          <p className="text-xs text-slate-500 mt-0.5">
            Completed in {phase.duration}s
          </p>
        )}
      </div>
    </motion.div>
  );
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export const ProductionTracker: React.FC<ProductionTrackerProps> = ({
  sessionId,
  initialPhase,
  initialProgress = 0,
  videoUrl: initialVideoUrl,
  deliveryToken,
  onComplete,
  className,
}) => {
  const [phases, setPhases] = useState<ProductionPhase[]>(() =>
    PRODUCTION_PHASES.map((p) => ({ ...p, status: "pending" as const }))
  );
  const [progress, setProgress] = useState(initialProgress);
  const [videoUrl, setVideoUrl] = useState(initialVideoUrl);
  const [isComplete, setIsComplete] = useState(!!initialVideoUrl);
  const [error, setError] = useState<string | null>(null);
  const [estimatedTime, setEstimatedTime] = useState("~4 min");
  const [elapsedTime, setElapsedTime] = useState(0);

  // WebSocket connection
  useEffect(() => {
    if (isComplete) return;

    const ws = new WebSocket(
      `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/progress/${sessionId}`
    );

    ws.onopen = () => {
      console.log("Production tracker connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case "progress":
            handleProgressUpdate(data);
            break;
          case "phase_complete":
            handlePhaseComplete(data.phase_id, data.duration);
            break;
          case "production_complete":
            handleProductionComplete(data.video_url);
            break;
          case "error":
            handleError(data.message);
            break;
          case "heartbeat":
            // Keep-alive, no action needed
            break;
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      console.log("Production tracker disconnected");
    };

    // Ping to keep connection alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 25000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [sessionId, isComplete]);

  // Elapsed time counter
  useEffect(() => {
    if (isComplete) return;

    const timer = setInterval(() => {
      setElapsedTime((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isComplete]);

  const handleProgressUpdate = useCallback((data: any) => {
    setProgress(data.percent || 0);
    
    if (data.current_phase) {
      setPhases((prev) =>
        prev.map((p) => {
          const phaseIndex = PRODUCTION_PHASES.findIndex((pp) => pp.id === p.id);
          const currentIndex = PRODUCTION_PHASES.findIndex((pp) => pp.id === data.current_phase);
          
          if (phaseIndex < currentIndex) {
            return { ...p, status: "complete" };
          } else if (phaseIndex === currentIndex) {
            return { ...p, status: "active" };
          }
          return { ...p, status: "pending" };
        })
      );
    }
    
    if (data.estimated_remaining) {
      setEstimatedTime(data.estimated_remaining);
    }
  }, []);

  const handlePhaseComplete = useCallback((phaseId: string, duration: number) => {
    setPhases((prev) =>
      prev.map((p) =>
        p.id === phaseId ? { ...p, status: "complete", duration } : p
      )
    );
  }, []);

  const handleProductionComplete = useCallback((url: string) => {
    setVideoUrl(url);
    setIsComplete(true);
    setProgress(100);
    setPhases((prev) => prev.map((p) => ({ ...p, status: "complete" })));
    onComplete?.(url);
  }, [onComplete]);

  const handleError = useCallback((message: string) => {
    setError(message);
    setPhases((prev) => {
      const activeIndex = prev.findIndex((p) => p.status === "active");
      return prev.map((p, i) =>
        i === activeIndex ? { ...p, status: "error" } : p
      );
    });
  }, []);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "w-full max-w-md rounded-2xl overflow-hidden",
        "bg-gradient-to-b from-slate-900 to-slate-950",
        "border border-slate-700/50",
        "shadow-2xl",
        isComplete ? "shadow-emerald-500/10" : "shadow-cyan-500/10",
        className
      )}
    >
      {/* Header */}
      <div
        className={cn(
          "relative px-6 py-5 border-b border-slate-700/50",
          isComplete
            ? "bg-gradient-to-r from-emerald-600/20 to-cyan-600/20"
            : "bg-gradient-to-r from-cyan-600/20 to-purple-600/20"
        )}
      >
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center",
              isComplete
                ? "bg-gradient-to-br from-emerald-500 to-cyan-500"
                : "bg-gradient-to-br from-cyan-500 to-purple-500"
            )}
          >
            {isComplete ? (
              <Check className="w-6 h-6 text-white" />
            ) : (
              <Film className="w-6 h-6 text-white" />
            )}
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">
              {isComplete ? "Your Video is Ready!" : "Creating Your Commercial"}
            </h2>
            <p className="text-sm text-slate-400">
              {isComplete
                ? "Download your commercial below"
                : `Estimated: ${estimatedTime}`}
            </p>
          </div>
        </div>

        {/* Progress bar */}
        {!isComplete && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span>{progress}% complete</span>
              <span>Elapsed: {formatTime(elapsedTime)}</span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-500 to-purple-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Phases */}
      <div className="p-6 space-y-0">
        {phases.map((phase, index) => (
          <PhaseItem
            key={phase.id}
            phase={phase}
            index={index}
            isLast={index === phases.length - 1}
          />
        ))}
      </div>

      {/* Error state */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mx-6 mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30"
          >
            <div className="flex items-center gap-2 text-red-400">
              <AlertCircle className="w-5 h-5" />
              <p className="text-sm">{error}</p>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="mt-3 text-sm text-red-400 hover:text-red-300 underline"
            >
              Retry
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Download section */}
      <AnimatePresence>
        {isComplete && videoUrl && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-6 pt-0 space-y-3"
          >
            {/* Video preview */}
            <div className="aspect-video bg-slate-800 rounded-xl overflow-hidden border border-slate-700">
              <video
                src={videoUrl}
                controls
                poster="/video-poster.jpg"
                className="w-full h-full object-cover"
              />
            </div>

            {/* Download buttons */}
            <div className="flex gap-3">
              <a
                href={deliveryToken ? `/api/v3/download/${deliveryToken}` : videoUrl}
                download
                className={cn(
                  "flex-1 py-3 rounded-xl font-semibold text-white",
                  "bg-gradient-to-r from-emerald-600 to-cyan-600",
                  "hover:from-emerald-500 hover:to-cyan-500",
                  "flex items-center justify-center gap-2",
                  "transition-all duration-200"
                )}
              >
                <Download className="w-5 h-5" />
                Download Video
              </a>
              
              <button
                onClick={() => window.open(videoUrl, "_blank")}
                className={cn(
                  "px-4 py-3 rounded-xl",
                  "bg-slate-800 text-slate-300",
                  "hover:bg-slate-700 hover:text-white",
                  "border border-slate-700",
                  "transition-all duration-200"
                )}
              >
                <ExternalLink className="w-5 h-5" />
              </button>
            </div>

            {/* Celebration message */}
            <div className="text-center py-4">
              <p className="text-sm text-slate-400">
                🎉 Thank you for choosing Barrios A2I!
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Need revisions? Reply to your delivery email.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading animation when not complete */}
      {!isComplete && (
        <div className="px-6 pb-6">
          <div className="flex items-center justify-center gap-2 text-sm text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>AI is working on your video...</span>
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default ProductionTracker;
