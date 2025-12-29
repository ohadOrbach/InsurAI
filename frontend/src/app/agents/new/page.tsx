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
  ArrowRight,
  Shield,
  Bot,
  Sparkles,
  File,
  Hash,
} from "lucide-react";
import clsx from "clsx";
import { ThemeToggle } from "@/components/theme-toggle";
import { useTheme } from "@/lib/theme-context";

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
// Step Indicator Component
// =============================================================================

function StepIndicator({ 
  currentStep, 
  steps 
}: { 
  currentStep: number; 
  steps: { label: string; description: string }[] 
}) {
  const { theme } = useTheme();
  
  return (
    <div className="mb-8">
      {/* Steps */}
      <div className="flex items-center justify-center gap-0">
        {steps.map((step, index) => {
          const stepNum = index + 1;
          const isActive = stepNum === currentStep;
          const isCompleted = stepNum < currentStep;
          
          return (
            <div key={index} className="flex items-center">
              {/* Step Circle */}
              <div className="flex flex-col items-center">
                <div
                  className={clsx(
                    "w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm transition-all",
                    isCompleted
                      ? "bg-emerald-500 text-white"
                      : isActive
                        ? "bg-brand-500 text-white shadow-lg shadow-brand-500/30"
                        : theme === "dark"
                          ? "bg-surface-800 text-surface-500 border border-surface-700"
                          : "bg-slate-100 text-slate-400 border border-slate-200"
                  )}
                >
                  {isCompleted ? <CheckCircle size={20} /> : stepNum}
                </div>
                <div className="mt-2 text-center">
                  <p className={clsx(
                    "text-sm font-medium",
                    isActive || isCompleted 
                      ? theme === "dark" ? "text-white" : "text-slate-900"
                      : theme === "dark" ? "text-surface-500" : "text-slate-400"
                  )}>
                    {step.label}
                  </p>
                  <p className={clsx(
                    "text-xs mt-0.5",
                    theme === "dark" ? "text-surface-500" : "text-slate-400"
                  )}>
                    {step.description}
                  </p>
                </div>
              </div>
              
              {/* Connector Line */}
              {index < steps.length - 1 && (
                <div className={clsx(
                  "w-24 h-0.5 mx-4 mb-8",
                  isCompleted
                    ? "bg-emerald-500"
                    : theme === "dark" ? "bg-surface-700" : "bg-slate-200"
                )} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// Summary Card Component
// =============================================================================

function SummaryCard({
  file,
  textContent,
  agentName,
  mode,
}: {
  file: File | null;
  textContent: string;
  agentName: string;
  mode: "pdf" | "text";
}) {
  const { theme } = useTheme();
  
  return (
    <div className={clsx(
      "rounded-xl p-5 mb-6 border",
      theme === "dark"
        ? "bg-gradient-to-br from-surface-800/80 to-surface-800/40 border-surface-700"
        : "bg-gradient-to-br from-slate-50 to-white border-slate-200"
    )}>
      <div className="flex items-center gap-2 mb-4">
        <div className={clsx(
          "w-8 h-8 rounded-lg flex items-center justify-center",
          theme === "dark" ? "bg-brand-500/20" : "bg-brand-500/10"
        )}>
          <FileText size={16} className="text-brand-500" />
        </div>
        <div>
          <h3 className={clsx(
            "text-sm font-semibold",
            theme === "dark" ? "text-white" : "text-slate-900"
          )}>
            Review Before Creating
          </h3>
          <p className={clsx(
            "text-xs",
            theme === "dark" ? "text-surface-400" : "text-slate-500"
          )}>
            Confirm your agent details
          </p>
        </div>
      </div>
      
      <div className="space-y-3">
        {/* Source File/Text */}
        <div className={clsx(
          "flex items-center gap-3 p-3 rounded-lg",
          theme === "dark" ? "bg-surface-900/50" : "bg-slate-100/80"
        )}>
          <div className={clsx(
            "w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",
            theme === "dark" ? "bg-surface-700" : "bg-white border border-slate-200"
          )}>
            <File size={18} className={theme === "dark" ? "text-surface-400" : "text-slate-500"} />
          </div>
          <div className="flex-1 min-w-0">
            <p className={clsx(
              "text-xs font-medium uppercase tracking-wide mb-0.5",
              theme === "dark" ? "text-surface-500" : "text-slate-400"
            )}>
              Source Document
            </p>
            <p className={clsx(
              "text-sm font-medium truncate",
              theme === "dark" ? "text-white" : "text-slate-900"
            )}>
              {mode === "pdf" ? file?.name : `Pasted text (${textContent.length} chars)`}
            </p>
          </div>
          {mode === "pdf" && file && (
            <span className={clsx(
              "text-xs px-2 py-1 rounded-full",
              theme === "dark" 
                ? "bg-emerald-500/10 text-emerald-400" 
                : "bg-emerald-50 text-emerald-600"
            )}>
              {(file.size / 1024 / 1024).toFixed(1)} MB
            </span>
          )}
        </div>
        
        {/* Agent Name */}
        <div className={clsx(
          "flex items-center gap-3 p-3 rounded-lg",
          theme === "dark" ? "bg-surface-900/50" : "bg-slate-100/80"
        )}>
          <div className={clsx(
            "w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",
            theme === "dark" ? "bg-surface-700" : "bg-white border border-slate-200"
          )}>
            <Bot size={18} className={theme === "dark" ? "text-surface-400" : "text-slate-500"} />
          </div>
          <div className="flex-1 min-w-0">
            <p className={clsx(
              "text-xs font-medium uppercase tracking-wide mb-0.5",
              theme === "dark" ? "text-surface-500" : "text-slate-400"
            )}>
              Agent Name
            </p>
            <p className={clsx(
              "text-sm font-medium truncate",
              theme === "dark" ? "text-white" : "text-slate-900"
            )}>
              {agentName || "Not set"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Page
// =============================================================================

export default function NewAgentPage() {
  const router = useRouter();
  const { theme } = useTheme();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<"upload" | "name">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [textContent, setTextContent] = useState("");
  const [agentName, setAgentName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [mode, setMode] = useState<"pdf" | "text">("pdf");

  const steps = [
    { label: "Upload", description: "Add policy document" },
    { label: "Name", description: "Name your assistant" },
  ];

  const currentStepNum = step === "upload" ? 1 : 2;

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
      <header className="header-bar">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className={clsx(
                "p-2 rounded-lg transition-colors",
                theme === "dark" ? "hover:bg-surface-800" : "hover:bg-slate-100"
              )}
            >
              <ArrowLeft className={clsx(
                "w-5 h-5",
                theme === "dark" ? "text-surface-400" : "text-slate-500"
              )} />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/20">
                <Shield size={22} className="text-white" />
              </div>
              <div>
                <h1 className="font-semibold">Create New Agent</h1>
                <p className={clsx(
                  "text-xs",
                  theme === "dark" ? "text-surface-400" : "text-slate-500"
                )}>
                  {step === "upload" ? "Step 1 of 2" : "Step 2 of 2"}
                </p>
              </div>
            </div>
          </div>
          
          <ThemeToggle />
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        {/* Progress Steps */}
        <StepIndicator currentStep={currentStepNum} steps={steps} />

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-500 flex items-start gap-3">
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
            <h2 className="text-2xl font-bold mb-2">Upload Your Policy</h2>
            <p className={clsx(
              "mb-6",
              theme === "dark" ? "text-surface-400" : "text-slate-500"
            )}>
              Upload a PDF of your insurance policy document. Our AI will analyze it and create a personalized assistant.
            </p>

            {/* Mode Tabs */}
            <div className="flex gap-2 mb-6">
              <button
                onClick={() => setMode("pdf")}
                className={clsx(
                  "flex-1 py-3 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2",
                  mode === "pdf"
                    ? "bg-brand-500/10 text-brand-500 border border-brand-500/30"
                    : theme === "dark"
                      ? "bg-surface-800 text-surface-400 hover:text-surface-200"
                      : "bg-slate-100 text-slate-500 hover:text-slate-700"
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
                    ? "bg-brand-500/10 text-brand-500 border border-brand-500/30"
                    : theme === "dark"
                      ? "bg-surface-800 text-surface-400 hover:text-surface-200"
                      : "bg-slate-100 text-slate-500 hover:text-slate-700"
                )}
              >
                <Hash className="w-5 h-5" />
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
                    : theme === "dark"
                      ? "border-surface-700 hover:border-surface-600"
                      : "border-slate-300 hover:border-slate-400"
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
                      <CheckCircle className="w-8 h-8 text-emerald-500" />
                    </div>
                    <p className="text-lg font-medium mb-1">{file.name}</p>
                    <p className={clsx(
                      "text-sm mb-4",
                      theme === "dark" ? "text-surface-400" : "text-slate-500"
                    )}>
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    <button
                      onClick={() => setFile(null)}
                      className="text-sm text-rose-500 hover:text-rose-400 flex items-center gap-1"
                    >
                      <X className="w-4 h-4" />
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <div className={clsx(
                      "w-16 h-16 rounded-xl flex items-center justify-center mb-4",
                      theme === "dark" ? "bg-surface-800" : "bg-slate-100"
                    )}>
                      <Upload className={clsx(
                        "w-8 h-8",
                        theme === "dark" ? "text-surface-400" : "text-slate-400"
                      )} />
                    </div>
                    <p className="text-lg font-medium mb-1">
                      Drop your policy PDF here
                    </p>
                    <p className={clsx(
                      "text-sm mb-4",
                      theme === "dark" ? "text-surface-400" : "text-slate-500"
                    )}>
                      or click to browse
                    </p>
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
                <p className={clsx(
                  "text-xs mt-2",
                  theme === "dark" ? "text-surface-500" : "text-slate-400"
                )}>
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
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Name */}
        {step === "name" && (
          <div className="card p-8 animate-fade-in">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500/20 to-brand-600/20 flex items-center justify-center">
                <Bot className="w-8 h-8 text-brand-500" />
              </div>
              <div>
                <h2 className="text-2xl font-bold">Name Your Agent</h2>
                <p className={theme === "dark" ? "text-surface-400" : "text-slate-500"}>
                  Give your insurance assistant a memorable name
                </p>
              </div>
            </div>

            <div className="mb-6">
              <label className={clsx(
                "block text-sm font-medium mb-2",
                theme === "dark" ? "text-surface-300" : "text-slate-700"
              )}>
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
              <p className={clsx(
                "text-xs mt-2",
                theme === "dark" ? "text-surface-500" : "text-slate-400"
              )}>
                You can change this later by clicking the pencil icon
              </p>
            </div>

            {/* Summary Card */}
            <SummaryCard
              file={file}
              textContent={textContent}
              agentName={agentName}
              mode={mode}
            />

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
