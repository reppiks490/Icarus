export type JsonObject = Record<string, unknown>;

export type IcarusAsset = {
  symbol?: string;
  warm?: boolean;
  paused?: boolean;
  position?: number | string | null;
  last?: number | null;
  poll_age?: number | null;
  bar_index?: number;
  trades_total?: number;
  pnl?: number | null;
  equity?: number | null;
  last_error?: string | null;
  [key: string]: unknown;
};

export type PublicStatus = {
  ok?: boolean;
  paused?: boolean;
  all_warm?: boolean;
  preset?: string | null;
  capital?: number | null;
  equity?: number | null;
  assets?: IcarusAsset[];
  [key: string]: unknown;
};

export type SystemAudit = JsonObject & {
  status?: string;
  repository?: string;
  recorded_at?: string;
};

export type DeviceCredentials = {
  baseUrl: string;
  deviceId: string;
  refreshToken: string;
  sessionToken: string;
  sessionExpiresAt: number;
};

export type GatewaySnapshot = {
  cursor: string;
  generated_at: number;
  status?: PublicStatus;
  audit?: SystemAudit;
  briefing?: JsonObject;
  error?: string;
};

export type ChartPayload = {
  symbol?: string;
  tf?: number;
  mintick?: number;
  bars?: number[][];
  forming?: number[] | null;
  overlays?: JsonObject[];
  fills?: JsonObject[];
  [key: string]: unknown;
};

export type TradeRow = {
  id?: string;
  dir?: string;
  qty?: number;
  entry?: number;
  entry_ts?: number;
  exit?: number;
  exit_ts?: number;
  comment?: string;
  profit?: number;
  live?: boolean;
  [key: string]: unknown;
};
