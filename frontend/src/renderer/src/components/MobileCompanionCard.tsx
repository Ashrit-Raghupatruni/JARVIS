import React, { useState, useEffect } from 'react';
import { Smartphone, QrCode, ShieldCheck, RefreshCw, CheckCircle, SmartphoneNfc, X, Maximize2 } from 'lucide-react';
import { QRPairingModal } from './QRPairingModal';

interface PairingData {
  pairing_session_id: string;
  pairing_code: string;
  server_public_key?: string;
  expires_in_seconds?: number;
  qr_payload?: string;
}

interface DeviceInfo {
  device_id: string;
  friendly_name: string;
  registered_at: number;
  last_active: number;
  trusted: boolean;
  is_online?: boolean;
}

export const MobileCompanionCard: React.FC = () => {
  const [pairingData, setPairingData] = useState<PairingData | null>(null);
  const [trustedDevices, setTrustedDevices] = useState<DeviceInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);

  const getHost = () => typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.hostname : '127.0.0.1';

  const fetchPairingCode = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://${getHost()}:8000/api/v1/mobile/pair/qr/generate`);
      if (res.ok) {
        const data = await res.json();
        setPairingData(data);
      } else {
        const fallbackRes = await fetch(`http://${getHost()}:8000/api/v1/mobile/pair/initiate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_name: "Desktop Terminal Pairing",
            device_id: "desktop_host_01"
          })
        });
        if (fallbackRes.ok) {
          const data = await fallbackRes.json();
          data.qr_payload = `jarvis_pair://${data.pairing_session_id}:${data.pairing_code}`;
          setPairingData(data);
        }
      }
    } catch (err) {
      console.error("Failed to generate mobile pairing PIN/QR:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTrustedDevices = async () => {
    try {
      const res = await fetch(`http://${getHost()}:8000/api/v1/mobile/devices`);
      if (res.ok) {
        const data = await res.json();
        setTrustedDevices(data);
      }
    } catch (err) {
      console.error("Failed to fetch trusted devices:", err);
    }
  };

  useEffect(() => {
    fetchPairingCode();
    fetchTrustedDevices();
    const interval = setInterval(fetchTrustedDevices, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div className="glass rounded-xl p-5 border border-jarvis-accent/20 bg-jarvis-surface/40 backdrop-blur-md">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-jarvis-accent/10 text-jarvis-accent">
              <Smartphone className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-jarvis-text tracking-wide uppercase font-mono">
                ANDROID MOBILE COMPANION
              </h3>
              <p className="text-xs text-jarvis-text-muted">
                Pair your phone with QR Code scan or 6-digit PIN for remote control & security approvals
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowQRModal(true)}
              className="px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-cyan-300 text-xs font-mono font-bold transition flex items-center gap-1.5 shadow-[0_0_10px_rgba(0,229,255,0.2)]"
            >
              <QrCode className="w-3.5 h-3.5 text-cyan-400" />
              Full QR Modal
            </button>

            <button
              onClick={fetchPairingCode}
              disabled={loading}
              className="px-3 py-1.5 rounded-lg bg-jarvis-accent/10 hover:bg-jarvis-accent/20 border border-jarvis-accent/30 text-jarvis-accent text-xs font-mono font-medium transition flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              New PIN
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Section 1: Live QR Code Display */}
          <div className="p-4 rounded-lg bg-jarvis-bg-alt/60 border border-jarvis-accent/15 flex flex-col items-center justify-center relative group">
            <span className="text-xs text-jarvis-text-dim font-mono mb-2 flex items-center gap-1">
              <QrCode className="w-3.5 h-3.5 text-cyan-400" /> SCAN QR CODE TO PAIR
            </span>

            <div 
              onClick={() => setShowQRModal(true)}
              className="cursor-pointer p-2.5 bg-slate-950 border border-cyan-500/30 rounded-xl shadow-lg hover:border-cyan-400 transition-all flex flex-col items-center"
            >
              {/* Scaled Visual QR Matrix */}
              <div className="w-32 h-32 bg-slate-900 p-2 rounded-lg border border-cyan-500/40 flex flex-col justify-between items-center shadow-inner">
                <div className="grid grid-cols-6 gap-1 w-full h-full p-1 bg-slate-950 rounded">
                  {Array.from({ length: 36 }).map((_, i) => (
                    <div
                      key={i}
                      className={`rounded-xs ${
                        i % 2 === 0 || i % 5 === 0 || i % 7 === 0 ? 'bg-cyan-400 shadow-[0_0_4px_rgba(0,229,255,0.6)]' : 'bg-slate-800/40'
                      }`}
                    />
                  ))}
                </div>
              </div>
              <span className="text-[10px] text-cyan-400/80 font-mono mt-1.5 flex items-center gap-1">
                <Maximize2 className="w-2.5 h-2.5" /> Tap to Enlarge
              </span>
            </div>
          </div>

          {/* Section 2: 6-Digit Pairing PIN */}
          <div className="p-4 rounded-lg bg-jarvis-bg-alt/60 border border-jarvis-accent/15 flex flex-col items-center justify-center">
            <span className="text-xs text-jarvis-text-dim font-mono mb-1">PAIRING CODE</span>
            {pairingData ? (
              <div className="text-center">
                <div className="text-4xl font-black text-jarvis-accent font-mono tracking-widest my-2">
                  {pairingData.pairing_code}
                </div>
                <span className="text-[10px] text-jarvis-text-muted block">
                  Enter code in Android app (Expires in 300s)
                </span>
                {pairingData.qr_payload && (
                  <span className="text-[9px] text-slate-500 font-mono block mt-1 truncate max-w-[200px]">
                    {pairingData.qr_payload}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-xs text-jarvis-text-muted">Generating PIN...</span>
            )}
          </div>

          {/* Section 3: Paired Devices List */}
          <div className="p-4 rounded-lg bg-jarvis-bg-alt/60 border border-jarvis-accent/15">
            <span className="text-xs text-jarvis-text-dim font-mono mb-2 block">PAIRED TRUSTED DEVICES</span>
            {trustedDevices.length > 0 ? (
              <div className="space-y-2">
                {trustedDevices.map((dev) => (
                  <div key={dev.device_id} className="flex items-center justify-between p-2 rounded bg-jarvis-surface/60 border border-jarvis-accent/10">
                    <div className="flex items-center space-x-2">
                      <SmartphoneNfc className="w-4 h-4 text-jarvis-accent" />
                      <div>
                        <div className="text-xs font-bold text-jarvis-text">{dev.friendly_name}</div>
                        <div className="text-[10px] text-jarvis-text-muted font-mono">{dev.device_id.slice(0, 12)}...</div>
                      </div>
                    </div>
                    {dev.is_online ? (
                      <span className="inline-flex items-center text-[10px] text-emerald-400 font-bold gap-1 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30">
                        <CheckCircle className="w-3 h-3" /> ONLINE & CONNECTED
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-[10px] text-slate-400 font-medium gap-1 px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
                        DISCONNECTED (PAIRED)
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-jarvis-text-muted italic py-4 text-center">
                No companion devices paired yet. Scan QR or enter code.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* QR Pairing Modal Overlay */}
      <QRPairingModal isOpen={showQRModal} onClose={() => setShowQRModal(false)} />
    </>
  );
};
