/**
 * Alert system types — matches backend Pydantic schemas.
 */

// ── Core Types ─────────────────────────────────────────────────────

export type AlertType = "formula" | "drawing";
export type AlertStatus = "active" | "paused" | "triggered" | "expired";
export type AlertFrequency =
  | "once"
  | "once_per_minute"
  | "once_per_bar"
  | "end_of_day";
export type DrawingTrigger =
  | "crosses_above"
  | "crosses_below"
  | "enters"
  | "exits"
  | "enters_or_exits";
export type ChannelType = "in_app" | "telegram" | "web_push";

// ── Drawing Conditions ─────────────────────────────────────────────

export interface DrawingPoint {
  time: number; // Unix seconds
  price: number;
}

export interface TrendlineCondition {
  drawing_type: "trendline";
  trigger_when: "crosses_above" | "crosses_below";
  points: DrawingPoint[];
}

export interface HlineCondition {
  drawing_type: "hline";
  trigger_when: "crosses_above" | "crosses_below";
  price: number;
}

export interface RectangleCondition {
  drawing_type: "rectangle";
  trigger_when: "enters" | "exits" | "enters_or_exits";
  top: number;
  bottom: number;
  left: number;
  right: number;
}

export interface FormulaCondition {
  formula: string;
}

export type TriggerCondition =
  | FormulaCondition
  | TrendlineCondition
  | HlineCondition
  | RectangleCondition;

export interface GuardCondition {
  formula: string;
}

// ── Alert Model ────────────────────────────────────────────────────

export interface Alert {
  id: string;
  user_id: string;
  name: string;
  symbol: string;
  alert_type: AlertType;
  status: AlertStatus;
  trigger_condition: Record<string, unknown>;
  guard_conditions: GuardCondition[];
  frequency: AlertFrequency;
  frequency_interval: number;
  expiry: string | null;
  trigger_count: number;
  last_triggered_at: string | null;
  notification_channels: string[] | null;
  alert_sound: string;
  drawing_id: string | null;
  created_at: string;
  updated_at: string;
}

// ── Alert Create / Update ──────────────────────────────────────────

export interface AlertCreateParams {
  name?: string;
  symbol: string;
  alert_type?: AlertType;
  trigger_condition: Record<string, unknown>;
  guard_conditions?: GuardCondition[];
  frequency?: AlertFrequency;
  frequency_interval?: number;
  expiry?: string | null;
  notification_channels?: string[] | null;
  alert_sound?: string | null;
  drawing_id?: string | null;
}

export interface AlertUpdateParams {
  name?: string;
  trigger_condition?: Record<string, unknown>;
  guard_conditions?: GuardCondition[];
  frequency?: AlertFrequency;
  frequency_interval?: number;
  expiry?: string | null;
  notification_channels?: string[] | null;
  alert_sound?: string | null;
  drawing_id?: string | null;
}

// ── Alert Log ──────────────────────────────────────────────────────

export interface AlertLog {
  id: string;
  alert_id: string;
  user_id: string;
  symbol: string;
  triggered_at: string;
  trigger_value: number | null;
  message: string;
  read: boolean;
}

export interface AlertLogsResponse {
  logs: AlertLog[];
  total: number;
  limit: number;
  offset: number;
}

// ── Notification Channel ───────────────────────────────────────────

export interface NotificationChannel {
  id: string;
  user_id: string;
  channel_type: ChannelType;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationChannelCreate {
  channel_type: ChannelType;
  config?: Record<string, unknown>;
}

// ── WebSocket Alert Messages ───────────────────────────────────────

export interface AlertTriggeredPayload {
  alert_id: string;
  alert_name: string;
  symbol: string;
  trigger_value: number;
  message: string;
  alert_sound: string | null;
  timestamp: string;
}

export interface AlertStatusChangedPayload {
  alert_id: string;
  alert_name: string;
  new_status: AlertStatus;
  timestamp: string;
}
