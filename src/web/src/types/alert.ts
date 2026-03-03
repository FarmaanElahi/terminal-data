export interface Alert {
  uuid: string;
  name: string;
  type: string;
  status: string;
  disabled_reason: string;
  lhs_exchange: string;
  lhs_tradingsymbol: string;
  lhs_attribute: string;
  operator: string;
  rhs_type: string;
  rhs_constant: number | null;
  rhs_attribute: string;
  rhs_exchange: string;
  rhs_tradingsymbol: string;
  alert_count: number;
  provider_id: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface AlertCreateParams {
  provider_id: string;
  name: string;
  type?: string;
  lhs_exchange: string;
  lhs_tradingsymbol: string;
  lhs_attribute?: string;
  operator: string;
  rhs_type?: string;
  rhs_constant?: number;
  rhs_attribute?: string;
  rhs_exchange?: string;
  rhs_tradingsymbol?: string;
}

export interface AlertModifyParams {
  provider_id: string;
  name?: string;
  type?: string;
  lhs_exchange?: string;
  lhs_tradingsymbol?: string;
  lhs_attribute?: string;
  operator?: string;
  rhs_type?: string;
  rhs_constant?: number;
  rhs_attribute?: string;
  rhs_exchange?: string;
  rhs_tradingsymbol?: string;
}

export interface AlertDeleteParams {
  provider_id: string;
  uuids: string[];
}
