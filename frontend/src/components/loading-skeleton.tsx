"use client";

import clsx from "clsx";

// =============================================================================
// Base Skeleton Component
// =============================================================================

interface SkeletonProps {
  className?: string;
  variant?: "text" | "circular" | "rectangular";
  width?: string | number;
  height?: string | number;
}

export function Skeleton({ 
  className, 
  variant = "text",
  width,
  height,
}: SkeletonProps) {
  const baseStyles = "skeleton rounded";
  
  const variantStyles = {
    text: "h-4 rounded",
    circular: "rounded-full",
    rectangular: "rounded-lg",
  };

  return (
    <div
      className={clsx(baseStyles, variantStyles[variant], className)}
      style={{
        width: typeof width === "number" ? `${width}px` : width,
        height: typeof height === "number" ? `${height}px` : height,
      }}
    />
  );
}

// =============================================================================
// Message Skeleton (for chat loading)
// =============================================================================

interface MessageSkeletonProps {
  isUser?: boolean;
  lines?: number;
}

export function MessageSkeleton({ isUser = false, lines = 3 }: MessageSkeletonProps) {
  return (
    <div
      className={clsx(
        "flex gap-3 animate-fade-in",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <Skeleton
        variant="rectangular"
        className="flex-shrink-0 w-9 h-9 rounded-xl"
      />

      {/* Message content */}
      <div className={clsx("flex-1 max-w-[80%]", isUser ? "items-end" : "items-start")}>
        <div
          className={clsx(
            "px-4 py-3 rounded-2xl space-y-2",
            isUser ? "rounded-tr-sm" : "rounded-tl-sm",
            "dark:bg-surface-800/50 bg-slate-100"
          )}
        >
          {/* Simulate multiple lines of text */}
          {Array.from({ length: lines }).map((_, i) => (
            <Skeleton
              key={i}
              variant="text"
              className={clsx(
                "h-3",
                i === lines - 1 ? "w-2/3" : "w-full" // Last line shorter
              )}
            />
          ))}
        </div>

        {/* Timestamp skeleton */}
        <Skeleton variant="text" className="h-2 w-12 mt-2" />
      </div>
    </div>
  );
}

// =============================================================================
// Chat Loading Skeleton (multiple messages)
// =============================================================================

export function ChatLoadingSkeleton() {
  return (
    <div className="space-y-6 p-4">
      {/* User message */}
      <MessageSkeleton isUser lines={1} />
      
      {/* Assistant message (longer) */}
      <MessageSkeleton isUser={false} lines={4} />
      
      {/* Another user message */}
      <MessageSkeleton isUser lines={2} />
      
      {/* Assistant response */}
      <MessageSkeleton isUser={false} lines={3} />
    </div>
  );
}

// =============================================================================
// Agent Card Skeleton
// =============================================================================

export function AgentCardSkeleton() {
  return (
    <div className="card p-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        {/* Avatar */}
        <Skeleton variant="rectangular" className="w-16 h-16 rounded-2xl" />

        {/* Info */}
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" className="h-5 w-3/4" />
          <Skeleton variant="text" className="h-3 w-1/2" />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="dark:bg-surface-800/50 bg-slate-100 rounded-lg p-3">
            <Skeleton variant="text" className="h-3 w-12 mb-2" />
            <Skeleton variant="text" className="h-5 w-8" />
          </div>
        ))}
      </div>

      {/* Categories */}
      <div className="pt-4 border-t dark:border-surface-800 border-slate-200">
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rectangular" className="h-6 w-20 rounded" />
          ))}
        </div>
      </div>

      {/* Button */}
      <Skeleton variant="rectangular" className="h-10 w-full mt-4 rounded-lg" />
    </div>
  );
}

// =============================================================================
// Initial Loading Screen
// =============================================================================

export function InitialLoadingSkeleton() {
  return (
    <div className="flex items-center justify-center min-h-[200px]">
      <div className="flex flex-col items-center gap-4">
        {/* Animated logo placeholder */}
        <div className="relative">
          <Skeleton variant="rectangular" className="w-16 h-16 rounded-2xl" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
        
        {/* Text */}
        <div className="space-y-2 text-center">
          <Skeleton variant="text" className="h-4 w-32 mx-auto" />
          <Skeleton variant="text" className="h-3 w-24 mx-auto" />
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Thinking Indicator (animated dots with text)
// =============================================================================

interface ThinkingIndicatorProps {
  agentColor?: string;
  text?: string;
}

export function ThinkingIndicator({ 
  agentColor = "#f97316",
  text = "Thinking"
}: ThinkingIndicatorProps) {
  return (
    <div className="flex gap-3 animate-fade-in">
      {/* Avatar */}
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center border dark:border-surface-700 border-slate-200"
        style={{ background: `${agentColor}15`, color: agentColor }}
      >
        <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      </div>

      {/* Message bubble */}
      <div className="dark:bg-surface-800/80 bg-white border dark:border-surface-700 border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <div className="flex items-center gap-2">
          <span className="text-sm dark:text-surface-400 text-slate-500">{text}</span>
          <div className="flex gap-1">
            <span
              className="w-1.5 h-1.5 rounded-full animate-bounce [animation-delay:0ms]"
              style={{ background: agentColor }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full animate-bounce [animation-delay:150ms]"
              style={{ background: agentColor }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full animate-bounce [animation-delay:300ms]"
              style={{ background: agentColor }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

