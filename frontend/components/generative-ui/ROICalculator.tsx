// components/generative-ui/ROICalculator.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — ROI CALCULATOR CARD
// ============================================================================
// Visual: Interactive sliders with glowing green projected savings
// Style: Cyberpunk/HUD aesthetic with animated number counters
// ============================================================================

"use client";

import React, { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ROICalculatorCard,
  ROISlider,
  ROIProjection,
} from "@/lib/types/generative-ui";
import { cn } from "@/lib/utils";
import {
  Calculator,
  TrendingUp,
  DollarSign,
  Clock,
  Info,
  ChevronRight,
  Sparkles,
  ArrowUpRight,
} from "lucide-react";

interface ROICalculatorProps {
  data: ROICalculatorCard;
  className?: string;
  onCTAClick?: () => void;
}

// ============================================================================
// ANIMATED COUNTER
// ============================================================================

const AnimatedCounter: React.FC<{
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  className?: string;
}> = ({ value, prefix = "", suffix = "", decimals = 0, className }) => {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const duration = 1000;
    const startTime = Date.now();
    const startValue = displayValue;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // Ease out cubic
      const current = startValue + (value - startValue) * eased;

      setDisplayValue(current);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [value]);

  return (
    <span className={className}>
      {prefix}
      {displayValue.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
};

// ============================================================================
// SLIDER COMPONENT
// ============================================================================

interface SliderInputProps {
  slider: ROISlider;
  value: number;
  onChange: (value: number) => void;
}

const SliderInput: React.FC<SliderInputProps> = ({
  slider,
  value,
  onChange,
}) => {
  const percentage =
    ((value - slider.min_value) / (slider.max_value - slider.min_value)) * 100;

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-slate-300 flex items-center gap-2">
          {slider.label}
          {slider.tooltip && (
            <div className="relative">
              <Info className="w-3.5 h-3.5 text-slate-500 cursor-help" />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-800 text-xs text-slate-300 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10 border border-slate-700">
                {slider.tooltip}
              </div>
            </div>
          )}
        </label>
        <span className="text-sm font-bold text-cyan-400">
          {slider.unit === "$" && slider.unit}
          {value.toLocaleString()}
          {slider.unit !== "$" && slider.unit}
        </span>
      </div>

      {/* Custom Slider */}
      <div className="relative h-3">
        {/* Track */}
        <div className="absolute inset-0 bg-slate-700 rounded-full overflow-hidden">
          {/* Filled portion */}
          <motion.div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-500 to-emerald-400 rounded-full"
            style={{ width: `${percentage}%` }}
            initial={false}
            animate={{ width: `${percentage}%` }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          />
          {/* Glow effect */}
          <motion.div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-400 to-emerald-300 rounded-full blur-sm opacity-50"
            style={{ width: `${percentage}%` }}
          />
        </div>

        {/* Thumb */}
        <motion.div
          className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white rounded-full shadow-lg shadow-cyan-500/30 border-2 border-cyan-400 cursor-grab active:cursor-grabbing"
          style={{ left: `calc(${percentage}% - 10px)` }}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
        />

        {/* Invisible range input */}
        <input
          type="range"
          min={slider.min_value}
          max={slider.max_value}
          step={slider.step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute inset-0 opacity-0 cursor-pointer"
        />
      </div>

      {/* Range Labels */}
      <div className="flex justify-between mt-1 text-[10px] text-slate-500">
        <span>
          {slider.unit === "$" && slider.unit}
          {slider.min_value.toLocaleString()}
        </span>
        <span>
          {slider.unit === "$" && slider.unit}
          {slider.max_value.toLocaleString()}
        </span>
      </div>
    </div>
  );
};

// ============================================================================
// PROJECTION CARD
// ============================================================================

interface ProjectionCardProps {
  projection: ROIProjection;
  index: number;
}

const ProjectionCard: React.FC<ProjectionCardProps> = ({
  projection,
  index,
}) => {
  const isPositive = projection.improvement_percent > 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.1 + 0.3 }}
      className={cn(
        "p-4 rounded-xl border transition-all",
        "bg-slate-800/50 hover:bg-slate-800/70",
        isPositive ? "border-emerald-400/30" : "border-red-400/30"
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-medium text-slate-400">
          {projection.metric_name}
        </span>
        <span
          className={cn(
            "flex items-center gap-0.5 text-xs font-bold",
            isPositive ? "text-emerald-400" : "text-red-400"
          )}
        >
          {isPositive ? "+" : ""}
          {projection.improvement_percent.toFixed(1)}%
          <ArrowUpRight
            className={cn(
              "w-3 h-3",
              !isPositive && "rotate-90"
            )}
          />
        </span>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-slate-500 text-xs line-through">
          ${projection.current_value.toLocaleString()}
        </span>
        <span className="text-lg font-bold text-white">
          <AnimatedCounter
            value={projection.projected_value}
            prefix="$"
            decimals={0}
          />
        </span>
      </div>

      <span className="text-[10px] text-slate-500 mt-1 block">
        {projection.timeframe}
      </span>
    </motion.div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const ROICalculator: React.FC<ROICalculatorProps> = ({
  data,
  className,
  onCTAClick,
}) => {
  // Initialize slider values with defaults
  const [sliderValues, setSliderValues] = useState<Record<string, number>>(
    () =>
      data.sliders.reduce(
        (acc, slider) => ({
          ...acc,
          [slider.id]: slider.default_value,
        }),
        {}
      )
  );

  // Calculate total savings based on slider values (simplified)
  const calculatedSavings = useMemo(() => {
    // In production, this would use the actual formula
    // For now, we scale based on slider positions
    const baseMultiplier = Object.entries(sliderValues).reduce(
      (acc, [id, value]) => {
        const slider = data.sliders.find((s) => s.id === id);
        if (!slider) return acc;
        const normalized =
          (value - slider.min_value) / (slider.max_value - slider.min_value);
        return acc * (0.5 + normalized);
      },
      1
    );
    return data.total_savings * baseMultiplier;
  }, [sliderValues, data.sliders, data.total_savings]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "relative overflow-hidden rounded-2xl",
        "bg-gradient-to-b from-slate-900 via-slate-900 to-emerald-950/30",
        "border border-slate-700/50",
        "shadow-2xl shadow-emerald-500/10",
        className
      )}
    >
      {/* Ambient glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-1/2 bg-emerald-500/10 blur-3xl rounded-full" />
      </div>

      {/* Header */}
      <div className="relative px-6 py-5 border-b border-slate-700/50">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/30">
            <Calculator className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">{data.title}</h2>
            {data.subtitle && (
              <p className="text-sm text-slate-400 mt-0.5">{data.subtitle}</p>
            )}
          </div>
        </div>
      </div>

      {/* Sliders Section */}
      <div className="relative px-6 py-6 border-b border-slate-700/30 space-y-6">
        {data.sliders.map((slider) => (
          <SliderInput
            key={slider.id}
            slider={slider}
            value={sliderValues[slider.id]}
            onChange={(value) =>
              setSliderValues((prev) => ({ ...prev, [slider.id]: value }))
            }
          />
        ))}
      </div>

      {/* Total Savings - HERO */}
      <div className="relative px-6 py-8">
        <div className="text-center">
          <span className="text-sm font-medium text-slate-400 uppercase tracking-wider">
            Projected Annual Savings
          </span>

          {/* Glowing number */}
          <div className="relative mt-3 mb-2">
            <motion.div
              className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-cyan-400 to-emerald-400"
              animate={{
                backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"],
              }}
              transition={{
                duration: 5,
                repeat: Infinity,
                ease: "linear",
              }}
              style={{
                backgroundSize: "200% 100%",
              }}
            >
              <AnimatedCounter
                value={calculatedSavings}
                prefix="$"
                decimals={0}
              />
            </motion.div>

            {/* Glow effect */}
            <div className="absolute inset-0 text-5xl font-black text-emerald-400 blur-2xl opacity-30 pointer-events-none">
              ${calculatedSavings.toLocaleString()}
            </div>
          </div>

          {/* Payback period */}
          {data.payback_period_months && (
            <div className="flex items-center justify-center gap-2 text-sm text-slate-400">
              <Clock className="w-4 h-4" />
              Payback in {data.payback_period_months.toFixed(1)} months
            </div>
          )}
        </div>
      </div>

      {/* Projections Grid */}
      <div className="px-6 pb-6">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-semibold text-slate-300">
            Detailed Projections
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {data.projections.slice(0, 4).map((projection, index) => (
            <ProjectionCard
              key={projection.metric_name}
              projection={projection}
              index={index}
            />
          ))}
        </div>
      </div>

      {/* Formula Description */}
      {data.formula_description && (
        <div className="px-6 pb-4">
          <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
            <p className="text-xs text-slate-500 leading-relaxed">
              <Info className="w-3 h-3 inline mr-1" />
              {data.formula_description}
            </p>
          </div>
        </div>
      )}

      {/* CTA */}
      <div className="px-6 py-5 border-t border-slate-700/50 bg-slate-900/50">
        <motion.button
          onClick={onCTAClick}
          className={cn(
            "w-full flex items-center justify-center gap-2",
            "px-6 py-4 rounded-xl",
            "bg-gradient-to-r from-emerald-500 to-cyan-500",
            "text-white font-bold text-sm",
            "shadow-lg shadow-emerald-500/30",
            "hover:from-emerald-400 hover:to-cyan-400",
            "transition-all"
          )}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <Sparkles className="w-4 h-4" />
          {data.cta_text}
          <ChevronRight className="w-4 h-4" />
        </motion.button>
      </div>
    </motion.div>
  );
};

export default ROICalculator;
