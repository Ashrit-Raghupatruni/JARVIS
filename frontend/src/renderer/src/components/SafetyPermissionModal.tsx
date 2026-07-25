import React from 'react';
import { AlertTriangle, ShieldAlert, CheckCircle2, XCircle, Lock } from 'lucide-react';

export interface PermissionRequestPayload {
  request_id: string;
  action: string;
  details: string;
  risk_level: string;
}

interface SafetyPermissionModalProps {
  request: PermissionRequestPayload;
  onApprove: (requestId: string) => void;
  onDeny: (requestId: string) => void;
}

export const SafetyPermissionModal: React.FC<SafetyPermissionModalProps> = ({
  request,
  onApprove,
  onDeny
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md p-6 rounded-2xl bg-slate-900 border border-rose-500/40 shadow-2xl space-y-5">
        {/* Header */}
        <div className="flex items-center space-x-3">
          <div className="p-3 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/40">
            <ShieldAlert className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <span className="text-[10px] font-mono font-bold tracking-widest text-rose-400 uppercase">
              SAFETY INTERLOCK REQUIRING APPROVAL
            </span>
            <h3 className="text-lg font-bold font-mono text-slate-100 uppercase">
              Dangerous Action Requested
            </h3>
          </div>
        </div>

        {/* Action Details */}
        <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs font-mono">
          <div className="flex justify-between items-center text-slate-400">
            <span>ACTION CATEGORY</span>
            <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold uppercase">
              {request.action} ({request.risk_level || 'HIGH'})
            </span>
          </div>

          <div className="pt-2 border-t border-slate-800 space-y-1">
            <span className="text-slate-500 block">TARGET DETAILS:</span>
            <span className="text-slate-200 font-bold block break-all bg-slate-900 p-2 rounded border border-slate-800">
              {request.details}
            </span>
          </div>
        </div>

        {/* Notice */}
        <div className="flex items-center space-x-2 text-[11px] text-amber-300 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20 font-mono">
          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
          <span>JARVIS will not proceed with this action until you explicitly approve it.</span>
        </div>

        {/* Buttons */}
        <div className="grid grid-cols-2 gap-3 pt-2 font-mono text-xs">
          <button
            onClick={() => onDeny(request.request_id)}
            className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold transition flex items-center justify-center gap-2 border border-slate-700"
          >
            <XCircle className="w-4 h-4 text-rose-400" />
            Deny & Cancel
          </button>

          <button
            onClick={() => onApprove(request.request_id)}
            className="w-full py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold transition flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(244,63,94,0.4)]"
          >
            <CheckCircle2 className="w-4 h-4" />
            Approve Execution
          </button>
        </div>
      </div>
    </div>
  );
};
