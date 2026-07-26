import React, { useState, useEffect } from 'react';
import { Eye, Layers, Monitor, Target, FormInput, Activity, CheckCircle2, AlertCircle } from 'lucide-react';

interface WorldModelInspectorPayload {
  timestamp: number;
  active_app: string;
  window_title: string;
  process_id: number;
  monitors_count: number;
  clipboard_text: string;
  scene_graph_nodes: number;
  buttons_detected: string[];
  textboxes_detected: string[];
  dialogs_detected: string[];
}

export const LivePerceptionVisualizer: React.FC = () => {
  const [data, setData] = useState<WorldModelInspectorPayload | null>(null);

  const getHost = () => typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.hostname : '127.0.0.1';

  useEffect(() => {
    const fetchPerception = async () => {
      try {
        const host = getHost();
        const res = await fetch(`http://${host}:8000/api/v1/debug/world_model_inspector`);
        if (res.ok) {
          setData(await res.json());
        }
      } catch (err) {
        console.error("Failed to fetch perception visualizer data:", err);
      }
    };

    fetchPerception();
    const interval = setInterval(fetchPerception, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-5 rounded-2xl bg-slate-900 border border-cyan-500/30 space-y-4 font-mono text-xs text-slate-100 shadow-xl backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Eye className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-cyan-300 uppercase tracking-wide">
              WHAT JARVIS IS SEEING (LIVE SCENE GRAPH)
            </h3>
            <span className="text-[10px] text-slate-400">
              Win32 UIA control tree perception & active window state
            </span>
          </div>
        </div>

        {data && (
          <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold text-[10px] flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            LIVE PERCEPTION ACTIVE
          </span>
        )}
      </div>

      {data ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Active Window */}
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
            <span className="text-slate-500 text-[10px] block uppercase font-bold flex items-center gap-1.5">
              <Monitor className="w-3.5 h-3.5 text-cyan-400" /> FOREGROUND WINDOW
            </span>
            <span className="text-slate-100 font-bold block truncate">{data.window_title}</span>
            <div className="flex justify-between text-[10px] text-slate-400 pt-1">
              <span>PID: <strong className="text-cyan-300">{data.process_id}</strong></span>
              <span>Monitors: <strong className="text-emerald-400">{data.monitors_count}</strong></span>
            </div>
          </div>

          {/* Detected Buttons */}
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
            <span className="text-slate-500 text-[10px] block uppercase font-bold flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5 text-purple-400" /> DETECTED BUTTONS ({data.buttons_detected.length})
            </span>
            <div className="space-y-1 max-h-24 overflow-y-auto custom-scrollbar">
              {data.buttons_detected.length > 0 ? (
                data.buttons_detected.slice(0, 5).map((btn, idx) => (
                  <span key={idx} className="block text-[11px] px-2 py-1 rounded bg-slate-900 text-purple-300 truncate border border-purple-500/20">
                    {btn}
                  </span>
                ))
              ) : (
                <span className="text-slate-600 italic block py-2 text-center text-[10px]">[No buttons indexed]</span>
              )}
            </div>
          </div>

          {/* Detected Form Textboxes */}
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
            <span className="text-slate-500 text-[10px] block uppercase font-bold flex items-center gap-1.5">
              <FormInput className="w-3.5 h-3.5 text-amber-400" /> TEXT INPUT FIELDS ({data.textboxes_detected.length})
            </span>
            <div className="space-y-1 max-h-24 overflow-y-auto custom-scrollbar">
              {data.textboxes_detected.length > 0 ? (
                data.textboxes_detected.slice(0, 5).map((txt, idx) => (
                  <span key={idx} className="block text-[11px] px-2 py-1 rounded bg-slate-900 text-amber-300 truncate border border-amber-500/20">
                    {txt}
                  </span>
                ))
              ) : (
                <span className="text-slate-600 italic block py-2 text-center text-[10px]">[No text fields indexed]</span>
              )}
            </div>
          </div>
          {/* Workspace Intelligence Card */}
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 md:col-span-3">
            <span className="text-slate-500 text-[10px] block uppercase font-bold flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-emerald-400" /> WORKSPACE INTELLIGENCE & HABIT PREDICTION
            </span>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px] pt-1">
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-slate-500 block text-[9px] font-bold uppercase">ACTIVE PROJECT</span>
                <span className="text-cyan-300 font-bold block truncate">JARVIS Personal AI OS</span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-slate-500 block text-[9px] font-bold uppercase">WORKFLOW CLASSIFICATION</span>
                <span className="text-purple-300 font-bold block truncate">Software Engineering & Coding</span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-slate-500 block text-[9px] font-bold uppercase">NEXT LIKELY ACTION (HABIT PREDICTION)</span>
                <span className="text-emerald-400 font-bold block truncate">Run Unit Verification Tests</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 text-center text-slate-500 italic">Initializing Live Perception Visualizer...</div>
      )}
    </div>
  );
};
