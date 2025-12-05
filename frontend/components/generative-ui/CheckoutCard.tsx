// components/generative-ui/CheckoutCard.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v3.0 — CHECKOUT CARD
// ============================================================================
// Displays commercial brief summary and Stripe checkout button
// ============================================================================

"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  CreditCard,
  Check,
  Sparkles,
  User,
  Target,
  FileText,
  TrendingUp,
  ArrowRight,
  Loader2,
  ShieldCheck,
} from "lucide-react";

// =============================================================================
// TYPES
// =============================================================================

interface CheckoutCardProps {
  sessionId: string;
  personaName?: string;
  competitorName?: string;
  format?: string;
  tone?: string;
  investment?: number;
  projectedRoi?: number;
  onCheckout?: (sessionId: string, email: string) => Promise<string>;
  className?: string;
}

// =============================================================================
// CARD STATUS INDICATOR
// =============================================================================

interface CardStatusProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  complete: boolean;
}

const CardStatus: React.FC<CardStatusProps> = ({ icon, label, value, complete }) => (
  <motion.div
    initial={{ opacity: 0, x: -10 }}
    animate={{ opacity: 1, x: 0 }}
    className={cn(
      "flex items-center gap-3 p-3 rounded-lg",
      "bg-slate-800/50 border",
      complete ? "border-emerald-500/30" : "border-slate-700"
    )}
  >
    <div
      className={cn(
        "w-8 h-8 rounded-lg flex items-center justify-center",
        complete
          ? "bg-emerald-500/20 text-emerald-400"
          : "bg-slate-700 text-slate-400"
      )}
    >
      {icon}
    </div>
    <div className="flex-1 min-w-0">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm text-white truncate">{value}</p>
    </div>
    {complete && (
      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
    )}
  </motion.div>
);

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export const CheckoutCard: React.FC<CheckoutCardProps> = ({
  sessionId,
  personaName = "Your Target Customer",
  competitorName = "Competition",
  format = "60s",
  tone = "professional",
  investment = 5000,
  projectedRoi = 500,
  onCheckout,
  className,
}) => {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCheckout = async () => {
    if (!email.trim()) {
      setError("Please enter your email");
      return;
    }

    if (!email.includes("@")) {
      setError("Please enter a valid email");
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      if (onCheckout) {
        const checkoutUrl = await onCheckout(sessionId, email);
        window.location.href = checkoutUrl;
      } else {
        // Default API call
        const response = await fetch("/api/v3/checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            email: email.trim(),
          }),
        });

        if (!response.ok) {
          throw new Error("Checkout failed");
        }

        const data = await response.json();
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      setError("Failed to initiate checkout. Please try again.");
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "w-full max-w-md rounded-2xl overflow-hidden",
        "bg-gradient-to-b from-slate-900 to-slate-950",
        "border border-slate-700/50",
        "shadow-2xl shadow-purple-500/10",
        className
      )}
    >
      {/* Header */}
      <div className="relative px-6 py-5 bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border-b border-slate-700/50">
        {/* Animated background effect */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(139,92,246,0.15),transparent_50%)]" />
        
        <div className="relative flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">
              Your Commercial is Ready!
            </h2>
            <p className="text-sm text-slate-400">
              Review your brief and proceed to checkout
            </p>
          </div>
        </div>
      </div>

      {/* Brief Summary */}
      <div className="p-6 space-y-3">
        <CardStatus
          icon={<User className="w-4 h-4" />}
          label="Target Persona"
          value={personaName}
          complete={true}
        />
        <CardStatus
          icon={<Target className="w-4 h-4" />}
          label="Competitor Analysis"
          value={`vs ${competitorName}`}
          complete={true}
        />
        <CardStatus
          icon={<FileText className="w-4 h-4" />}
          label="Commercial Format"
          value={`${format} ${tone}`}
          complete={true}
        />
        <CardStatus
          icon={<TrendingUp className="w-4 h-4" />}
          label="Projected ROI"
          value={`${projectedRoi}%`}
          complete={true}
        />
      </div>

      {/* Investment Amount */}
      <div className="mx-6 p-4 rounded-xl bg-gradient-to-r from-purple-500/10 to-cyan-500/10 border border-purple-500/20">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Investment</span>
          <span className="text-2xl font-bold text-white">
            ${investment.toLocaleString()}
          </span>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          One-time payment · Includes video production & delivery
        </p>
      </div>

      {/* Email Input */}
      <div className="px-6 pt-4">
        <label className="block text-sm text-slate-400 mb-2">
          Email for delivery
        </label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className={cn(
            "w-full px-4 py-3 rounded-xl",
            "bg-slate-800 text-white placeholder-slate-500",
            "border focus:ring-2 transition-all",
            error
              ? "border-red-500/50 focus:ring-red-500/30"
              : "border-slate-700 focus:border-purple-500 focus:ring-purple-500/30"
          )}
        />
        {error && (
          <p className="mt-2 text-sm text-red-400">{error}</p>
        )}
      </div>

      {/* Checkout Button */}
      <div className="p-6">
        <motion.button
          onClick={handleCheckout}
          disabled={isLoading}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className={cn(
            "w-full py-4 rounded-xl font-semibold text-white",
            "bg-gradient-to-r from-purple-600 to-cyan-600",
            "hover:from-purple-500 hover:to-cyan-500",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "flex items-center justify-center gap-2",
            "shadow-lg shadow-purple-500/25",
            "transition-all duration-200"
          )}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <CreditCard className="w-5 h-5" />
              Proceed to Checkout
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </motion.button>

        {/* Trust badges */}
        <div className="mt-4 flex items-center justify-center gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-1">
            <ShieldCheck className="w-4 h-4" />
            <span>Secure Payment</span>
          </div>
          <div className="flex items-center gap-1">
            <Check className="w-4 h-4" />
            <span>100% Satisfaction</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default CheckoutCard;
