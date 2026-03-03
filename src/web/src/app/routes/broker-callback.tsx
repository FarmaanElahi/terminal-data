import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { brokerApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function BrokerCallbackPage() {
  const { providerId = "" } = useParams<{ providerId: string }>();
  const callbackToken = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("code") ?? params.get("request_token");
  }, []);
  const initialError = useMemo(() => {
    if (!providerId) return "Missing broker provider in callback URL.";
    if (!callbackToken) return "Missing authorization token in callback URL.";
    return null;
  }, [providerId, callbackToken]);

  const [status, setStatus] = useState<"loading" | "success" | "error">(
    initialError ? "error" : "loading",
  );
  const [error, setError] = useState<string | null>(initialError);

  useEffect(() => {
    if (!providerId || !callbackToken) {
      return;
    }

    brokerApi
      .exchangeCode(providerId, callbackToken)
      .then(() => {
        setStatus("success");
        if (window.opener) {
          window.opener.postMessage(
            { type: "broker-login-success", provider_id: providerId },
            "*",
          );
        }
        setTimeout(() => window.close(), 1500);
      })
      .catch((err) => {
        const msg =
          err?.response?.data?.detail ?? err?.message ?? "Unknown error";
        setError(msg);
        setStatus("error");
      });
  }, [providerId, callbackToken]);

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
      <div className="w-full max-w-md border border-border bg-card rounded-lg p-6 space-y-3 text-center">
        {status === "loading" && (
          <p className="text-sm text-muted-foreground">Connecting broker…</p>
        )}

        {status === "success" && (
          <>
            <p className="text-sm font-medium text-foreground">Connected successfully</p>
            <p className="text-xs text-muted-foreground">
              This window will close automatically.
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <p className="text-sm font-medium text-destructive">
              Connection failed
            </p>
            <p className="text-xs text-muted-foreground break-words">{error}</p>
            <Button variant="outline" onClick={() => window.close()}>
              Close
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
