"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Send,
  Bot,
  User,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Loader2,
  ArrowLeft,
  Pencil,
  Check,
  X,
  MessageSquare,
} from "lucide-react";
import clsx from "clsx";

// =============================================================================
// Types
// =============================================================================

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
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

async function* streamMessage(
  sessionId: string,
  message: string
): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, stream: true }),
  });

  if (!res.ok) throw new Error("Failed to send message");
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data && data !== "{}") {
          yield data.replace(/\\n/g, "\n");
        }
      }
    }
  }
}

// =============================================================================
// Components
// =============================================================================

function CoverageStatusBadge({ content }: { content: string }) {
  const upperContent = content.toUpperCase();

  if (
    upperContent.includes("NOT COVERED") ||
    upperContent.includes("NOT_COVERED") ||
    upperContent.includes("EXCLUDED")
  ) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/30">
        <ShieldAlert size={12} />
        Not Covered
      </span>
    );
  }

  if (
    upperContent.includes("CONDITIONAL") ||
    upperContent.includes("CONDITIONS APPLY")
  ) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
        <Shield size={12} />
        Conditional
      </span>
    );
  }

  if (upperContent.includes("COVERED")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
        <ShieldCheck size={12} />
        Covered
      </span>
    );
  }

  return null;
}

function MessageBubble({ message, agentColor }: { message: Message; agentColor: string }) {
  const isUser = message.role === "user";

  return (
    <div
      className={clsx(
        "flex gap-3 animate-slide-up",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={clsx(
          "flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center",
          isUser
            ? "bg-brand-500/20 text-brand-400"
            : "border border-surface-700"
        )}
        style={!isUser ? { background: `${agentColor}15`, color: agentColor } : {}}
      >
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      <div className={clsx("flex-1 max-w-[80%]", isUser ? "text-right" : "text-left")}>
        <div
          className={clsx(
            "inline-block px-4 py-3 rounded-2xl",
            isUser
              ? "bg-gradient-to-br from-brand-500 to-brand-600 text-white rounded-tr-sm"
              : "bg-surface-800/80 text-surface-100 border border-surface-700 rounded-tl-sm"
          )}
        >
          {!isUser && message.content && (
            <div className="mb-2">
              <CoverageStatusBadge content={message.content} />
            </div>
          )}

          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
            {message.isStreaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-brand-400 animate-pulse rounded-sm" />
            )}
          </div>
        </div>

        <p className="text-xs text-surface-500 mt-1.5 px-1">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}

function WelcomeMessage({ 
  agent, 
  onSuggestionClick 
}: { 
  agent: Agent; 
  onSuggestionClick: (question: string) => void;
}) {
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
        className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center border border-surface-700"
        style={{ background: `${agent.color}15`, color: agent.color }}
      >
        <Bot size={18} />
      </div>
      <div className="flex-1">
        <div className="inline-block px-4 py-3 rounded-2xl rounded-tl-sm bg-surface-800/80 text-surface-100 border border-surface-700">
          <p className="text-sm leading-relaxed">
            👋 Hi! I'm <strong>{agent.name}</strong>, your insurance assistant
            {agent.policy_type && <> for <strong>{agent.policy_type}</strong></>}.
          </p>
          <p className="text-sm leading-relaxed mt-2 text-surface-400">
            I can help you understand your coverage, exclusions, deductibles, and more.
          </p>
        </div>
        
        <div className="mt-4 flex flex-wrap gap-2">
          {suggestions.map((q, i) => (
            <button
              key={i}
              onClick={() => onSuggestionClick(q)}
              className="px-3 py-1.5 bg-surface-800 hover:bg-surface-700 hover:border-brand-500/50 border border-surface-700 rounded-lg text-xs text-surface-300 hover:text-white transition-all cursor-pointer group"
            >
              <Sparkles size={12} className="inline mr-1.5 text-brand-400 group-hover:text-brand-300" />
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function TypingIndicator({ agentColor }: { agentColor: string }) {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center border border-surface-700"
        style={{ background: `${agentColor}15`, color: agentColor }}
      >
        <Bot size={18} />
      </div>
      <div className="bg-surface-800/80 border border-surface-700 rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex gap-1.5">
          <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:0ms]" style={{ background: agentColor }} />
          <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:150ms]" style={{ background: agentColor }} />
          <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:300ms]" style={{ background: agentColor }} />
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

  const [agent, setAgent] = useState<Agent | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Name editing
  const [isEditingName, setIsEditingName] = useState(false);
  const [editName, setEditName] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load agent and create session
  useEffect(() => {
    const init = async () => {
      try {
        const agentData = await fetchAgent(agentId);
        setAgent(agentData);
        setEditName(agentData.name);

        const session = await createSession(agentId);
        setSessionId(session.session_id);
      } catch (err) {
        console.error("Failed to initialize:", err);
        setError("Failed to load agent. It may not exist.");
      }
    };
    init();
  }, [agentId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    } catch (err) {
      console.error("Failed to update name:", err);
    }
  };

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
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const assistantId = (Date.now() + 1).toString();
      const assistantMessage: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      let fullContent = "";
      for await (const token of streamMessage(sessionId, userMessage.content)) {
        fullContent += token;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, content: fullContent } : msg
          )
        );
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId ? { ...msg, isStreaming: false } : msg
        )
      );
    } catch (err) {
      console.error("Failed to send message:", err);
      setError("Failed to send message. Please try again.");
      setMessages((prev) => prev.filter((m) => !m.isStreaming));
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
    setError(null);

    try {
      const assistantId = (Date.now() + 1).toString();
      const assistantMessage: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      let fullContent = "";
      for await (const token of streamMessage(sessionId, question)) {
        fullContent += token;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, content: fullContent } : msg
          )
        );
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId ? { ...msg, isStreaming: false } : msg
        )
      );
    } catch (err) {
      console.error("Failed to send message:", err);
      setError("Failed to send message. Please try again.");
      setMessages((prev) => prev.filter((m) => !m.isStreaming));
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  if (error && !agent) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="card p-8 text-center max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-rose-500/10 flex items-center justify-center mx-auto mb-4">
            <ShieldAlert className="w-8 h-8 text-rose-400" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Agent Not Found</h2>
          <p className="text-surface-400 mb-6">{error}</p>
          <button onClick={() => router.push("/")} className="btn-primary">
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-surface-800 bg-surface-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className="p-2 hover:bg-surface-800 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-surface-400" />
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
                      className="bg-surface-800 border border-surface-600 rounded px-2 py-1 text-white font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                      autoFocus
                    />
                    <button onClick={handleSaveName} className="p-1 text-emerald-400 hover:bg-surface-800 rounded">
                      <Check size={16} />
                    </button>
                    <button onClick={() => setIsEditingName(false)} className="p-1 text-rose-400 hover:bg-surface-800 rounded">
                      <X size={16} />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 group">
                    <h1 className="font-semibold text-white">{agent.name}</h1>
                    <button
                      onClick={() => setIsEditingName(true)}
                      className="p-1 opacity-0 group-hover:opacity-100 hover:bg-surface-800 rounded transition-all"
                    >
                      <Pencil size={14} className="text-surface-400" />
                    </button>
                  </div>
                )}
                <p className="text-xs text-surface-400">
                  {agent.policy_type || "Insurance Assistant"}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 text-sm text-surface-400">
            <MessageSquare size={14} />
            <span>{messages.length}</span>
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
            />
          ))}

          {isLoading && !messages.some((m) => m.isStreaming) && (
            <TypingIndicator agentColor={agent.color} />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error */}
        {error && (
          <div className="px-4 pb-2">
            <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-lg px-4 py-2 text-sm">
              {error}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="flex-shrink-0 border-t border-surface-800 bg-surface-950/80 backdrop-blur-sm p-4">
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
                  <Loader2 size={20} className="animate-spin text-surface-400" />
                ) : (
                  <Send size={20} className={input.trim() ? "text-white" : "text-surface-500"} />
                )}
              </button>
            </div>

            <p className="text-xs text-surface-500 mt-2 text-center">
              Press Enter to send • Shift+Enter for new line
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

