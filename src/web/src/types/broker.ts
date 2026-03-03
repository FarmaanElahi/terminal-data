export interface BrokerAccount {
  account_key: string;
  credential_id: string;
  account_id: string | null;
  account_label: string | null;
  account_owner: string | null;
}

export interface BrokerInfo {
  provider_id: string;
  display_name: string;
  markets: string[];
  capabilities: string[];
  connected: boolean;
  login_required: boolean;
  accounts: BrokerAccount[];
  active_account_key: string | null;
}

export interface BrokerStatus {
  provider_id: string;
  connected: boolean;
  login_required: boolean;
}

export interface BrokerDefault {
  capability: string;
  market: string;
  provider_id: string;
}
