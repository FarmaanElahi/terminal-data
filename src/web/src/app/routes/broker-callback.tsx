import { useEffect, useState } from "react";
import { brokerApi } from "@/lib/api";

export function UpstoxCallbackPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");

    if (!code) {
      setError("Missing authorization code in callback URL.");
      setStatus("error");
      return;
    }

    brokerApi
      .exchangeUpstoxCode(code)
      .then(() => {
        setStatus("success");
        // Notify the opener window and close the popup
        if (window.opener) {
          window.opener.postMessage({ type: "upstox-login-success" }, "*");
        }
        setTimeout(() => window.close(), 1500);
      })
      .catch((err) => {
        const msg =
          err?.response?.data?.detail ?? err?.message ?? "Unknown error";
        setError(msg);
        setStatus("error");
      });
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        gap: "12px",
        fontFamily: "sans-serif",
      }}
    >
      {status === "loading" && <p>Connecting to Upstox…</p>}
      {status === "success" && (
        <>
          <p style={{ color: "green", fontWeight: 600 }}>
            Connected successfully!
          </p>
          <p style={{ fontSize: "0.875rem", color: "#666" }}>
            This window will close automatically.
          </p>
        </>
      )}
      {status === "error" && (
        <>
          <p style={{ color: "red", fontWeight: 600 }}>Connection failed</p>
          <p style={{ fontSize: "0.875rem", color: "#666" }}>{error}</p>
          <button onClick={() => window.close()}>Close</button>
        </>
      )}
    </div>
  );
}
