import * as SecureStore from 'expo-secure-store';
import type { DeviceCredentials } from './types';

const KEY = 'icarus.mobile.device.v2';

export async function loadCredentials(): Promise<DeviceCredentials | null> {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<DeviceCredentials>;
    if (
      typeof value.baseUrl !== 'string' ||
      typeof value.deviceId !== 'string' ||
      typeof value.refreshToken !== 'string' ||
      typeof value.sessionToken !== 'string' ||
      typeof value.sessionExpiresAt !== 'number'
    ) {
      return null;
    }
    return value as DeviceCredentials;
  } catch {
    return null;
  }
}

export async function saveCredentials(value: DeviceCredentials): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify(value), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export async function clearCredentials(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}
