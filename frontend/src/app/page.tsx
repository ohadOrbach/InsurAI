"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Bot,
  Plus,
  Shield,
  MessageSquare,
  Clock,
  Pencil,
  Check,
  X,
  Loader2,
  AlertTriangle,
  Sparkles,
} from "lucide-react";
import clsx from "clsx";
import { ThemeToggle } from "@/components/theme-toggle";
import { AgentCardSkeleton } from "@/components/loading-skeleton";
import { useTheme } from "@/lib/theme-context";

// =============================================================================
// Types
// =============================================================================

interface Agent {
  id: number;
  name: string;
  description: string | null;
  agent_type: "personal" | "shared";
  status: string;
  policy_id: string;
  policy_type: string | null;
  provider_name: string | null;
  color: string;
  created_at: string;
  last_used_at: string | null;
  total_conversations: number;
  total_messages: number;
  coverage_summary: {
    total_categories?: number;
    total_inclusions?: number;
    total_exclusions?: number;
    categories?: string[];
  };
}

// =============================================================================
// API Client
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

async function fetchAgents(): Promise<Agent[]> {
  const res = await fetch(`${API_BASE}/agents`);
  if (!res.ok) throw new Error("Failed to fetch agents");
  const data = await res.json();
  return data.agents;
}

async function updateAgentName(id: number, name: string): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("Failed to update agent");
  return res.json();
}

async function createDemoAgent(name: string): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents/create/demo?name=${encodeURIComponent(name)}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to create agent");
  const data = await res.json();
  return data.agent;
}

// =============================================================================
// Components
// =============================================================================

function AgentCard({ 
  agent, 
  onClick, 
  onNameChange 
}: { 
  agent: Agent; 
  onClick: () => void;
  onNameChange: (name: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(agent.name);
  const inputRef = useRef<HTMLInputElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = () => {
    if (editName.trim() && editName !== agent.name) {
      onNameChange(editName.trim());
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditName(agent.name);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  };

  return (
    <div className="group card p-6 hover:border-brand-500/50 transition-all duration-300">
      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        {/* Avatar - Clickable to chat */}
        <button
          onClick={onClick}
          className="w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg transition-all hover:scale-105 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          style={{
            background: `linear-gradient(135deg, ${agent.color}20, ${agent.color}40)`,
            borderColor: `${agent.color}50`,
            borderWidth: 1,
          }}
        >
          <Bot className="w-8 h-8" style={{ color: agent.color }} />
        </button>

        {/* Info */}
        <div className="flex-1 min-w-0">
          {/* Editable Name */}
          <div className="flex items-center gap-2 mb-1">
            {isEditing ? (
              <div className="flex items-center gap-2 flex-1">
                <input
                  ref={inputRef}
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onBlur={handleSave}
                  className={clsx(
                    "flex-1 border rounded-lg px-3 py-1.5 text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                    theme === "dark"
                      ? "bg-surface-800 border-surface-600 text-white"
                      : "bg-white border-slate-300 text-slate-900"
                  )}
                />
                <button
                  onClick={handleSave}
                  className="p-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-500 rounded-lg transition-colors"
                >
                  <Check size={16} />
                </button>
                <button
                  onClick={handleCancel}
                  className="p-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-500 rounded-lg transition-colors"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <>
                <button
                  onClick={onClick}
                  className="font-semibold text-lg truncate hover:text-brand-500 transition-colors text-left"
                >
                  {agent.name}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsEditing(true);
                  }}
                  className={clsx(
                    "p-1.5 opacity-0 group-hover:opacity-100 rounded-lg transition-all",
                    theme === "dark" ? "hover:bg-surface-700" : "hover:bg-slate-100"
                  )}
                >
                  <Pencil size={14} className={theme === "dark" ? "text-surface-400" : "text-slate-400"} />
                </button>
              </>
            )}
          </div>
          <p className={clsx(
            "text-sm truncate",
            theme === "dark" ? "text-surface-400" : "text-slate-500"
          )}>
            {agent.provider_name || "Insurance Provider"} · {agent.policy_type || "Policy"}
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className={clsx(
          "rounded-lg p-3",
          theme === "dark" ? "bg-surface-800/50" : "bg-slate-50"
        )}>
          <div className={clsx(
            "flex items-center gap-1.5 text-xs mb-1",
            theme === "dark" ? "text-surface-500" : "text-slate-500"
          )}>
            <MessageSquare className="w-3.5 h-3.5" />
            Chats
          </div>
          <p className="font-semibold">{agent.total_conversations}</p>
        </div>
        <div className={clsx(
          "rounded-lg p-3",
          theme === "dark" ? "bg-surface-800/50" : "bg-slate-50"
        )}>
          <div className={clsx(
            "flex items-center gap-1.5 text-xs mb-1",
            theme === "dark" ? "text-surface-500" : "text-slate-500"
          )}>
            <Shield className="w-3.5 h-3.5" />
            Coverage
          </div>
          <p className="font-semibold">
            {agent.coverage_summary?.total_inclusions || 0}
          </p>
        </div>
        <div className={clsx(
          "rounded-lg p-3",
          theme === "dark" ? "bg-surface-800/50" : "bg-slate-50"
        )}>
          <div className={clsx(
            "flex items-center gap-1.5 text-xs mb-1",
            theme === "dark" ? "text-surface-500" : "text-slate-500"
          )}>
            <Clock className="w-3.5 h-3.5" />
            Last Used
          </div>
          <p className="font-semibold text-xs">
            {agent.last_used_at
              ? new Date(agent.last_used_at).toLocaleDateString()
              : "Never"}
          </p>
        </div>
      </div>

      {/* Categories */}
      {agent.coverage_summary?.categories && agent.coverage_summary.categories.length > 0 && (
        <div className={clsx(
          "pt-4 border-t",
          theme === "dark" ? "border-surface-800" : "border-slate-200"
        )}>
          <div className="flex flex-wrap gap-2">
            {agent.coverage_summary.categories.slice(0, 3).map((cat, i) => (
              <span
                key={i}
                className={clsx(
                  "px-2 py-1 rounded text-xs",
                  theme === "dark" 
                    ? "bg-surface-800 text-surface-400" 
                    : "bg-slate-100 text-slate-600"
                )}
              >
                {cat}
              </span>
            ))}
            {agent.coverage_summary.categories.length > 3 && (
              <span className={clsx(
                "px-2 py-1 text-xs",
                theme === "dark" ? "text-surface-500" : "text-slate-400"
              )}>
                +{agent.coverage_summary.categories.length - 3} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Chat Button */}
      <button
        onClick={onClick}
        className="mt-4 w-full btn-primary flex items-center justify-center gap-2"
      >
        <MessageSquare size={18} />
        Start Chat
      </button>
    </div>
  );
}

function CreateAgentCard({ onClick }: { onClick: () => void }) {
  const { theme } = useTheme();
  
  return (
    <button
      onClick={onClick}
      className="card p-6 border-dashed hover:border-brand-500/50 transition-all duration-300 group h-full min-h-[280px] flex flex-col items-center justify-center"
    >
      <div className="w-20 h-20 rounded-2xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
        <Plus className="w-10 h-10 text-brand-500" />
      </div>
      <h3 className="font-semibold text-xl mb-2 group-hover:text-brand-500 transition-colors">
        New Agent
      </h3>
      <p className={clsx(
        "text-sm text-center max-w-xs",
        theme === "dark" ? "text-surface-400" : "text-slate-500"
      )}>
        Upload a policy document to create a new insurance assistant
      </p>
    </button>
  );
}

function EmptyState({ onCreateDemo, onCreate }: { onCreateDemo: () => void; onCreate: () => void }) {
  const { theme } = useTheme();
  
  return (
    <div className="card p-12 text-center">
      <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-brand-500/20 to-brand-600/20 flex items-center justify-center mx-auto mb-6">
        <Bot className="w-12 h-12 text-brand-500" />
      </div>
      <h2 className="text-3xl font-bold mb-3">Welcome to InsurAI</h2>
      <p className={clsx(
        "max-w-md mx-auto mb-8 text-lg",
        theme === "dark" ? "text-surface-400" : "text-slate-500"
      )}>
        Create your first insurance agent by uploading a policy document.
        Each agent specializes in understanding one specific policy.
      </p>
      <div className="flex items-center justify-center gap-4">
        <button onClick={onCreate} className="btn-primary flex items-center gap-2 text-lg px-6 py-3">
          <Plus className="w-5 h-5" />
          Create Agent
        </button>
        <button onClick={onCreateDemo} className="btn-secondary flex items-center gap-2">
          <Sparkles className="w-5 h-5" />
          Try Demo
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// Main Page
// =============================================================================

export default function HomePage() {
  const router = useRouter();
  const { theme } = useTheme();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch agents on mount
  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      const data = await fetchAgents();
      setAgents(data);
    } catch (err) {
      console.error("Failed to fetch agents:", err);
      setError("Failed to load agents. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  // Create demo agent
  const handleCreateDemo = async () => {
    setCreating(true);
    setError(null);
    try {
      const name = `Insurance Agent ${agents.length + 1}`;
      const agent = await createDemoAgent(name);
      setAgents([agent, ...agents]);
    } catch (err) {
      console.error("Failed to create demo agent:", err);
      setError("Failed to create agent. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  // Update agent name
  const handleNameChange = async (agentId: number, newName: string) => {
    try {
      await updateAgentName(agentId, newName);
      setAgents(agents.map(a => 
        a.id === agentId ? { ...a, name: newName } : a
      ));
    } catch (err) {
      console.error("Failed to update name:", err);
      setError("Failed to update agent name.");
    }
  };

  // Navigate to agent chat
  const handleAgentClick = (agent: Agent) => {
    router.push(`/agents/${agent.id}`);
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="header-bar">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <Shield size={22} className="text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-lg">InsurAI</h1>
              <p className={clsx(
                "text-xs",
                theme === "dark" ? "text-surface-400" : "text-slate-500"
              )}>Policy Intelligence</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {agents.length > 0 && (
              <>
                <button
                  onClick={handleCreateDemo}
                  disabled={creating}
                  className="btn-secondary flex items-center gap-2"
                >
                  {creating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4" />
                  )}
                  Demo
                </button>
                <button
                  onClick={() => router.push("/agents/new")}
                  className="btn-primary flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  New Agent
                </button>
              </>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Error */}
        {error && (
          <div className="mb-6 bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-start gap-3 animate-slide-up">
            <AlertTriangle className="w-5 h-5 text-rose-500 mt-0.5" />
            <div>
              <p className="font-medium text-rose-500">Error</p>
              <p className="text-sm text-rose-400">{error}</p>
            </div>
          </div>
        )}

        {/* Loading State with Skeletons */}
        {loading && (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <AgentCardSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && agents.length === 0 && (
          <EmptyState 
            onCreateDemo={handleCreateDemo} 
            onCreate={() => router.push("/agents/new")} 
          />
        )}

        {/* Agent Grid */}
        {!loading && agents.length > 0 && (
          <>
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-2">My Agents</h2>
              <p className={theme === "dark" ? "text-surface-400" : "text-slate-500"}>
                Click an agent to start chatting, or click the pencil to rename
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {agents.map((agent, index) => (
                <div
                  key={agent.id}
                  className="animate-slide-up opacity-0"
                  style={{ animationDelay: `${index * 100}ms`, animationFillMode: "forwards" }}
                >
                  <AgentCard
                    agent={agent}
                    onClick={() => handleAgentClick(agent)}
                    onNameChange={(name) => handleNameChange(agent.id, name)}
                  />
                </div>
              ))}

              {/* Create Card */}
              <div
                className="animate-slide-up opacity-0"
                style={{ animationDelay: `${agents.length * 100}ms`, animationFillMode: "forwards" }}
              >
                <CreateAgentCard onClick={() => router.push("/agents/new")} />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
