import React, { useState } from 'react';
import { setRoleGlobal } from '../roleStore';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simulated validation delay for premium feel
    setTimeout(() => {
      if (username === 'admin' && password === 'admin123') {
        setRoleGlobal('admin');
      } else if (username === 'viewer' && password === 'viewer123') {
        setRoleGlobal('viewer');
      } else {
        setError('Invalid credentials. Access denied.');
        setLoading(false);
      }
    }, 800);
  };

  const handleQuickViewer = () => {
    setRoleGlobal('viewer');
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-background z-50 animate-in fade-in duration-700 overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/5 blur-[120px] rounded-full" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-500/5 blur-[120px] rounded-full" />

      <div className="w-full max-w-md p-10 rounded-[32px] border border-border bg-card/50 backdrop-blur-xl shadow-[0_32px_64px_-16px_rgba(0,0,0,0.2)] relative overflow-hidden group">
        {/* Animated border line */}
        <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-primary/50 to-transparent animate-pulse" />
        
        <div className="text-center space-y-3 mb-10">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center border border-primary/20 shadow-inner group-hover:scale-110 transition-transform duration-500">
              <span className="text-primary font-black text-3xl">S</span>
            </div>
          </div>
          <h1 className="text-4xl font-black tracking-tighter text-foreground italic">SENTINEL</h1>
          <p className="text-[10px] text-muted-foreground uppercase tracking-[0.3em] font-bold">Secure Fraud Response Workbench</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground ml-1">Terminal Identity</label>
            <input 
              type="text" 
              placeholder="Username" 
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-5 py-4 bg-muted/30 border border-border rounded-2xl text-sm font-medium focus:ring-2 focus:ring-primary/20 focus:border-primary/50 outline-none transition-all placeholder:text-muted-foreground/50"
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground ml-1">Access Cipher</label>
            <input 
              type="password" 
              placeholder="Password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-5 py-4 bg-muted/30 border border-border rounded-2xl text-sm font-medium focus:ring-2 focus:ring-primary/20 focus:border-primary/50 outline-none transition-all placeholder:text-muted-foreground/50"
              required
            />
          </div>

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-[11px] text-red-500 font-bold text-center animate-in slide-in-from-top-2">
              ⚠️ {error}
            </div>
          )}

          <button 
            type="submit"
            disabled={loading}
            className="w-full py-5 rounded-2xl bg-primary text-primary-foreground font-black uppercase tracking-[0.2em] hover:opacity-90 transition-all hover:scale-[1.01] active:scale-[0.99] shadow-2xl shadow-primary/30 disabled:opacity-50 disabled:cursor-wait mt-4"
          >
            {loading ? 'Authenticating...' : 'Establish Secure Link'}
          </button>
        </form>

        <div className="mt-8 pt-8 border-t border-border/50 text-center space-y-4">
          <button 
            onClick={handleQuickViewer}
            className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest hover:text-primary transition-colors"
          >
            Public Viewer Access
          </button>
          <p className="text-[9px] text-muted-foreground/40 font-bold uppercase tracking-widest leading-loose">
            Quantum Encrypted Session • PROD-1.4.2<br/>
            Neural ID Monitoring Active
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
