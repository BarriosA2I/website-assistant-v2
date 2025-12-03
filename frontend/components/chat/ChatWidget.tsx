// components/chat/ChatWidget.tsx
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — CHAT WIDGET
// ============================================================================
// Enhanced with Generative UI card rendering
// Displays rich interactive cards inline with chat messages
// ============================================================================

"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  MessageCircle,
  X,
  Send,
  Loader2,
  Bot,
  User,
  Sparkles,
  Minimize2,
  Maximize2,
} from "lucide-react";
import { DynamicCard } from "../generative-ui/DynamicCard";
import { RenderCard, AssistantMessage } from "@/lib/types/generative-ui";

// ============================================================================
// TYPES
// ============================================================================

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  render_card?: RenderCard | null;
  timestamp: Date;
  isLoading?: boolean;
  metadata?: {
    intent?: string;
    confidence?: number;
    latency_ms?: number;
    model_used?: string;
  };
}

interface ChatWidgetProps {
  apiEndpoint?: string;
  sessionId?: string;
  tenantId?: string;
  siteId?: string;
  userTier?: "starter" | "pro" | "elite";
  initialMessages?: ChatMessage[];
  className?: string;
  position?: "bottom-right" | "bottom-left";
  primaryColor?: string;
}

// ============================================================================
// MESSAGE BUBBLE COMPONENT
// ============================================================================

interface MessageBubbleProps {
  message: ChatMessage;
  onCardAction?: (action: string, data?: any) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  onCardAction,
}) => {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex gap-3",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          isUser
            ? "bg-gradient-to-br from-cyan-500 to-purple-600"
            : "bg-gradient-to-br from-slate-700 to-slate-800 border border-slate-600"
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-cyan-400" />
        )}
      </div>

      {/* Content */}
      <div className={cn("flex flex-col gap-2 max-w-[85%]", isUser && "items-end")}>
        {/* Text Message */}
        {message.content && (
          <div
            className={cn(
              "px-4 py-3 rounded-2xl text-sm leading-relaxed",
              isUser
                ? "bg-gradient-to-r from-cyan-500 to-purple-600 text-white rounded-br-md"
                : "bg-slate-800 text-slate-200 border border-slate-700 rounded-bl-md"
            )}
          >
            {message.isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-slate-400">Thinking...</span>
              </div>
            ) : (
              <p className="whitespace-pre-wrap">{message.content}</p>
            )}
          </div>
        )}

        {/* Generative UI Card */}
        {message.render_card && !message.isLoading && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="mt-2"
          >
            <DynamicCard
              card={message.render_card}
              onCompetitorDetails={() => onCardAction?.("competitor_details")}
              onPersonaExpand={() => onCardAction?.("persona_expand")}
              onScriptRegenerate={() => onCardAction?.("script_regenerate")}
              onScriptApprove={() => onCardAction?.("script_approve")}
              onScriptReject={() => onCardAction?.("script_reject")}
              onScriptEdit={(content) =>
                onCardAction?.("script_edit", { content })
              }
              onROICTA={() => onCardAction?.("roi_cta")}
            />
          </motion.div>
        )}

        {/* Metadata */}
        {message.metadata && !isUser && !message.isLoading && (
          <div className="flex items-center gap-3 text-[10px] text-slate-500 mt-1">
            {message.metadata.intent && (
              <span className="flex items-center gap-1">
                <Sparkles className="w-2.5 h-2.5" />
                {message.metadata.intent}
              </span>
            )}
            {message.metadata.latency_ms && (
              <span>{message.metadata.latency_ms.toFixed(0)}ms</span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const ChatWidget: React.FC<ChatWidgetProps> = ({
  apiEndpoint = "/api/chat",
  sessionId: initialSessionId,
  tenantId = "demo",
  siteId = "demo",
  userTier = "starter",
  initialMessages = [],
  className,
  position = "bottom-right",
  primaryColor = "#06b6d4",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(
    initialSessionId || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen && !isMinimized) {
      inputRef.current?.focus();
    }
  }, [isOpen, isMinimized]);

  // Send message handler
  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    const loadingMessage: ChatMessage = {
      id: `msg_${Date.now()}_loading`,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch(apiEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage.content,
          session_id: sessionId,
          tenant_id: tenantId,
          site_id: siteId,
          user_tier: userTier,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: AssistantMessage = await response.json();

      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now()}_assistant`,
        role: "assistant",
        content: data.content,
        render_card: data.render_card,
        timestamp: new Date(),
        metadata: {
          intent: data.intent,
          confidence: data.confidence,
          latency_ms: data.latency_ms,
          model_used: data.model_used,
        },
      };

      // Remove loading message and add real response
      setMessages((prev) => [
        ...prev.filter((m) => !m.isLoading),
        assistantMessage,
      ]);
    } catch (error) {
      console.error("Chat error:", error);

      const errorMessage: ChatMessage = {
        id: `msg_${Date.now()}_error`,
        role: "assistant",
        content:
          "I'm having trouble connecting right now. Please try again in a moment.",
        timestamp: new Date(),
      };

      setMessages((prev) => [
        ...prev.filter((m) => !m.isLoading),
        errorMessage,
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, apiEndpoint, sessionId, tenantId, siteId, userTier]);

  // Handle card actions
  const handleCardAction = useCallback(
    (action: string, data?: any) => {
      console.log("Card action:", action, data);

      // You can send these actions back to the server
      // or handle them client-side
      switch (action) {
        case "competitor_details":
          // Navigate to detailed competitor report
          break;
        case "script_regenerate":
          // Trigger script regeneration
          sendMessageToBackend("Please regenerate the script with different wording");
          break;
        case "script_approve":
          sendMessageToBackend("I approve this script");
          break;
        case "roi_cta":
          sendMessageToBackend("I'd like to get a custom quote");
          break;
        default:
          console.log("Unhandled action:", action);
      }
    },
    []
  );

  const sendMessageToBackend = (message: string) => {
    setInput(message);
    setTimeout(() => {
      sendMessage();
    }, 100);
  };

  // Handle key press
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Floating Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            onClick={() => setIsOpen(true)}
            className={cn(
              "fixed z-50 w-14 h-14 rounded-full shadow-2xl",
              "bg-gradient-to-r from-cyan-500 to-purple-600",
              "flex items-center justify-center",
              "hover:scale-105 transition-transform",
              position === "bottom-right" ? "bottom-6 right-6" : "bottom-6 left-6",
              className
            )}
          >
            <MessageCircle className="w-6 h-6 text-white" />
            {/* Pulse indicator */}
            <span className="absolute top-0 right-0 w-3 h-3 bg-emerald-400 rounded-full border-2 border-white" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat Window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{
              opacity: 1,
              scale: 1,
              y: 0,
              height: isMinimized ? "60px" : "600px",
            }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: "spring", damping: 25 }}
            className={cn(
              "fixed z-50 w-[420px] bg-slate-900 rounded-2xl",
              "border border-slate-700/50 shadow-2xl shadow-cyan-500/10",
              "flex flex-col overflow-hidden",
              position === "bottom-right" ? "bottom-6 right-6" : "bottom-6 left-6"
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-slate-800 to-slate-900 border-b border-slate-700/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">
                    Barrios A2I Assistant
                  </h3>
                  <p className="text-xs text-emerald-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                    Online
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => setIsMinimized(!isMinimized)}
                  className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                >
                  {isMinimized ? (
                    <Maximize2 className="w-4 h-4" />
                  ) : (
                    <Minimize2 className="w-4 h-4" />
                  )}
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Messages */}
            {!isMinimized && (
              <>
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.length === 0 && (
                    <div className="text-center py-8">
                      <Sparkles className="w-8 h-8 text-cyan-400 mx-auto mb-3" />
                      <p className="text-sm text-slate-400">
                        Hi! I'm your AI assistant. How can I help you today?
                      </p>
                      <div className="mt-4 flex flex-wrap gap-2 justify-center">
                        {[
                          "How do you beat Wistia?",
                          "What's your pricing?",
                          "Show me an ROI calculation",
                        ].map((suggestion) => (
                          <button
                            key={suggestion}
                            onClick={() => {
                              setInput(suggestion);
                              setTimeout(sendMessage, 100);
                            }}
                            className="px-3 py-1.5 text-xs bg-slate-800 text-slate-300 rounded-full hover:bg-slate-700 transition-colors border border-slate-700"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {messages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      onCardAction={handleCardAction}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="p-4 border-t border-slate-700/50 bg-slate-900/80 backdrop-blur">
                  <div className="flex items-end gap-2">
                    <textarea
                      ref={inputRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Type your message..."
                      rows={1}
                      className={cn(
                        "flex-1 resize-none px-4 py-3 rounded-xl",
                        "bg-slate-800 text-white placeholder-slate-500",
                        "border border-slate-700 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500",
                        "text-sm outline-none transition-colors",
                        "max-h-32"
                      )}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!input.trim() || isLoading}
                      className={cn(
                        "flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center",
                        "bg-gradient-to-r from-cyan-500 to-purple-600",
                        "text-white font-medium",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "hover:shadow-lg hover:shadow-cyan-500/30 transition-all"
                      )}
                    >
                      {isLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <Send className="w-5 h-5" />
                      )}
                    </button>
                  </div>
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default ChatWidget;
