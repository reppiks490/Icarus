import type { JsonObject, PublicStatus, SystemAudit } from './types';

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

export class IcarusClient {
  readonly baseUrl: string;

  constructor(baseUrl: string, private readonly token = '') {
    this.baseUrl = normalizeBaseUrl(baseUrl);
  }

  private async get<T>(path: string, authenticated = false): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (authenticated) {
      if (!this.token) throw new IcarusApiError('Admin token is required for this panel');
      headers.Authorization = 'Bearer ' + this.token;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(this.baseUrl + path, {
        method: 'GET',
        headers,
        cache: 'no-store',
        signal: controller.signal,
      });
      const text = await response.text();
      let payload: unknown = {};
      try {
        payload = text ? JSON.parse(text) : {};
      } catch {
        throw new IcarusApiError('ICARUS returned non-JSON data', response.status);
      }
      if (!response.ok) {
        const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
          ? String((payload as { detail?: unknown }).detail || '')
          : '';
        throw new IcarusApiError(detail || 'ICARUS request failed', response.status);
      }
      return payload as T;
    } catch (error) {
      if (error instanceof IcarusApiError) throw error;
      if (error instanceof Error && error.name === 'AbortError') {
        throw new IcarusApiError('ICARUS gateway timed out');
      }
      throw new IcarusApiError(error instanceof Error ? error.message : 'Network error');
    } finally {
      clearTimeout(timer);
    }
  }

  health(): Promise<JsonObject> {
    return this.get('/healthz');
  }

  status(): Promise<PublicStatus> {
    return this.get('/status/public');
  }

  audit(): Promise<SystemAudit> {
    return this.get('/api/system/audit');
  }

  briefing(): Promise<JsonObject> {
    return this.get('/api/briefing');
  }

  brain(): Promise<JsonObject> {
    return this.get('/api/brain', true);
  }

  apex(): Promise<JsonObject> {
    return this.get('/api/apex', true);
  }

  learningHealth(): Promise<JsonObject> {
    return this.get('/api/learning/health', true);
  }

  engineControl(): Promise<JsonObject> {
    return this.get('/api/engine-control', true);
  }
}
