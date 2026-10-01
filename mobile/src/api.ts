import type {
  ChartPayload,
  DeviceCredentials,
  GatewaySnapshot,
  JsonObject,
  TradeRow,
} from './types';

export class IcarusApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = 'IcarusApiError';
  }
}

function normalizeBaseUrl(input: string): string {
  const value = input.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//i.test(value)) {
    throw new IcarusApiError('Gateway URL must start with https:// or http://');
  }
  return value;
}

type PairResponse = {
  device_id: string;
  refresh_token: string;
  session_token: string;
  session_expires_at: number;
};

async function requestJson<T>(
  baseUrl: string,
  path: string,
  options: {
    method?: string;
    body?: unknown;
    token?: string;
    signal?: AbortSignal;
    allow204?: boolean;
  } = {},
): Promise<T | null> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.token) headers.Authorization = 'Bearer ' + options.token;
  const response = await fetch(baseUrl + path, {
    method: options.method || 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: 'no-store',
    signal: options.signal,
  });
  if (response.status === 204 && options.allow204) return null;
  const text = await response.text();
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    throw new IcarusApiError('ICARUS gateway returned non-JSON data', response.status);
  }
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
      ? String((payload as { detail?: unknown }).detail || '')
      : '';
    throw new IcarusApiError(detail || 'ICARUS gateway request failed', response.status);
  }
  return payload as T;
}

export class IcarusClient {
  private credentials: DeviceCredentials;
  private refreshPromise: Promise<void> | null = null;

  constructor(
    credentials: DeviceCredentials,
    private readonly onCredentials?: (next: DeviceCredentials) => void | Promise<void>,
  ) {
    this.credentials = { ...credentials, baseUrl: normalizeBaseUrl(credentials.baseUrl) };
  }

  get baseUrl(): string {
    return this.credentials.baseUrl;
  }

  static async health(baseUrl: string): Promise<JsonObject> {
    const normalized = normalizeBaseUrl(baseUrl);
    const value = await requestJson<JsonObject>(normalized, '/healthz');
    return value || {};
  }

  static async pair(baseUrl: string, deviceName: string, pairingSecret: string): Promise<DeviceCredentials> {
    const normalized = normalizeBaseUrl(baseUrl);
    await IcarusClient.health(normalized);
    const value = await requestJson<PairResponse>(normalized, '/v1/pair', {
      method: 'POST',
      body: {
        device_name: deviceName.trim() || 'ICARUS Mobile',
        pairing_secret: pairingSecret,
      },
    });
    if (!value) throw new IcarusApiError('Gateway returned an empty pairing response');
    return {
      baseUrl: normalized,
      deviceId: value.device_id,
      refreshToken: value.refresh_token,
      sessionToken: value.session_token,
      sessionExpiresAt: value.session_expires_at,
    };
  }

  private async persist(next: DeviceCredentials): Promise<void> {
    this.credentials = next;
    await this.onCredentials?.(next);
  }

  private async refreshSession(): Promise<void> {
    if (this.refreshPromise) return this.refreshPromise;
    this.refreshPromise = (async () => {
      const value = await requestJson<PairResponse>(this.baseUrl, '/v1/session', {
        method: 'POST',
        body: {
          device_id: this.credentials.deviceId,
          refresh_token: this.credentials.refreshToken,
        },
      });
      if (!value) throw new IcarusApiError('Gateway returned an empty refresh response');
      await this.persist({
        ...this.credentials,
        deviceId: value.device_id,
        refreshToken: value.refresh_token,
        sessionToken: value.session_token,
        sessionExpiresAt: value.session_expires_at,
      });
    })();
    try {
      await this.refreshPromise;
    } finally {
      this.refreshPromise = null;
    }
  }

  private async ensureSession(): Promise<void> {
    if (this.credentials.sessionExpiresAt > Date.now() / 1000 + 45) return;
    await this.refreshSession();
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    await this.ensureSession();
    try {
      const value = await requestJson<T>(this.baseUrl, path, {
        method: 'POST',
        body,
        token: this.credentials.sessionToken,
      });
      return value as T;
    } catch (error) {
      if (error instanceof IcarusApiError && error.status === 401) {
        await this.refreshSession();
        const value = await requestJson<T>(this.baseUrl, path, {
          method: 'POST',
          body,
          token: this.credentials.sessionToken,
        });
        return value as T;
      }
      throw error;
    }
  }

  private async get<T>(path: string, signal?: AbortSignal, allow204 = false): Promise<T | null> {
    await this.ensureSession();
    try {
      return await requestJson<T>(this.baseUrl, path, {
        token: this.credentials.sessionToken,
        signal,
        allow204,
      });
    } catch (error) {
      if (error instanceof IcarusApiError && error.status === 401) {
        await this.refreshSession();
        return requestJson<T>(this.baseUrl, path, {
          token: this.credentials.sessionToken,
          signal,
          allow204,
        });
      }
      throw error;
    }
  }

  snapshot(signal?: AbortSignal): Promise<GatewaySnapshot> {
    return this.get<GatewaySnapshot>('/v1/snapshot', signal).then((value) => value as GatewaySnapshot);
  }

  events(cursor: string, wait = 25, signal?: AbortSignal): Promise<GatewaySnapshot | null> {
    const query = '?cursor=' + encodeURIComponent(cursor) + '&wait=' + Math.max(1, Math.min(30, wait));
    return this.get<GatewaySnapshot>('/v1/events' + query, signal, true);
  }

  chart(symbol: string, n = 180): Promise<ChartPayload> {
    return this.get<ChartPayload>('/v1/chart/' + encodeURIComponent(symbol) + '?n=' + n)
      .then((value) => value as ChartPayload);
  }

  trades(symbol: string, limit = 50): Promise<TradeRow[]> {
    return this.get<TradeRow[]>('/v1/trades/' + encodeURIComponent(symbol) + '?limit=' + limit)
      .then((value) => value || []);
  }

  brain(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/brain').then((value) => value || {});
  }

  apex(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/apex').then((value) => value || {});
  }

  learningHealth(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/learning/health').then((value) => value || {});
  }

  possibility(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/possibility').then((value) => value || {});
  }

  engineControl(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/engine-control').then((value) => value || {});
  }

  integrity(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/integrity').then((value) => value || {});
  }

  research(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/research').then((value) => value || {});
  }

  startBacktest(request: {
    asset: string;
    chart_type?: 'real' | 'heikin_ashi';
    session?: 'rth' | 'eth';
    timeframe?: string;
    window_start?: number;
    window_end?: number;
  }): Promise<JsonObject> {
    return this.post<JsonObject>('/v1/backtest', request);
  }

  backtest(jobId: string): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/backtest/' + encodeURIComponent(jobId))
      .then((value) => value || {});
  }

  notificationStatus(): Promise<JsonObject> {
    return this.get<JsonObject>('/v1/notifications').then((value) => value || {});
  }

  registerPush(expoPushToken: string, platform: 'ios' | 'android'): Promise<JsonObject> {
    return this.post<JsonObject>('/v1/notifications/register', {
      expo_push_token: expoPushToken,
      platform,
      topics: ['system'],
    });
  }

  unregisterPush(): Promise<JsonObject> {
    return this.post<JsonObject>('/v1/notifications/unregister', {});
  }

  async revoke(): Promise<void> {
    await this.ensureSession();
    await requestJson<JsonObject>(this.baseUrl, '/v1/revoke', {
      method: 'POST',
      body: {},
      token: this.credentials.sessionToken,
    });
  }
}
