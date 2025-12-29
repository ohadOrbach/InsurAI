"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast, Toaster } from "sonner";
import {
  Send,
  Bot,
  User,
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  Sparkles,
  Loader2,
  ArrowLeft,
  Pencil,
  Check,
  X,
  MessageSquare,
  Copy,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  FileText,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import clsx from "clsx";
import { ThemeToggle } from "@/components/theme-toggle";
import { ThinkingIndicator, InitialLoadingSkeleton } from "@/components/loading-skeleton";
import { useTheme } from "@/lib/theme-context";

// =============================================================================
// Types
// =============================================================================

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  reasoning?: {
    pipeline?: string;
    reasoning_trace?: string[];
    coverage_checks?: Array<{
      item?: string;
      status?: string;
      confidence?: number;
    }>;
    citations?: string[];
  };
  feedback?: "positive" | "negative" | null;
}

interface Agent {
  id: number;
  name: string;
  description: string | null;
  agent_type: string;
  status: string;
  policy_id: string;
  policy_type: string | null;
  provider_name: string | null;
  color: string;
  coverage_summary: {
    total_categories?: number;
    total_inclusions?: number;
    categories?: string[];
  };
}

// =============================================================================
// API Client
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

async function fetchAgent(id: string): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents/${id}`);
  if (!res.ok) throw new Error("Agent not found");
  return res.json();
}

async function updateAgentName(id: string, name: string): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("Failed to update agent");
  return res.json();
}

async function createSession(agentId: string): Promise<{ session_id: string }> {
  const res = await fetch(`${API_BASE}/chat/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: parseInt(agentId) }),
  });
  if (!res.ok) throw new Error("Failed to create session");
  return res.json();
}

async function sendMessageNonStream(
  sessionId: string,
  message: string
): Promise<{
  message: {
    id: string;
    role: string;
    content: string;
    timestamp: string;
    metadata: Record<string, unknown>;
  };
  reasoning?: {
    pipeline: string;
    reasoning_trace: string[];
    coverage_checks: Array<{ item?: string; status?: string; confidence?: number }>;
    citations: string[];
  };
}> {
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, stream: false }),
  });

  if (!res.ok) throw new Error("Failed to send message");
  return res.json();
}

// =============================================================================
// Components
// =============================================================================

function CoverageStatusBadge({ content }: { content: string }) {
  const upperContent = content.toUpperCase();

  if (
    upperContent.includes("NOT COVERED") ||
    upperContent.includes("NOT_COVERED") ||
    upperContent.includes("EXCLUDED") ||
    upperContent.includes("❌")
  ) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-500 border border-rose-500/30">
        <ShieldAlert size={12} />
        Not Covered
      </span>
    );
  }

  if (
    upperContent.includes("CONDITIONAL") ||
    upperContent.includes("CONDITIONS APPLY") ||
    upperContent.includes("⚠")
  ) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-500 border border-amber-500/30">
        <Shield size={12} />
        Conditional
      </span>
    );
  }

  if (upperContent.includes("COVERED") || upperContent.includes("✅")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
        <ShieldCheck size={12} />
        Covered
      </span>
    );
  }

  if (upperContent.includes("UNKNOWN") || upperContent.includes("❓")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-500 border border-slate-500/30">
        <ShieldQuestion size={12} />
        Unknown
      </span>
    );
  }

  return null;
}

function CitationsPanel({ citations }: { citations: string[] }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { theme } = useTheme();

  if (!citations || citations.length === 0) return null;

  return (
    <div className={clsx(
      "mt-3 pt-3 border-t",
      theme === "dark" ? "border-surface-700/50" : "border-slate-200"
    )}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={clsx(
          "flex items-center gap-2 text-xs transition-colors",
          theme === "dark" 
            ? "text-surface-400 hover:text-surface-300" 
            : "text-slate-500 hover:text-slate-700"
        )}
      >
        <FileText size={12} />
        <span>{citations.length} source{citations.length > 1 ? "s" : ""} cited</span>
        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {isExpanded && (
        <div className="mt-2 space-y-1.5 animate-fade-in">
          {citations.map((citation, i) => (
            <div
              key={i}
              className={clsx(
                "text-xs px-3 py-2 rounded-lg border-l-2 border-brand-500/50",
                theme === "dark" 
                  ? "bg-surface-800/80 text-surface-300" 
                  : "bg-slate-50 text-slate-600"
              )}
            >
              {citation}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageFeedback({
  feedback,
  onFeedback,
}: {
  feedback: "positive" | "negative" | null;
  onFeedback: (type: "positive" | "negative") => void;
}) {
  const { theme } = useTheme();
  
  return (
    <div className="flex items-center gap-1 mt-2">
      <button
        onClick={() => onFeedback("positive")}
        className={clsx(
          "p-1.5 rounded transition-all",
          feedback === "positive"
            ? "bg-emerald-500/20 text-emerald-500"
            : theme === "dark"
              ? "hover:bg-surface-700 text-surface-500 hover:text-surface-300"
              : "hover:bg-slate-100 text-slate-400 hover:text-slate-600"
        )}
        title="Helpful response"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        onClick={() => onFeedback("negative")}
        className={clsx(
          "p-1.5 rounded transition-all",
          feedback === "negative"
            ? "bg-rose-500/20 text-rose-500"
            : theme === "dark"
              ? "hover:bg-surface-700 text-surface-500 hover:text-surface-300"
              : "hover:bg-slate-100 text-slate-400 hover:text-slate-600"
        )}
        title="Not helpful"
      >
        <ThumbsDown size={14} />
      </button>
    </div>
  );
}

function MessageBubble({
  message,
  agentColor,
  onCopy,
  onFeedback,
}: {
  message: Message;
  agentColor: string;
  onCopy: () => void;
  onFeedback: (type: "positive" | "negative") => void;
}) {
  const isUser = message.role === "user";
  const [showActions, setShowActions] = useState(false);
  const { theme } = useTheme();

  return (
    <div
      className={clsx(
        "flex gap-3 animate-slide-up group",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div
        className={clsx(
          "flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center",
          isUser 
            ? "bg-brand-500/20 text-brand-500" 
            : theme === "dark" 
              ? "border border-surface-700" 
              : "border border-slate-200"
        )}
        style={!isUser ? { background: `${agentColor}15`, color: agentColor } : {}}
      >
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      <div className={clsx("flex-1 max-w-[80%]", isUser ? "text-right" : "text-left")}>
        <div
          className={clsx(
            "inline-block px-4 py-3 rounded-2xl relative",
            isUser
              ? "message-bubble-user"
              : "message-bubble-assistant"
          )}
        >
          {/* Coverage Badge */}
          {!isUser && message.content && (
            <div className="mb-2">
              <CoverageStatusBadge content={message.content} />
            </div>
          )}

          {/* Message Content with Markdown */}
          <div className="text-sm leading-relaxed">
            {isUser ? (
              <span className="whitespace-pre-wrap">{message.content}</span>
            ) : (
              <div className={clsx(
                "prose prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-0.5 prose-headings:my-2",
                theme === "dark" ? "prose-invert" : ""
              )}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
            {message.isStreaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-brand-500 animate-pulse rounded-sm" />
            )}
          </div>

          {/* Copy Button (for assistant messages) */}
          {!isUser && !message.isStreaming && showActions && (
            <button
              onClick={onCopy}
              className={clsx(
                "absolute top-2 right-2 p-1.5 rounded-lg transition-all opacity-0 group-hover:opacity-100",
                theme === "dark" 
                  ? "bg-surface-700/80 hover:bg-surface-600" 
                  : "bg-slate-100 hover:bg-slate-200"
              )}
              title="Copy to clipboard"
            >
              <Copy size={12} className={theme === "dark" ? "text-surface-300" : "text-slate-500"} />
            </button>
          )}

          {/* Citations */}
          {!isUser && message.reasoning?.citations && (
            <CitationsPanel citations={message.reasoning.citations} />
          )}
        </div>

        {/* Footer: Timestamp + Feedback */}
        <div className="flex items-center gap-2 mt-1.5 px-1">
          <p className={clsx(
            "text-xs",
            theme === "dark" ? "text-surface-500" : "text-slate-400"
          )}>
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>

          {/* Feedback buttons (only for assistant, non-streaming) */}
          {!isUser && !message.isStreaming && (
            <MessageFeedback feedback={message.feedback || null} onFeedback={onFeedback} />
          )}
        </div>
      </div>
    </div>
  );
}

function WelcomeMessage({
  agent,
  onSuggestionClick,
}: {
  agent: Agent;
  onSuggestionClick: (question: string) => void;
}) {
  const { theme } = useTheme();
  
  const suggestions = [
    "What is covered under my policy?",
    "What are the exclusions?",
    "What's my deductible?",
    "Is intentional damage covered?",
    "Is flood damage covered?",
  ];

  return (
    <div className="flex gap-3 animate-fade-in">
      <div
        className={clsx(
          "flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center border",
          theme === "dark" ? "border-surface-700" : "border-slate-200"
        )}
        style={{ background: `${agent.color}15`, color: agent.color }}
      >
        <Bot size={18} />
      </div>
      <div className="flex-1">
        <div className="message-bubble-assistant inline-block px-4 py-3">
          <p className="text-sm leading-relaxed">
            👋 Hi! I'm <strong>{agent.name}</strong>, your insurance assistant
            {agent.policy_type && (
              <>
                {" "}
                for <strong>{agent.policy_type}</strong>
              </>
            )}
            .
          </p>
          <p className={clsx(
            "text-sm leading-relaxed mt-2",
            theme === "dark" ? "text-surface-400" : "text-slate-500"
          )}>
            I can help you understand your coverage, exclusions, deductibles, and more.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {suggestions.map((q, i) => (
            <button
              key={i}
              onClick={() => onSuggestionClick(q)}
              className={clsx(
                "px-3 py-1.5 border rounded-lg text-xs transition-all cursor-pointer group",
                theme === "dark"
                  ? "bg-surface-800 hover:bg-surface-700 border-surface-700 hover:border-brand-500/50 text-surface-300 hover:text-white"
                  : "bg-white hover:bg-slate-50 border-slate-200 hover:border-brand-500/50 text-slate-600 hover:text-slate-900 shadow-sm"
              )}
            >
              <Sparkles
                size={12}
                className="inline mr-1.5 text-brand-500 group-hover:text-brand-400"
              />
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Chat Page
// =============================================================================

export default function AgentChatPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;
  const { theme } = useTheme();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  // Name editing
  const [isEditingName, setIsEditingName] = useState(false);
  const [editName, setEditName] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load agent and create session
  useEffect(() => {
    const init = async () => {
      setIsInitializing(true);
      try {
        const agentData = await fetchAgent(agentId);
        setAgent(agentData);
        setEditName(agentData.name);

        const session = await createSession(agentId);
        setSessionId(session.session_id);
      } catch (err) {
        console.error("Failed to initialize:", err);
        toast.error("Failed to load agent. It may not exist.");
      } finally {
        setIsInitializing(false);
      }
    };
    init();
  }, [agentId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "n") {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Handle name save
  const handleSaveName = async () => {
    if (!agent || !editName.trim() || editName === agent.name) {
      setIsEditingName(false);
      return;
    }

    try {
      await updateAgentName(agentId, editName.trim());
      setAgent({ ...agent, name: editName.trim() });
      setIsEditingName(false);
      toast.success("Agent name updated");
    } catch (err) {
      console.error("Failed to update name:", err);
      toast.error("Failed to update agent name");
    }
  };

  // Handle new chat
  const handleNewChat = async () => {
    try {
      const session = await createSession(agentId);
      setSessionId(session.session_id);
      setMessages([]);
      toast.success("Started new conversation");
    } catch (err) {
      console.error("Failed to create new session:", err);
      toast.error("Failed to start new conversation");
    }
  };

  // Handle copy to clipboard
  const handleCopy = useCallback((content: string) => {
    navigator.clipboard.writeText(content);
    toast.success("Copied to clipboard");
  }, []);

  // Handle message feedback
  const handleFeedback = useCallback(
    (messageId: string, type: "positive" | "negative") => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? { ...msg, feedback: msg.feedback === type ? null : type }
            : msg
        )
      );

      const feedbackText = type === "positive" ? "Thanks for the feedback!" : "We'll work on improving";
      toast.success(feedbackText);
    },
    []
  );

  // Handle sending a message
  const handleSend = async () => {
    if (!input.trim() || !sessionId || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const userInput = input.trim();
    setInput("");
    setIsLoading(true);

    try {
      const response = await sendMessageNonStream(sessionId, userInput);

      const assistantMessage: Message = {
        id: response.message.id || (Date.now() + 1).toString(),
        role: "assistant",
        content: response.message.content,
        timestamp: response.message.timestamp || new Date().toISOString(),
        reasoning: response.reasoning,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error("Failed to send message:", err);
      toast.error("Failed to send message. Please try again.");
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Handle clicking a suggestion question
  const handleSuggestionClick = async (question: string) => {
    if (!sessionId || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: question,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await sendMessageNonStream(sessionId, question);

      const assistantMessage: Message = {
        id: response.message.id || (Date.now() + 1).toString(),
        role: "assistant",
        content: response.message.content,
        timestamp: response.message.timestamp || new Date().toISOString(),
        reasoning: response.reasoning,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error("Failed to send message:", err);
      toast.error("Failed to send message. Please try again.");
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  // Initial loading state
  if (isInitializing) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <InitialLoadingSkeleton />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="card p-8 text-center max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-rose-500/10 flex items-center justify-center mx-auto mb-4">
            <ShieldAlert className="w-8 h-8 text-rose-500" />
          </div>
          <h2 className="text-xl font-bold mb-2">Agent Not Found</h2>
          <p className={clsx(
            "mb-6",
            theme === "dark" ? "text-surface-400" : "text-slate-500"
          )}>
            The agent you're looking for doesn't exist or has been deleted.
          </p>
          <button onClick={() => router.push("/")} className="btn-primary">
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Toast Container */}
      <Toaster
        position="top-right"
        toastOptions={{
          style: theme === "dark" ? {
            background: "rgb(30 41 59)",
            border: "1px solid rgb(51 65 85)",
            color: "rgb(241 245 249)",
          } : {
            background: "white",
            border: "1px solid rgb(226 232 240)",
            color: "rgb(15 23 42)",
          },
        }}
      />

      {/* Header */}
      <header className="header-bar flex-shrink-0">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className={clsx(
                "p-2 rounded-lg transition-colors",
                theme === "dark" ? "hover:bg-surface-800" : "hover:bg-slate-100"
              )}
              title="Back to agents"
            >
              <ArrowLeft className={clsx(
                "w-5 h-5",
                theme === "dark" ? "text-surface-400" : "text-slate-500"
              )} />
            </button>

            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg"
                style={{
                  background: `linear-gradient(135deg, ${agent.color}30, ${agent.color}50)`,
                }}
              >
                <Bot size={20} style={{ color: agent.color }} />
              </div>
              <div>
                {isEditingName ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSaveName();
                        if (e.key === "Escape") setIsEditingName(false);
                      }}
                      className={clsx(
                        "border rounded px-2 py-1 font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                        theme === "dark" 
                          ? "bg-surface-800 border-surface-600 text-white" 
                          : "bg-white border-slate-300 text-slate-900"
                      )}
                      autoFocus
                    />
                    <button
                      onClick={handleSaveName}
                      className={clsx(
                        "p-1 text-emerald-500 rounded",
                        theme === "dark" ? "hover:bg-surface-800" : "hover:bg-slate-100"
                      )}
                    >
                      <Check size={16} />
                    </button>
                    <button
                      onClick={() => setIsEditingName(false)}
                      className={clsx(
                        "p-1 text-rose-500 rounded",
                        theme === "dark" ? "hover:bg-surface-800" : "hover:bg-slate-100"
                      )}
                    >
                      <X size={16} />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 group">
                    <h1 className="font-semibold">{agent.name}</h1>
                    <button
                      onClick={() => setIsEditingName(true)}
                      className={clsx(
                        "p-1 opacity-0 group-hover:opacity-100 rounded transition-all",
                        theme === "dark" ? "hover:bg-surface-800" : "hover:bg-slate-100"
                      )}
                    >
                      <Pencil size={14} className={theme === "dark" ? "text-surface-400" : "text-slate-400"} />
                    </button>
                  </div>
                )}
                <p className={clsx(
                  "text-xs",
                  theme === "dark" ? "text-surface-400" : "text-slate-500"
                )}>
                  {agent.policy_type || "Insurance Assistant"}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Message count */}
            <div className={clsx(
              "flex items-center gap-2 text-sm",
              theme === "dark" ? "text-surface-400" : "text-slate-500"
            )}>
              <MessageSquare size={14} />
              <span>{messages.length}</span>
            </div>

            {/* New Chat Button */}
            <button
              onClick={handleNewChat}
              className="btn-secondary flex items-center gap-2 !px-3 !py-2 text-sm"
              title="Start new conversation (⌘⇧N)"
            >
              <RotateCcw size={14} />
              <span className="hidden sm:inline">New Chat</span>
            </button>

            {/* Theme Toggle */}
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <main className="flex-1 overflow-hidden flex flex-col max-w-4xl w-full mx-auto">
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6 scrollbar-thin">
          <WelcomeMessage agent={agent} onSuggestionClick={handleSuggestionClick} />

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              agentColor={agent.color}
              onCopy={() => handleCopy(message.content)}
              onFeedback={(type) => handleFeedback(message.id, type)}
            />
          ))}

          {isLoading && <ThinkingIndicator agentColor={agent.color} />}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className={clsx(
          "flex-shrink-0 border-t backdrop-blur-sm p-4",
          theme === "dark" 
            ? "border-surface-800 bg-surface-950/80" 
            : "border-slate-200 bg-white/80"
        )}>
          <div className="max-w-4xl mx-auto">
            <div className="relative flex items-end gap-3">
              <div className="flex-1 relative">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`Ask ${agent.name} about your coverage...`}
                  disabled={!sessionId || isLoading}
                  rows={1}
                  className="input-field resize-none min-h-[52px] max-h-32 pr-4 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ height: "auto" }}
                  onInput={(e) => {
                    const target = e.target as HTMLTextAreaElement;
                    target.style.height = "auto";
                    target.style.height = Math.min(target.scrollHeight, 128) + "px";
                  }}
                />
              </div>

              <button
                onClick={handleSend}
                disabled={!input.trim() || !sessionId || isLoading}
                className="h-[52px] w-[52px] flex items-center justify-center rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  background:
                    input.trim() && sessionId && !isLoading
                      ? `linear-gradient(135deg, ${agent.color}, ${agent.color}dd)`
                      : undefined,
                }}
              >
                {isLoading ? (
                  <Loader2 size={20} className={clsx(
                    "animate-spin",
                    theme === "dark" ? "text-surface-400" : "text-slate-400"
                  )} />
                ) : (
                  <Send
                    size={20}
                    className={input.trim() ? "text-white" : theme === "dark" ? "text-surface-500" : "text-slate-400"}
                  />
                )}
              </button>
            </div>

            <p className={clsx(
              "text-xs mt-2 text-center",
              theme === "dark" ? "text-surface-500" : "text-slate-400"
            )}>
              Press Enter to send • Shift+Enter for new line • ⌘K to focus • ⌘⇧N for new chat
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
