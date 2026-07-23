import React, { useState, useEffect } from 'react';
import { Smartphone, QrCode, ShieldCheck, RefreshCw, CheckCircle, SmartphoneNfc } from 'lucide-react';

interface PairingData {
  pairing_session_id: string;
  pairing_code: string;
  server_public_key: string;
  expires_in_seconds: number;
}

interface DeviceInfo {
  device_id: string;
  friendly_name: string;
  registered_at: number;
  last_active: number;
  trusted: boolean;
}

export const MobileCompanionCard: React.FC = () => {
  const [pairingData, setPairingData] = useState<PairingData | null>(null);
  const [trustedDevices, setTrustedDevices] = useState<DeviceInfo[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchPairingCode = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/mobile/pair/initiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_name: "Desktop Terminal Pairing",
          device_id: "desktop_host_01"
        })
      });
      if (res.ok) {
        const data = await res.json();
        setPairingData(data);
      }
    } catch (err) {
      console.error("Failed to generate mobile pairing PIN:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTrustedDevices = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/mobile/devices');
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
    const interval = setInterval(fetchTrustedDevices, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
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
              Pair your phone for remote control & security gatekeeper approvals
            </p>
          </div>
        </div>
        <button
          onClick={fetchPairingCode}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg bg-jarvis-accent/10 hover:bg-jarvis-accent/20 border border-jarvis-accent/30 text-jarvis-accent text-xs font-mono font-medium transition flex items-center gap-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          New PIN
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Pairing Code Panel */}
        <div className="p-4 rounded-lg bg-jarvis-bg-alt/60 border border-jarvis-accent/15 flex flex-col items-center justify-center">
          <span className="text-xs text-jarvis-text-dim font-mono mb-1">PAIRING CODE</span>
          {pairingData ? (
            <div className="text-center">
              <div className="text-3xl font-black text-jarvis-accent font-mono tracking-widest my-1">
                {pairingData.pairing_code}
              </div>
              <span className="text-[10px] text-jarvis-text-muted">
                Enter code in Android app (Expires in {pairingData.expires_in_seconds}s)
              </span>
            </div>
          ) : (
            <span className="text-xs text-jarvis-text-muted">Generating PIN...</span>
          )}
        </div>

        {/* Paired Devices List */}
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
                  <span className="inline-flex items-center text-[10px] text-green-400 font-bold gap-1">
                    <CheckCircle className="w-3 h-3" /> PAIRED
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-jarvis-text-muted italic py-3 text-center">
              No companion devices paired yet. Scan QR or enter code above.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
