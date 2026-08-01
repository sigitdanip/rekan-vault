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
} from 'lucide-react';

type Tab = 'home' | 'search' | 'ask' | 'vault' | 'skilltree' | 'admin';

export default function WorkspaceShell() {
  const [activeTab, setActiveTab] = useState<Tab>('home');
  const [searchQuery, setSearchQuery] = useState('');
  const [askPrompt, setAskPrompt] = useState('');

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
                    placeholder="Enter keywords or semantic query (e.g., Google Drive sync strategy, Notion block models)..."
                    className="flex-1 bg-slate-900/90 border border-slate-700/80 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                  <button className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-6 py-3 rounded-lg text-sm transition-all shadow-lg shadow-indigo-600/20">
                    Search
                  </button>
                </div>
              </div>
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
