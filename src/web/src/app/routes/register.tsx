import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";

export function RegisterPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const register = useAuthStore((s) => s.register);
  const isLoading = useAuthStore((s) => s.isLoading);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 4) {
      setError("Password must be at least 4 characters.");
      return;
    }

    try {
      await register(username, password);
      navigate("/screener");
    } catch {
      setError("Registration failed. Username may already exist.");
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-background p-8"
      style={{
        backgroundImage:
          "radial-gradient(oklch(0.3 0.01 250 / 0.35) 1px, transparent 1px)",
        backgroundSize: "24px 24px",
      }}
    >
      <div className="w-full max-w-sm space-y-8">
        {/* Logo area */}
        <div className="space-y-1">
          <div className="font-mono text-primary text-4xl font-bold tracking-tight leading-none">
            TERMINAL
            <span className="animate-pulse ml-0.5 text-primary/80">_</span>
          </div>
          <div className="text-xs font-mono text-muted-foreground tracking-[0.2em] uppercase pt-1">
            Market Intelligence System
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <p className="text-destructive font-mono text-xs">{error}</p>
          )}

          <div className="space-y-1">
            <label
              htmlFor="username"
              className="block text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              autoFocus
              className="w-full bg-transparent border-0 border-b border-border font-mono text-sm text-foreground px-0 py-1.5 outline-none focus:border-primary transition-colors placeholder:text-muted-foreground/40"
              placeholder="choose a username"
            />
          </div>

          <div className="space-y-1">
            <label
              htmlFor="password"
              className="block text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full bg-transparent border-0 border-b border-border font-mono text-sm text-foreground px-0 py-1.5 outline-none focus:border-primary transition-colors placeholder:text-muted-foreground/40"
              placeholder="create a password"
            />
          </div>

          <div className="space-y-1">
            <label
              htmlFor="confirmPassword"
              className="block text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]"
            >
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full bg-transparent border-0 border-b border-border font-mono text-sm text-foreground px-0 py-1.5 outline-none focus:border-primary transition-colors placeholder:text-muted-foreground/40"
              placeholder="confirm password"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-primary text-primary-foreground font-mono text-xs tracking-[0.15em] uppercase py-2.5 rounded-none disabled:opacity-50 hover:bg-primary/90 transition-colors mt-2"
          >
            {isLoading ? "Creating account..." : "Create account →"}
          </button>
        </form>

        <p className="font-mono text-xs text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
