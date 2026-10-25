import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

export type PushRegistration = {
  expoPushToken: string;
  platform: 'ios' | 'android';
};

export async function registerForSystemPush(): Promise<PushRegistration> {
  if (!Device.isDevice) {
    throw new Error('Push notifications require a physical device.');
  }

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('system', {
      name: 'ICARUS System',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 160, 250],
      sound: 'default',
    });
  }

  let permission = await Notifications.getPermissionsAsync();
  if (permission.status !== 'granted') {
    permission = await Notifications.requestPermissionsAsync();
  }
  if (permission.status !== 'granted') {
    throw new Error('Notification permission was not granted.');
  }

  const easConfig = (Constants as unknown as { easConfig?: { projectId?: string } }).easConfig;
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined;
  const projectId = easConfig?.projectId || extra?.eas?.projectId;
  if (!projectId) {
    throw new Error('EAS project ID is not configured for this build.');
  }

  const result = await Notifications.getExpoPushTokenAsync({ projectId });
  const platform = Platform.OS === 'ios' ? 'ios' : Platform.OS === 'android' ? 'android' : null;
  if (!platform) {
    throw new Error('Push notifications are supported on iOS and Android builds only.');
  }
  return { expoPushToken: result.data, platform };
}
