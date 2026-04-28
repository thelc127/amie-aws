"use client";

import { useState, useCallback, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ── Types ─────────────────────────────────────────────────────────────────────

type SD = "Present" | "Implied" | "Absent" | null;

interface IDCAResult {
  sd: SD;
  structural_synopsis: string;
  source_citation: string;
  fields_map: string[];
  reasoning: string;
}

interface Reference {
  citation: string;
  rs_synopsis: string;
  css: number;
  ewss: number;
  url?: string;
  notes?: string;
}

interface NAAResult {
  ss_synopsis: string;
  ucs: string;
  references: Reference[];
}

interface AAResult {
  context_header: {
    source_citation: string;
    ss_synopsis: string;
    sd: SD;
    fields_map: string[];
  };
  final_reference_table: Reference[];
  executive_summary: string;
  novelty_risk: "High" | "Medium" | "Low" | "Indeterminate";
}

interface Task {
  task_id: string;
  status: string;
  idca?: IDCAResult;
  naa?: NAAResult;
  aa?: AAResult;
  error?: string;
}

// ── Inline SVG Icons ──────────────────────────────────────────────────────────

function IconUpload() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 16 12 12 8 16" />
      <line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
    </svg>
  );
}

function IconFile() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function IconBarChart() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function IconClock() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function IconChevronDown() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function IconChevronUp() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="18 15 12 9 6 15" />
    </svg>
  );
}

function IconExternalLink() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

// ── Constants ─────────────────────────────────────────────────────────────────

const RISK_COLORS: Record<string, string> = {
  High: "bg-red-100 text-red-800 border-red-200",
  Medium: "bg-amber-100 text-amber-800 border-amber-200",
  Low: "bg-green-100 text-green-800 border-green-200",
  Indeterminate: "bg-slate-100 text-slate-700 border-slate-200",
};

const SD_COLORS: Record<string, string> = {
  Present: "text-emerald-700 bg-emerald-50 border-emerald-200",
  Implied: "text-amber-700 bg-amber-50 border-amber-200",
  Absent: "text-slate-600 bg-slate-50 border-slate-200",
};

const STATUS_STEPS = [
  { key: "pending", label: "Queued" },
  { key: "running", label: "Extracting PDF" },
  { key: "idca_complete", label: "IDCA Complete" },
  { key: "naa_complete", label: "NAA Complete" },
  { key: "complete", label: "Done" },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function ScoreBar({ value, color }: { value: number; color: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ flex: 1, height: "8px", backgroundColor: "#f1f5f9", borderRadius: "999px", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, borderRadius: "999px" }} className={color} />
      </div>
      <span style={{ fontSize: "11px", fontFamily: "monospace", minWidth: "40px", textAlign: "right" }}>
        {value.toFixed(1)}%
      </span>
    </div>
  );
}

function StatusProgress({ status }: { status: string }) {
  const currentIdx = STATUS_STEPS.findIndex((s) => s.key === status);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap" }}>
      {STATUS_STEPS.map((step, idx) => (
        <div key={step.key} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <div
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              border: `2px solid ${idx <= currentIdx ? "#6366f1" : "#e2e8f0"}`,
              backgroundColor: idx < currentIdx ? "#6366f1" : "#fff",
              boxShadow: idx === currentIdx ? "0 0 0 3px #e0e7ff" : "none",
            }}
          />
          {idx < STATUS_STEPS.length - 1 && (
            <div style={{ width: "24px", height: "2px", backgroundColor: idx < currentIdx ? "#6366f1" : "#e2e8f0" }} />
          )}
        </div>
      ))}
      <span style={{ marginLeft: "8px", fontSize: "14px", color: "#64748b" }}>
        {STATUS_STEPS[currentIdx]?.label ?? status}
      </span>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AMIEPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRef, setExpandedRef] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") {
      setFile(dropped);
      setError(null);
    } else {
      setError("Please upload a PDF file.");
    }
  }, []);

  async function evaluate() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setTask(null);
    if (pollRef.current) clearInterval(pollRef.current);

    try {
      // 1. Get presigned S3 upload URL
      const urlResp = await fetch(`${API_BASE}/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name }),
      });
      if (!urlResp.ok) throw new Error(`Upload URL request failed (${urlResp.status})`);
      const { upload_url, s3_key, bucket } = await urlResp.json();

      // 2. PUT PDF directly to S3
      const uploadResp = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": "application/pdf" },
        body: file,
      });
      if (!uploadResp.ok) throw new Error(`S3 upload failed (${uploadResp.status})`);

      // 3. Create evaluation task
      const taskResp = await fetch(`${API_BASE}/a2a/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ s3_key, bucket }),
      });
      if (!taskResp.ok) throw new Error(`Task creation failed (${taskResp.status})`);
      const taskData: Task = await taskResp.json();
      setTask(taskData);

      // 4. Poll every 4 seconds until complete or error
      pollRef.current = setInterval(async () => {
        try {
          const statusResp = await fetch(`${API_BASE}/a2a/tasks/${taskData.task_id}`);
          if (!statusResp.ok) return;
          const updated: Task = await statusResp.json();
          setTask(updated);
          if (updated.status === "complete" || updated.status === "error") {
            clearInterval(pollRef.current!);
            pollRef.current = null;
            setLoading(false);
          }
        } catch {
          // transient poll error — keep retrying
        }
      }, 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unknown error occurred.");
      setLoading(false);
    }
  }

  const isRunning = loading || (task != null && !["complete", "error"].includes(task.status));
  const refs = task?.aa?.final_reference_table ?? [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50">

      {/* ── Header ── */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">AMIE Software</h1>
            <p className="text-xs text-slate-500">Academic Manuscript IP Evaluator </p>
          </div>
          <span className="text-xs bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full font-semibold">
          </span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-10 space-y-6">

        {/* ── Upload Card ── */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <span className="text-indigo-500"><IconUpload /></span>
            Upload Manuscript
          </h2>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => document.getElementById("file-input")?.click()}
            className={[
              "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors",
              dragging
                ? "border-indigo-400 bg-indigo-50"
                : "border-slate-200 hover:border-indigo-300 hover:bg-slate-50",
            ].join(" ")}
          >
            <input
              id="file-input"
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) { setFile(f); setError(null); }
              }}
            />
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <span className="text-indigo-500"><IconFile /></span>
                <p className="font-semibold text-slate-800 text-sm">{file.name}</p>
                <p className="text-xs text-slate-400">
                  {(file.size / 1024).toFixed(1)} KB · Click to change
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-slate-400">
                <IconUpload />
                <p className="font-medium text-sm">Drop PDF here or click to browse</p>
                <p className="text-xs">Academic manuscripts, preprints, technical reports</p>
              </div>
            )}
          </div>

          {error && (
            <div className="mt-3 flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
              <span className="shrink-0"><IconAlert /></span>
              {error}
            </div>
          )}

          <button
            onClick={evaluate}
            disabled={!file || !!isRunning}
            className="mt-4 w-full py-3 rounded-xl font-semibold text-sm text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {isRunning ? (
              <>
                <span style={{
                  display: "inline-block",
                  width: "16px",
                  height: "16px",
                  border: "2px solid rgba(255,255,255,0.3)",
                  borderTopColor: "#fff",
                  borderRadius: "50%",
                  animation: "spin 0.7s linear infinite",
                }} />
                Evaluating...
              </>
            ) : (
              <>
                <span><IconSearch /></span>
                Evaluate Novelty
              </>
            )}
          </button>

          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>

        {task && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <span className="text-indigo-500"><IconClock /></span>
              Processing
            </h2>
            <StatusProgress status={task.status} />
            <p className="text-xs text-slate-400 mt-3">
              {["complete", "error"].includes(task.status)
                ? "Evaluation complete"
                : "Polling every 4s"}
            </p>
          </div>
        )}

        {/* ── Task Error ── */}
        {task?.status === "error" && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6">
            <h2 className="text-sm font-semibold text-red-700 flex items-center gap-2 mb-2">
              <IconAlert /> Evaluation Failed
            </h2>
            <p className="text-sm text-red-600 font-mono break-all">{task.error}</p>
          </div>
        )}

        {/* ── IDCA ── */}
        {task?.idca && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <span className="text-indigo-500"><IconFile /></span>
              IDCA · Invention Detection
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Status Determination
                </p>
                <span className={`inline-block px-3 py-1.5 rounded-full text-sm font-semibold border ${SD_COLORS[task.idca.sd ?? "Absent"]}`}>
                  {task.idca.sd}
                </span>
              </div>
              <div className="sm:col-span-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Fields Map
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {task.idca.fields_map?.map((f) => (
                    <span key={f} className="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full">
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Structural Synopsis</p>
                <p className="text-sm text-slate-700 leading-relaxed">{task.idca.structural_synopsis}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Source Citation</p>
                <p className="text-sm text-slate-600 italic">{task.idca.source_citation}</p>
              </div>
              {task.idca.reasoning && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Reasoning</p>
                  <p className="text-sm text-slate-500">{task.idca.reasoning}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── NAA ── */}
        {task?.naa && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <span className="text-indigo-500"><IconSearch /></span>
              NAA · Prior Art Search
            </h2>
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">SS Synopsis</p>
                <p className="text-sm text-slate-700">{task.naa.ss_synopsis}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Unified Composite String (UCS)
                </p>
                <p className="text-xs font-mono bg-slate-50 border border-slate-200 rounded-lg p-3 text-slate-600 break-all">
                  {task.naa.ucs}
                </p>
              </div>
              <p className="text-xs text-slate-400">
                {task.naa.references?.length ?? 0} references scored
              </p>
            </div>
          </div>
        )}

        {/* ── AA / Final Report ── */}
        {task?.aa && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
              <span className="text-indigo-500"><IconBarChart /></span>
              Final Report
            </h2>

            <div className="flex items-center gap-2 mb-5">
              <span className="text-emerald-500"><IconCheck /></span>
              <span className="text-xs text-slate-500">Novelty Risk:</span>
              <span className={`px-3 py-1 rounded-full text-xs font-bold border ${RISK_COLORS[task.aa.novelty_risk ?? "Indeterminate"]}`}>
                {task.aa.novelty_risk}
              </span>
            </div>

            {task.aa.executive_summary && (
              <div className="mb-6 bg-slate-50 border border-slate-200 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Executive Summary</p>
                <p className="text-sm text-slate-700 leading-relaxed">{task.aa.executive_summary}</p>
              </div>
            )}

            {refs.length > 0 && (
              <>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                  Reference Manuscripts Sorted By Relevance
                </p>
                <div className="space-y-3">
                  {refs.map((ref, idx) => (
                    <div key={idx} className="border border-slate-200 rounded-xl overflow-hidden">
                      <button
                        onClick={() => setExpandedRef(expandedRef === idx ? null : idx)}
                        className="w-full text-left px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors flex items-start gap-3"
                      >
                        <span className="text-xs font-mono font-bold text-slate-400 mt-0.5 w-5 shrink-0">
                          {idx + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-800 leading-snug">{ref.citation}</p>
                          <div className="mt-2 grid grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs text-slate-400 mb-1">CSS</p>
                              <ScoreBar value={ref.css} color="bg-blue-400" />
                            </div>
                            <div>
                              <p className="text-xs text-slate-400 mb-1">EWSS</p>
                              <ScoreBar value={ref.ewss} color="bg-indigo-500" />
                            </div>
                          </div>
                        </div>
                        <span className="text-slate-400 shrink-0 mt-1">
                          {expandedRef === idx ? <IconChevronUp /> : <IconChevronDown />}
                        </span>
                      </button>

                      {expandedRef === idx && (
                        <div className="px-4 py-4 border-t border-slate-100 space-y-3">
                          <div>
                            <p className="text-xs font-semibold text-slate-400 mb-1">RS Synopsis</p>
                            <p className="text-sm text-slate-700">{ref.rs_synopsis}</p>
                          </div>
                          {ref.notes && (
                            <div>
                              <p className="text-xs font-semibold text-slate-400 mb-1">Notes</p>
                              <p className="text-xs text-slate-500">{ref.notes}</p>
                            </div>
                          )}
                          {ref.url && (
                            <a
                              href={ref.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 text-xs text-indigo-600 hover:underline"
                            >
                              <IconExternalLink /> View source
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}

            {refs.length === 0 && task.idca?.sd !== "Present" && (
              <div className="text-center py-8 text-slate-400 text-sm">
                No prior art searched — Status Determination is <strong>{task.idca?.sd}</strong>.
              </div>
            )}
          </div>
        )}

      </main>
    </div>
  );
}
