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

export type ConnectionSettings = {
  baseUrl: string;
  token: string;
};

export type SystemAudit = JsonObject & {
  status?: string;
  repository?: string;
  recorded_at?: string;
};
