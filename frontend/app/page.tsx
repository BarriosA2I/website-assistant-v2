// app/page.tsx
"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { 
  Sparkles, 
  Zap, 
  TrendingUp, 
  Shield, 
  Play,
  ArrowRight,
  CheckCircle
} from "lucide-react";
import ChatWidget from "@/components/chat/ChatWidget";

export default function HomePage() {
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);

  return (
    <main className="min-h-screen bg-slate-950">
      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        {/* Background Effects */}
        <div className="absolute inset-0">
          {/* Grid */}
          <div 
            className="absolute inset-0 opacity-20"
            style={{
              backgroundImage: `
                linear-gradient(rgba(6, 182, 212, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(6, 182, 212, 0.1) 1px, transparent 1px)
              `,
              backgroundSize: '50px 50px'
            }}
          />
          {/* Gradient Orbs */}
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/20 rounded-full blur-[100px]" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-[100px]" />
        </div>

        {/* Content */}
        <div className="relative z-10 max-w-6xl mx-auto px-6 py-20 text-center">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-sm font-medium mb-8"
          >
            <Sparkles className="w-4 h-4" />
            AI-Powered Video Generation
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-7xl font-bold mb-6"
          >
            <span className="text-white">Create </span>
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400">
              Stunning Commercials
            </span>
            <br />
            <span className="text-white">in </span>
            <span className="text-cyan-400">243 Seconds</span>
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-slate-400 max-w-2xl mx-auto mb-10"
          >
            Our 9-agent AI system generates professional video commercials at 
            <span className="text-emerald-400 font-semibold"> $2.60 each</span> with 
            <span className="text-emerald-400 font-semibold"> 97.5% success rate</span>.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-col sm:flex-row gap-4 justify-center mb-16"
          >
            <button className="group flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-purple-500 text-white font-semibold text-lg shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transition-all duration-300 hover:scale-105">
              <Play className="w-5 h-5" />
              Start Creating
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <button className="flex items-center justify-center gap-2 px-8 py-4 rounded-xl border border-slate-700 text-slate-300 font-semibold text-lg hover:bg-slate-800/50 transition-all duration-300">
              Watch Demo
            </button>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-4xl mx-auto"
          >
            {[
              { value: "230K+", label: "Videos Generated", icon: Zap },
              { value: "243s", label: "Avg. Generation Time", icon: TrendingUp },
              { value: "$2.60", label: "Per Commercial", icon: Shield },
              { value: "97.5%", label: "Success Rate", icon: CheckCircle },
            ].map((stat, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-900/50 border border-slate-800"
              >
                <stat.icon className="w-6 h-6 text-cyan-400 mx-auto mb-2" />
                <div className="text-2xl md:text-3xl font-bold text-white mb-1">
                  {stat.value}
                </div>
                <div className="text-sm text-slate-500">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            <span className="text-white">Why Choose </span>
            <span className="text-gradient-cyber">Barrios A2I</span>
          </h2>
          <p className="text-slate-400 text-center max-w-2xl mx-auto mb-12">
            Our multi-agent orchestration system outperforms traditional video 
            creation by 10x in speed and 5x in cost efficiency.
          </p>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                title: "9-Agent System",
                description: "Specialized AI agents for scripting, visuals, voiceover, music, and assembly working in parallel.",
                icon: Sparkles,
                gradient: "from-cyan-500 to-blue-500",
              },
              {
                title: "Data-Driven",
                description: "Trinity intelligence system provides competitive analysis and market insights in real-time.",
                icon: TrendingUp,
                gradient: "from-purple-500 to-pink-500",
              },
              {
                title: "Enterprise Ready",
                description: "99.95% uptime, SOC2 compliant, with full API access and white-label options.",
                icon: Shield,
                gradient: "from-emerald-500 to-cyan-500",
              },
            ].map((feature, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                viewport={{ once: true }}
                className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-colors"
              >
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center mb-4`}>
                  <feature.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-slate-400">
                  {feature.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Chat Widget */}
      <ChatWidget
        apiEndpoint="/api/chat"
        sessionId={sessionId}
        tenantId="barriosa2i"
        siteId="main"
        userTier="pro"
        position="bottom-right"
      />
    </main>
  );
}
