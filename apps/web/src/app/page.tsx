'use client';

import React, { useState } from 'react';
import {
  ShieldCheck,
  Search,
  MessageSquare,
  Vault,
  Compass,
  Settings,
  Database,
  Cpu,
  Layers,
  CheckCircle2,
  Lock,
  Sparkles,
  Zap,
  Activity,
  FileText,
  UserCheck,
  Loader2,
  ExternalLink,
  X,
} from 'lucide-react';

// ponytail: API base hardcoded for pilot — env config deferred to P5.
const SEARCH_API_BASE = 'http://localhost:9002';

// RekanVault search contracts — mirror rekanvault/contracts/evidence.py + context.py.
interface Citation {
  document_id: string;
  version_id: string;
  block_id: string | null;
  title: string;
  uri: string;
  snippet: string;
}

interface EvidenceChunk {
  chunk_id: string;
  document_id: string;
  version_id: string;
  workspace_id: string;
  content: string;
  token_count: number;
  score: number;
  locator: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

interface SearchDiagnostics {
  pipeline: string;
  lexical_hits: number;
  dense_hits: number;
  reranked_count: number;
  latency_ms: number;
}

interface SearchResponse {
  context_pack_id: string;
  query: string;
  evidence_chunks: EvidenceChunk[];
  citations: Citation[];
  token_budget: number;
  created_at: string;
  metadata: {
    diagnostics: SearchDiagnostics;
  };
}

type Tab = 'home' | 'search' | 'ask' | 'vault' | 'skilltree' | 'admin';

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-slate-500 shrink-0">{label}:</dt>
      <dd className="text-slate-300 break-all">{value}</dd>
    </div>
  );
}

export default function WorkspaceShell() {
  const [activeTab, setActiveTab] = useState<Tab>('home');
  const [searchQuery, setSearchQuery] = useState('');
  const [askPrompt, setAskPrompt] = useState('');

  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [inspectedChunk, setInspectedChunk] = useState<EvidenceChunk | null>(null);

  async function handleSearch() {
    const query = searchQuery.trim();
    if (!query || searchLoading) return;
    setSearchLoading(true);
    setSearchError(null);
    try {
      const res = await fetch(`${SEARCH_API_BASE}/api/v1/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) {
        throw new Error(`Search failed: ${res.status} ${res.statusText}`);
      }
      const data: SearchResponse = await res.json();
      setSearchResponse(data);
    } catch (err) {
      setSearchResponse(null);
      setSearchError(err instanceof Error ? err.message : 'Search request failed');
    } finally {
      setSearchLoading(false);
      setHasSearched(true);
    }
  }

  function chunkTitle(chunk: EvidenceChunk): string {
    const t = chunk.metadata['document_title'];
    return typeof t === 'string' && t ? t : 'Untitled Document';
  }

  function chunkSource(chunk: EvidenceChunk): string {
    const src = chunk.metadata['source'];
    if (typeof src === 'string' && src) return src;
    const matchers = chunk.metadata['matchers'];
    if (typeof matchers === 'string' && matchers) return matchers;
    return 'Lexical+Dense';
  }

  function snippet(content: string, max = 300): string {
    return content.length > max ? `${content.slice(0, max)}…` : content;
  }

  function citationForChunk(chunk: EvidenceChunk, citations: Citation[]): Citation | undefined {
    return citations.find((c) => c.document_id === chunk.document_id && c.version_id === chunk.version_id);
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090d16] text-slate-200">
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-slate-800/80 bg-[#0d1322] flex flex-col justify-between p-4">
        <div>
          {/* Logo Brand */}
          <div className="flex items-center gap-3 px-3 py-3 mb-6 border-b border-slate-800/60">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <ShieldCheck className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-white tracking-wide text-base">RekanVault</h1>
              <span className="text-[10px] uppercase font-mono tracking-widest text-indigo-400 font-medium">v0.1.0 Pre-Alpha</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('home')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'home'
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Layers className="h-4 w-4" />
              Home Workspace
            </button>

            <button
              onClick={() => setActiveTab('search')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'search'
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Search className="h-4 w-4" />
              Hybrid Search
            </button>

            <button
              onClick={() => setActiveTab('ask')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'ask'
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <MessageSquare className="h-4 w-4" />
              Grounded Ask
            </button>

            <button
              onClick={() => setActiveTab('vault')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'vault'
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Vault className="h-4 w-4" />
              Document Vault
            </button>

            <button
              onClick={() => setActiveTab('skilltree')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'skilltree'
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Compass className="h-4 w-4" />
              SkillTree Navigation
            </button>

            <button
              onClick={() => setActiveTab('admin')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'admin'
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Settings className="h-4 w-4" />
              System Admin
            </button>
          </nav>
        </div>

        {/* Auth Placeholder & System Status */}
        <div className="space-y-3 pt-4 border-t border-slate-800/60">
          <div className="glass-panel p-3 rounded-lg flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
              <UserCheck className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-200 truncate">Developer Session</p>
              <p className="text-[10px] text-slate-400 flex items-center gap-1 font-mono">
                <Lock className="h-3 w-3 text-slate-500" /> Auth Placeholder
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono px-1">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" /> API Healthy
            </span>
            <span>:8000</span>
          </div>
        </div>
      </aside>

      {/* Main Content Viewport */}
      <main className="flex-1 flex flex-col overflow-hidden bg-gradient-to-br from-[#090d16] via-[#0d1424] to-[#090d16]">
        {/* Top Header */}
        <header className="h-16 border-b border-slate-800/80 px-8 flex items-center justify-between bg-[#0d1322]/50 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono uppercase tracking-widest text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded border border-indigo-500/20">
              Phase 1 Monorepo Active
            </span>
            <h2 className="text-lg font-semibold text-white capitalize">
              {activeTab === 'home' && 'Workspace Dashboard'}
              {activeTab === 'search' && 'Hybrid Lexical + Vector Search'}
              {activeTab === 'ask' && 'Grounded RAG Assistant'}
              {activeTab === 'vault' && 'Sources & Documents'}
              {activeTab === 'skilltree' && 'Skill Graph & Knowledge Growth'}
              {activeTab === 'admin' && 'System Configuration & Health'}
            </h2>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
            <span className="flex items-center gap-1.5">
              <Database className="h-3.5 w-3.5 text-indigo-400" /> Drive & Notion Connectors
            </span>
            <span className="flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-violet-400" /> FastAPI + Worker
            </span>
          </div>
        </header>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
          {activeTab === 'home' && (
            <div className="space-y-6">
              {/* Stat Cards Grid */}
              <div className="grid grid-[#090d16] grid-cols-4 gap-4">
                <div className="glass-panel p-5 rounded-xl border border-slate-800">
                  <div className="flex items-center justify-between text-slate-400 mb-2">
                    <span className="text-xs font-medium uppercase tracking-wider">Connectors</span>
                    <Zap className="h-4 w-4 text-amber-400" />
                  </div>
                  <div className="text-2xl font-bold text-white">2 Active</div>
                  <p className="text-xs text-slate-400 mt-1">Google Drive & Notion Ready</p>
                </div>

                <div className="glass-panel p-5 rounded-xl border border-slate-800">
                  <div className="flex items-center justify-between text-slate-400 mb-2">
                    <span className="text-xs font-medium uppercase tracking-wider">Test Baseline</span>
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div className="text-2xl font-bold text-white">29 Passed</div>
                  <p className="text-xs text-slate-400 mt-1">Contract & Connector Suites</p>
                </div>

                <div className="glass-panel p-5 rounded-xl border border-slate-800">
                  <div className="flex items-center justify-between text-slate-400 mb-2">
                    <span className="text-xs font-medium uppercase tracking-wider">API Health</span>
                    <Activity className="h-4 w-4 text-indigo-400" />
                  </div>
                  <div className="text-2xl font-bold text-emerald-400">ONLINE</div>
                  <p className="text-xs text-slate-400 mt-1">GET /health & /version</p>
                </div>

                <div className="glass-panel p-5 rounded-xl border border-slate-800">
                  <div className="flex items-center justify-between text-slate-400 mb-2">
                    <span className="text-xs font-medium uppercase tracking-wider">Architecture</span>
                    <Sparkles className="h-4 w-4 text-violet-400" />
                  </div>
                  <div className="text-2xl font-bold text-white">Modular</div>
                  <p className="text-xs text-slate-400 mt-1">Monorepo Python + Next.js</p>
                </div>
              </div>

              {/* Monorepo Consolidation Status Banner */}
              <div className="glass-panel p-6 rounded-xl border border-indigo-500/30 bg-indigo-950/20 relative overflow-hidden">
                <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-indigo-500/10 to-transparent pointer-events-none" />
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-lg bg-indigo-600/20 text-indigo-300 border border-indigo-500/40">
                    <ShieldCheck className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-white">Phase 1 Monorepo Consolidation Verified</h3>
                    <p className="text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
                      Unified Python package <code className="text-indigo-300 font-mono">rekanvault</code>, FastAPI backend <code className="text-indigo-300 font-mono">apps/api</code>, worker daemon <code className="text-indigo-300 font-mono">apps/worker</code>, contract exports <code className="text-indigo-300 font-mono">packages/contracts</code>, and Next.js Web Shell <code className="text-indigo-300 font-mono">apps/web</code> are integrated.
                    </p>
                  </div>
                </div>
              </div>

              {/* Quick Actions & Recent Architecture Notes */}
              <div className="grid grid-cols-2 gap-6">
                <div className="glass-panel p-6 rounded-xl border border-slate-800 space-y-4">
                  <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <FileText className="h-4 w-4 text-indigo-400" /> Canonical Domain Modules
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300">rekanvault.contracts</div>
                    <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300">rekanvault.sources</div>
                    <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300">rekanvault.ingestion</div>
                    <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300">rekanvault.evidence</div>
                    <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300">rekanvault.memory</div>
                    <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300">rekanvault.graph</div>
                  </div>
                </div>

                <div className="glass-panel p-6 rounded-xl border border-slate-800 space-y-4">
                  <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-emerald-400" /> System Contracts & Redaction
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Canonical Pydantic v2 domain schemas guarantee typed error envelopes, correlation IDs, secret redaction, and reproducible OpenAPI 3.1 & JSON schema generation.
                  </p>
                  <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px] font-mono text-emerald-400">
                    GET /health {"->"} &#123;"status": "ok", "version": "0.1.0", "component": "rekanvault-api"&#125;
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'search' && (
            <div className="space-y-6">
              <div className="glass-panel p-6 rounded-xl border border-slate-800 space-y-4">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-400">Search Workspace Documents & Notes</label>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }}
                    placeholder="Enter keywords or semantic query (e.g., Google Drive sync strategy, Notion block models)..."
                    className="flex-1 bg-slate-900/90 border border-slate-700/80 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    onClick={handleSearch}
                    disabled={searchLoading || !searchQuery.trim()}
                    className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-6 py-3 rounded-lg text-sm transition-all shadow-lg shadow-indigo-600/20 flex items-center gap-2"
                  >
                    {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    Search
                  </button>
                </div>
                {searchError && (
                  <p className="text-sm text-red-400 font-mono">⚠ {searchError}</p>
                )}
              </div>

              {searchLoading && (
                <div className="glass-panel p-8 rounded-xl border border-slate-800 flex items-center justify-center gap-3 text-slate-400 text-sm">
                  <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
                  Running hybrid retrieval pipeline…
                </div>
              )}

              {!searchLoading && searchResponse && (
                <>
                  {searchResponse.metadata?.diagnostics && (
                    <div className="glass-panel px-5 py-3 rounded-xl border border-slate-800 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs font-mono text-slate-400">
                      <span className="text-indigo-300 font-semibold">Pipeline: {searchResponse.metadata.diagnostics.pipeline}</span>
                      <span>Lexical: <span className="text-slate-200">{searchResponse.metadata.diagnostics.lexical_hits}</span></span>
                      <span>Dense: <span className="text-slate-200">{searchResponse.metadata.diagnostics.dense_hits}</span></span>
                      <span>Reranked: <span className="text-slate-200">{searchResponse.metadata.diagnostics.reranked_count}</span></span>
                      <span>{searchResponse.metadata.diagnostics.latency_ms}ms</span>
                      <span className="ml-auto text-slate-500">{searchResponse.evidence_chunks.length} chunks · budget {searchResponse.token_budget}</span>
                    </div>
                  )}

                  {searchResponse.evidence_chunks.length === 0 && (
                    <div className="glass-panel p-8 rounded-xl border border-slate-800 text-center">
                      <FileText className="h-8 w-8 text-slate-600 mx-auto mb-3" />
                      <p className="text-sm font-semibold text-slate-300">No evidence found in corpus</p>
                      <p className="text-xs text-slate-500 mt-1">The retrieval pipeline returned no chunks for this query.</p>
                    </div>
                  )}

                  {searchResponse.evidence_chunks.length > 0 && (
                    <div className="space-y-3">
                      {searchResponse.evidence_chunks.map((chunk, idx) => {
                        const citation = citationForChunk(chunk, searchResponse.citations);
                        return (
                          <button
                            key={chunk.chunk_id}
                            onClick={() => setInspectedChunk(chunk)}
                            className="glass-panel-interactive w-full text-left p-5 rounded-xl border border-slate-800 hover:border-indigo-500/40 transition-all cursor-pointer"
                          >
                            <div className="flex items-start justify-between gap-4 mb-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="text-[10px] font-mono text-slate-500 shrink-0">#{idx + 1}</span>
                                <h4 className="text-sm font-semibold text-white truncate">{chunkTitle(chunk)}</h4>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <span className="text-[11px] font-mono font-semibold text-indigo-300 bg-indigo-500/15 border border-indigo-500/30 px-2 py-0.5 rounded-full">
                                  {chunk.score.toFixed(2)}
                                </span>
                                <span className="text-[10px] font-mono text-slate-400 bg-slate-800/80 border border-slate-700 px-2 py-0.5 rounded-full uppercase tracking-wide">
                                  {chunkSource(chunk)}
                                </span>
                              </div>
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed line-clamp-3">
                              {snippet(chunk.content)}
                            </p>
                            <div className="flex items-center gap-3 mt-3 text-[10px] font-mono text-slate-500">
                              <span>{chunk.token_count} tokens</span>
                              <span className="truncate">doc: {chunk.document_id.slice(0, 8)}…</span>
                              {citation && (
                                <span className="flex items-center gap-1 text-emerald-400/70 ml-auto">
                                  <ExternalLink className="h-3 w-3" /> citation
                                </span>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </>
              )}

              {!searchLoading && !searchResponse && hasSearched && !searchError && (
                <div className="glass-panel p-8 rounded-xl border border-slate-800 text-center text-sm text-slate-400">
                  No response from search service.
                </div>
              )}

              {!searchLoading && !hasSearched && (
                <div className="glass-panel p-8 rounded-xl border border-slate-800 text-center">
                  <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
                  <p className="text-sm text-slate-400">Enter a query above to run the hybrid lexical + dense retrieval pipeline.</p>
                </div>
              )}

              {inspectedChunk && (
                <div className="fixed inset-0 z-50 flex justify-end">
                  <div
                    className="absolute inset-0 bg-black/50 backdrop-blur-sm"
                    onClick={() => setInspectedChunk(null)}
                  />
                  <aside className="relative w-full max-w-xl h-full bg-[#0d1322] border-l border-slate-800 shadow-2xl flex flex-col">
                    <div className="flex items-center justify-between px-5 h-14 border-b border-slate-800/80 bg-[#0d1322]/80 backdrop-blur-md shrink-0">
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="h-4 w-4 text-indigo-400 shrink-0" />
                        <h3 className="text-sm font-semibold text-white truncate">{chunkTitle(inspectedChunk)}</h3>
                      </div>
                      <button
                        onClick={() => setInspectedChunk(null)}
                        className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800/60 transition-colors shrink-0"
                        aria-label="Close inspector"
                      >
                        <X className="h-5 w-5" />
                      </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-5 space-y-5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-mono font-semibold text-indigo-300 bg-indigo-500/15 border border-indigo-500/30 px-2.5 py-1 rounded-full">
                          score {inspectedChunk.score.toFixed(4)}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-800/80 border border-slate-700 px-2.5 py-1 rounded-full uppercase tracking-wide">
                          {chunkSource(inspectedChunk)}
                        </span>
                        <span className="text-[10px] font-mono text-slate-500">{inspectedChunk.token_count} tokens</span>
                      </div>

                      <div>
                        <h4 className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Chunk Content</h4>
                        <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap bg-slate-900/60 border border-slate-800 rounded-lg p-4 max-h-96 overflow-y-auto font-mono">
                          {inspectedChunk.content}
                        </div>
                      </div>

                      <div>
                        <h4 className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Identity</h4>
                        <dl className="text-xs font-mono space-y-1.5">
                          <DataRow label="chunk_id" value={inspectedChunk.chunk_id} />
                          <DataRow label="document_id" value={inspectedChunk.document_id} />
                          <DataRow label="version_id" value={inspectedChunk.version_id} />
                          <DataRow label="workspace_id" value={inspectedChunk.workspace_id} />
                        </dl>
                      </div>

                      {Object.keys(inspectedChunk.locator).length > 0 && (
                        <div>
                          <h4 className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Locator</h4>
                          <pre className="text-xs font-mono text-slate-300 bg-slate-900/60 border border-slate-800 rounded-lg p-3 overflow-x-auto">
{JSON.stringify(inspectedChunk.locator, null, 2)}
                          </pre>
                        </div>
                      )}

                      {Object.keys(inspectedChunk.metadata).length > 0 && (
                        <div>
                          <h4 className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Metadata</h4>
                          <pre className="text-xs font-mono text-slate-300 bg-slate-900/60 border border-slate-800 rounded-lg p-3 overflow-x-auto">
{JSON.stringify(inspectedChunk.metadata, null, 2)}
                          </pre>
                        </div>
                      )}

                      {(() => {
                        const citation = searchResponse
                          ? citationForChunk(inspectedChunk, searchResponse.citations)
                          : undefined;
                        if (!citation) return null;
                        return (
                          <div>
                            <h4 className="text-[10px] font-mono uppercase tracking-widest text-emerald-400/80 mb-2">Citation</h4>
                            <dl className="text-xs font-mono space-y-1.5">
                              <DataRow label="title" value={citation.title} />
                              <DataRow label="block_id" value={citation.block_id ?? '—'} />
                              <DataRow label="uri" value={citation.uri} />
                              <div>
                                <dt className="text-slate-500 inline">snippet: </dt>
                                <dd className="text-slate-300 inline">{citation.snippet}</dd>
                              </div>
                            </dl>
                            <a
                              href={citation.uri}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 mt-3 text-xs text-indigo-300 hover:text-indigo-200 font-mono"
                            >
                              <ExternalLink className="h-3.5 w-3.5" /> open source
                            </a>
                          </div>
                        );
                      })()}
                    </div>
                  </aside>
                </div>
              )}
            </div>
          )}

          {activeTab === 'ask' && (
            <div className="space-y-6">
              <div className="glass-panel p-6 rounded-xl border border-slate-800 space-y-4">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-400">Ask Grounded Question</label>
                <textarea
                  value={askPrompt}
                  onChange={(e) => setAskPrompt(e.target.value)}
                  placeholder="Ask a question about your knowledge base with citation validation..."
                  rows={4}
                  className="w-full bg-slate-900/90 border border-slate-700/80 rounded-lg p-4 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
                <div className="flex justify-end">
                  <button className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-6 py-2.5 rounded-lg text-sm transition-all">
                    Generate Answer
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'vault' && (
            <div className="glass-panel p-6 rounded-xl border border-slate-800">
              <h3 className="text-sm font-semibold text-white mb-4">Connected Knowledge Sources</h3>
              <p className="text-xs text-slate-400">Google Drive and Notion connectors configured with provider-neutral document projection.</p>
            </div>
          )}

          {activeTab === 'skilltree' && (
            <div className="glass-panel p-6 rounded-xl border border-slate-800">
              <h3 className="text-sm font-semibold text-white mb-4">SkillTree Progress Graph</h3>
              <p className="text-xs text-slate-400">Evidence-backed skill acquisition and domain topic mappings.</p>
            </div>
          )}

          {activeTab === 'admin' && (
            <div className="glass-panel p-6 rounded-xl border border-slate-800">
              <h3 className="text-sm font-semibold text-white mb-4">System Administration & Logs</h3>
              <p className="text-xs text-slate-400">Configure logging levels, env variables, and worker shutdown grace timers.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
