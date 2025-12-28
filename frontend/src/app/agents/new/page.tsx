"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Upload,
  FileText,
  X,
  CheckCircle,
  AlertTriangle,
  Loader2,
  ArrowLeft,
  Shield,
  Bot,
  Sparkles,
} from "lucide-react";
import clsx from "clsx";

// =============================================================================
// Types
// =============================================================================

interface CreateAgentResponse {
  agent: {
    id: number;
    name: string;
    policy_id: string;
    color: string;
  };
}

// =============================================================================
// API Client
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

async function createAgentFromPDF(
  file: File,
  name: string
): Promise<CreateAgentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", name);

  const res = await fetch(`${API_BASE}/agents/create/pdf`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Failed to create agent");
  }

  return res.json();
}

async function createAgentFromText(
  text: string,
  name: string
): Promise<CreateAgentResponse> {
  const res = await fetch(`${API_BASE}/agents/create/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: text, name }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Creation failed" }));
    throw new Error(error.detail || "Failed to create agent");
  }

  return res.json();
}

// =============================================================================
// Main Page
// =============================================================================

export default function NewAgentPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<"upload" | "name">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [textContent, setTextContent] = useState("");
  const [agentName, setAgentName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [mode, setMode] = useState<"pdf" | "text">("pdf");

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "application/pdf" || droppedFile.name.endsWith(".pdf")) {
        setFile(droppedFile);
        setMode("pdf");
        setError(null);
      } else {
        setError("Please upload a PDF file");
      }
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleContinue = () => {
    if ((mode === "pdf" && file) || (mode === "text" && textContent.trim())) {
      // Generate default name
      if (!agentName) {
        if (file) {
          const baseName = file.name.replace(/\.pdf$/i, "");
          setAgentName(baseName.substring(0, 30));
        } else {
          setAgentName("My Insurance Agent");
        }
      }
      setStep("name");
    }
  };

  const handleCreate = async () => {
    if (!agentName.trim()) {
      setError("Please enter a name for your agent");
      return;
    }

    setUploading(true);
    setError(null);

    try {
      let result: CreateAgentResponse;

      if (mode === "pdf" && file) {
        result = await createAgentFromPDF(file, agentName.trim());
      } else if (mode === "text" && textContent.trim()) {
        result = await createAgentFromText(textContent.trim(), agentName.trim());
      } else {
        throw new Error("Please provide content to upload");
      }

      // Navigate to the new agent's chat
      router.push(`/agents/${result.agent.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create agent");
      setUploading(false);
    }
  };

  const canContinue = (mode === "pdf" && file) || (mode === "text" && textContent.trim().length > 100);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-surface-800 bg-surface-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => router.push("/")}
            className="p-2 hover:bg-surface-800 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-surface-400" />
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <Shield size={22} className="text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-white">Create New Agent</h1>
              <p className="text-xs text-surface-400">
                {step === "upload" ? "Step 1: Upload Policy" : "Step 2: Name Your Agent"}
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        {/* Progress */}
        <div className="flex items-center gap-4 mb-8">
          <div className={clsx(
            "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium",
            step === "upload" 
              ? "bg-brand-500/20 text-brand-400 border border-brand-500/30"
              : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
          )}>
            {step === "name" ? <CheckCircle size={16} /> : <span className="w-5 h-5 flex items-center justify-center">1</span>}
            Upload
          </div>
          <div className="flex-1 h-px bg-surface-700" />
          <div className={clsx(
            "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium",
            step === "name"
              ? "bg-brand-500/20 text-brand-400 border border-brand-500/30"
              : "bg-surface-800 text-surface-500 border border-surface-700"
          )}>
            <span className="w-5 h-5 flex items-center justify-center">2</span>
            Name
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 mt-0.5" />
            <div>
              <p className="font-medium">Error</p>
              <p className="text-sm opacity-80">{error}</p>
            </div>
          </div>
        )}

        {/* Step 1: Upload */}
        {step === "upload" && (
          <div className="card p-8 animate-fade-in">
            <h2 className="text-2xl font-bold text-white mb-2">Upload Your Policy</h2>
            <p className="text-surface-400 mb-6">
              Upload a PDF of your insurance policy document. Our AI will analyze it and create a personalized assistant.
            </p>

            {/* Mode Tabs */}
            <div className="flex gap-2 mb-6">
              <button
                onClick={() => setMode("pdf")}
                className={clsx(
                  "flex-1 py-3 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2",
                  mode === "pdf"
                    ? "bg-brand-500/10 text-brand-400 border border-brand-500/30"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200"
                )}
              >
                <FileText className="w-5 h-5" />
                PDF Upload
              </button>
              <button
                onClick={() => setMode("text")}
                className={clsx(
                  "flex-1 py-3 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2",
                  mode === "text"
                    ? "bg-brand-500/10 text-brand-400 border border-brand-500/30"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200"
                )}
              >
                <FileText className="w-5 h-5" />
                Paste Text
              </button>
            </div>

            {/* PDF Upload */}
            {mode === "pdf" && (
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={clsx(
                  "relative border-2 border-dashed rounded-xl p-12 text-center transition-all",
                  dragActive
                    ? "border-brand-500 bg-brand-500/10"
                    : file
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-surface-700 hover:border-surface-600"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={handleFileSelect}
                  className="hidden"
                />

                {file ? (
                  <div className="flex flex-col items-center">
                    <div className="w-16 h-16 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-4">
                      <CheckCircle className="w-8 h-8 text-emerald-400" />
                    </div>
                    <p className="text-lg font-medium text-white mb-1">{file.name}</p>
                    <p className="text-sm text-surface-400 mb-4">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    <button
                      onClick={() => setFile(null)}
                      className="text-sm text-rose-400 hover:text-rose-300 flex items-center gap-1"
                    >
                      <X className="w-4 h-4" />
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <div className="w-16 h-16 rounded-xl bg-surface-800 flex items-center justify-center mb-4">
                      <Upload className="w-8 h-8 text-surface-400" />
                    </div>
                    <p className="text-lg font-medium text-white mb-1">
                      Drop your policy PDF here
                    </p>
                    <p className="text-sm text-surface-400 mb-4">or click to browse</p>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="btn-secondary"
                    >
                      Select File
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Text Input */}
            {mode === "text" && (
              <div>
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  placeholder="Paste your policy document text here..."
                  rows={12}
                  className="input-field font-mono text-sm resize-none scrollbar-thin"
                />
                <p className="text-xs text-surface-500 mt-2">
                  {textContent.length} characters (minimum 100 required)
                </p>
              </div>
            )}

            {/* Continue Button */}
            <div className="mt-6 flex justify-end">
              <button
                onClick={handleContinue}
                disabled={!canContinue}
                className="btn-primary flex items-center gap-2"
              >
                Continue
                <ArrowLeft className="w-4 h-4 rotate-180" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Name */}
        {step === "name" && (
          <div className="card p-8 animate-fade-in">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500/20 to-brand-600/20 flex items-center justify-center">
                <Bot className="w-8 h-8 text-brand-400" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">Name Your Agent</h2>
                <p className="text-surface-400">Give your insurance assistant a memorable name</p>
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-surface-300 mb-2">
                Agent Name
              </label>
              <input
                type="text"
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="e.g., My Car Insurance, Home Policy..."
                className="input-field text-lg"
                maxLength={50}
              />
              <p className="text-xs text-surface-500 mt-2">
                You can change this later by clicking the pencil icon
              </p>
            </div>

            {/* Summary */}
            <div className="bg-surface-800/50 rounded-lg p-4 mb-6">
              <h3 className="text-sm font-medium text-surface-300 mb-3">Summary</h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-surface-400">Source</span>
                  <span className="text-white">
                    {mode === "pdf" ? file?.name : `${textContent.length} characters`}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-surface-400">Agent Name</span>
                  <span className="text-white">{agentName || "—"}</span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between">
              <button
                onClick={() => setStep("upload")}
                className="btn-secondary flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
              <button
                onClick={handleCreate}
                disabled={uploading || !agentName.trim()}
                className="btn-primary flex items-center gap-2"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Create Agent
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

