import * as SecureStore from 'expo-secure-store';
import type { ConnectionSettings } from './types';

const KEY = 'icarus.mobile.connection.v1';

export async function loadConnection(): Promise<ConnectionSettings | null> {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<ConnectionSettings>;
    if (typeof value.baseUrl !== 'string' || typeof value.token !== 'string') return null;
    return { baseUrl: value.baseUrl, token: value.token };
  } catch {
    return null;
  }
}

export async function saveConnection(value: ConnectionSettings): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify(value), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export async function clearConnection(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}
