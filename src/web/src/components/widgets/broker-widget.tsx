import { useMemo } from "react";
import { Link2, CheckCircle2, AlertCircle, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { WidgetProps } from "@/types/layout";
import { useBrokers } from "@/hooks/use-brokers";
import { toast } from "sonner";

function comboKey(capability: string, market: string): string {
  return `${capability}:${market}`;
}

export function BrokerWidget(props: WidgetProps) {
  void props;
  const {
    data: brokers = [],
    isLoading,
    isFetching,
    refetch,
    openLogin,
    defaults,
    setDefault,
    isSettingDefault,
    removeAccount,
    isRemovingAccount,
  } = useBrokers();

  const overlapCombos = useMemo(() => {
    const providersByCombo = new Map<string, string[]>();

    for (const broker of brokers) {
      for (const capability of broker.capabilities) {
        for (const market of broker.markets) {
          const key = comboKey(capability, market);
          const existing = providersByCombo.get(key) ?? [];
          providersByCombo.set(key, [...existing, broker.provider_id]);
        }
      }
    }

    return providersByCombo;
  }, [brokers]);

  const defaultsMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of defaults) {
      map.set(comboKey(item.capability, item.market), item.provider_id);
    }
    return map;
  }, [defaults]);

  const setAsDefault = async (
    capability: string,
    market: string,
    providerId: string,
  ) => {
    try {
      await setDefault({ capability, market, provider_id: providerId });
      toast.success("Default broker updated");
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        "Failed to set default broker";
      toast.error(message);
    }
  };

  const handleRemoveAccount = async (
    providerId: string,
    credentialId: string,
  ) => {
    const confirmed = window.confirm(
      "Remove this broker account? This will disconnect it from this user.",
    );
    if (!confirmed) return;
    try {
      await removeAccount({ providerId, credentialId });
      toast.success("Broker account removed");
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        "Failed to remove broker account";
      toast.error(message);
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
        Loading brokers...
      </div>
    );
  }

  if (brokers.length === 0) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="w-full max-w-sm rounded-md border border-border bg-card/80 p-4 text-center space-y-3">
          <div className="flex items-center justify-center">
            <Link2 className="w-6 h-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">No Broker Providers Available</p>
          <p className="text-xs text-muted-foreground">
            This server is not exposing any configured broker integrations.
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="gap-1"
          >
            <Plus className="w-3 h-3" />
            Refresh Providers
          </Button>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-3 space-y-3">
        <div className="rounded-md border border-border bg-card/60 p-2">
          <p className="text-[11px] text-muted-foreground mb-2">
            Add Broker Account
          </p>
          <div className="flex flex-wrap gap-2">
            {brokers.map((broker) => (
              <Button
                key={`add-${broker.provider_id}`}
                size="sm"
                variant="outline"
                onClick={() => openLogin(broker.provider_id)}
                className="gap-1"
              >
                <Plus className="w-3 h-3" />
                {broker.display_name}
              </Button>
            ))}
          </div>
        </div>

        {brokers.map((broker) => {
          const accounts = broker.accounts ?? [];
          const activeAccountKey = broker.active_account_key ?? null;

          return (
            <div
              key={broker.provider_id}
              className="rounded-md border border-border bg-card/80 p-3 space-y-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium truncate">{broker.display_name}</p>
                    {broker.connected ? (
                      <Badge variant="secondary" className="gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Connected
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="gap-1">
                        <AlertCircle className="w-3 h-3" /> Disconnected
                      </Badge>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground font-mono mt-1">
                    {broker.provider_id}
                  </p>
                </div>

                <Button
                  size="sm"
                  onClick={() => openLogin(broker.provider_id)}
                  className="shrink-0 gap-1"
                >
                  <Plus className="w-3 h-3" />
                  Add Account
                </Button>
              </div>

              <div className="space-y-2">
                <div className="flex flex-wrap gap-1">
                  {broker.markets.map((market) => (
                    <Badge key={`${broker.provider_id}-${market}`} variant="outline">
                      {market}
                    </Badge>
                  ))}
                </div>
                <div className="flex flex-wrap gap-1">
                  {broker.capabilities.map((capability) => (
                    <Badge
                      key={`${broker.provider_id}-${capability}`}
                      variant="secondary"
                    >
                      {capability}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5">
                <p className="text-[11px] text-muted-foreground">Accounts</p>
                {accounts.length === 0 ? (
                  <div className="rounded border border-border/60 px-2 py-2 text-[11px] text-muted-foreground flex items-center justify-between gap-2">
                    <span>No accounts connected yet</span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 px-2 text-[10px]"
                      onClick={() => openLogin(broker.provider_id)}
                    >
                      Connect
                    </Button>
                  </div>
                ) : (
                  accounts.map((account) => {
                    const accountTitle =
                      account.account_label ??
                      account.account_id ??
                      account.credential_id;
                    const owner = account.account_owner ?? "Unknown Owner";
                    const isActive = activeAccountKey === account.account_key;

                    return (
                      <div
                        key={account.account_key}
                        className="flex items-center justify-between gap-2 rounded border border-border/60 px-2 py-1"
                      >
                        <div className="min-w-0">
                          <p className="text-[11px] text-foreground truncate">
                            {accountTitle}
                          </p>
                          <p className="text-[10px] text-muted-foreground truncate">
                            Owner: {owner}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {isActive && (
                            <Badge variant="secondary" className="shrink-0">
                              Active
                            </Badge>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                            disabled={isRemovingAccount}
                            onClick={() =>
                              handleRemoveAccount(
                                broker.provider_id,
                                account.credential_id,
                              )
                            }
                            title="Remove account"
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="space-y-1.5">
                {broker.capabilities.flatMap((capability) =>
                  broker.markets
                    .map((market) => ({ capability, market }))
                    .filter(({ capability: c, market: m }) => {
                      const providers = overlapCombos.get(comboKey(c, m)) ?? [];
                      return providers.length > 1;
                    })
                    .map(({ capability: c, market: m }) => {
                      const key = comboKey(c, m);
                      const isDefault = defaultsMap.get(key) === broker.provider_id;
                      return (
                        <div
                          key={`${broker.provider_id}-${key}`}
                          className="flex items-center justify-between gap-2 rounded border border-border/60 px-2 py-1"
                        >
                          <p className="text-[11px] text-muted-foreground truncate">
                            {c} / {m}
                          </p>
                          <Button
                            size="sm"
                            variant={isDefault ? "secondary" : "outline"}
                            disabled={isSettingDefault || !broker.connected}
                            onClick={() => setAsDefault(c, m, broker.provider_id)}
                          >
                            {isDefault ? "Default" : "Set Default"}
                          </Button>
                        </div>
                      );
                    }),
                )}
              </div>
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}
