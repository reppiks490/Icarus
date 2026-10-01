import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { IcarusApiError, IcarusClient } from './src/api';
import { clearConnection, loadConnection, saveConnection } from './src/storage';
import type { ConnectionSettings, IcarusAsset, JsonObject, PublicStatus, SystemAudit } from './src/types';

type Tab = 'overview' | 'intelligence' | 'system' | 'settings';

const EMPTY: ConnectionSettings = { baseUrl: '', token: '' };

function stringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function ageLabel(age: unknown): string {
  if (typeof age !== 'number' || !Number.isFinite(age)) return '—';
  if (age < 1) return '<1s';
  if (age < 60) return Math.round(age) + 's';
  return Math.round(age / 60) + 'm';
}

function numberLabel(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '—';
}

function AssetCard({ asset }: { asset: IcarusAsset }) {
  const stale = typeof asset.poll_age === 'number' && asset.poll_age > 60;
  const bad = Boolean(asset.last_error);
  return (
    <View style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.asset}>{asset.symbol || 'UNKNOWN'}</Text>
        <View style={[styles.pill, bad ? styles.pillBad : stale ? styles.pillWarn : styles.pillGood]}>
          <Text style={styles.pillText}>{bad ? 'ERROR' : stale ? 'STALE' : asset.warm ? 'LIVE' : 'WARMING'}</Text>
        </View>
      </View>
      <View style={styles.metricGrid}>
        <Metric label="Last" value={numberLabel(asset.last)} />
        <Metric label="Feed age" value={ageLabel(asset.poll_age)} />
        <Metric label="Trades" value={numberLabel(asset.trades_total)} />
        <Metric label="Position" value={String(asset.position ?? '—')} />
      </View>
      {asset.last_error ? <Text style={styles.errorText}>{String(asset.last_error)}</Text> : null}
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

function JsonPanel({ title, data }: { title: string; data: JsonObject | null }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text selectable style={styles.code}>{data ? stringify(data) : 'Not loaded'}</Text>
    </View>
  );
}

export default function App() {
  const [settings, setSettings] = useState<ConnectionSettings>(EMPTY);
  const [draft, setDraft] = useState<ConnectionSettings>(EMPTY);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useState<Tab>('overview');
  const [status, setStatus] = useState<PublicStatus | null>(null);
  const [audit, setAudit] = useState<SystemAudit | null>(null);
  const [briefing, setBriefing] = useState<JsonObject | null>(null);
  const [brain, setBrain] = useState<JsonObject | null>(null);
  const [apex, setApex] = useState<JsonObject | null>(null);
  const [learning, setLearning] = useState<JsonObject | null>(null);
  const [control, setControl] = useState<JsonObject | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const liveRef = useRef(true);

  const client = useMemo(
    () => settings.baseUrl ? new IcarusClient(settings.baseUrl, settings.token) : null,
    [settings],
  );

  useEffect(() => {
    liveRef.current = true;
    loadConnection().then((stored) => {
      if (!liveRef.current) return;
      const next = stored || EMPTY;
      setSettings(next);
      setDraft(next);
      setBooting(false);
    });
    return () => {
      liveRef.current = false;
    };
  }, []);

  const refreshPublic = async (showSpinner = false) => {
    if (!client) return;
    if (showSpinner) setRefreshing(true);
    try {
      const [nextStatus, nextAudit, nextBriefing] = await Promise.all([
        client.status(),
        client.audit(),
        client.briefing(),
      ]);
      setStatus(nextStatus);
      setAudit(nextAudit);
      setBriefing(nextBriefing);
      setError('');
    } catch (e) {
      setError(e instanceof IcarusApiError ? e.message : String(e));
    } finally {
      if (showSpinner) setRefreshing(false);
    }
  };

  const refreshIntelligence = async () => {
    if (!client) return;
    try {
      const [nextBrain, nextApex, nextLearning, nextControl] = await Promise.all([
        client.brain(),
        client.apex(),
        client.learningHealth(),
        client.engineControl(),
      ]);
      setBrain(nextBrain);
      setApex(nextApex);
      setLearning(nextLearning);
      setControl(nextControl);
      setError('');
    } catch (e) {
      setError(e instanceof IcarusApiError ? e.message : String(e));
    }
  };

  useEffect(() => {
    if (!client) return;
    void refreshPublic();
    const timer = setInterval(() => void refreshPublic(), 5000);
    return () => clearInterval(timer);
  }, [client]);

  useEffect(() => {
    if (tab === 'intelligence' && client) void refreshIntelligence();
  }, [tab, client]);

  const connect = async () => {
    try {
      const candidate = new IcarusClient(draft.baseUrl, draft.token);
      await candidate.health();
      const next = { baseUrl: candidate.baseUrl, token: draft.token };
      await saveConnection(next);
      setSettings(next);
      setDraft(next);
      setError('');
      setTab('overview');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const disconnect = async () => {
    await clearConnection();
    setSettings(EMPTY);
    setDraft(EMPTY);
    setStatus(null);
    setAudit(null);
    setBriefing(null);
    setBrain(null);
    setApex(null);
    setLearning(null);
    setControl(null);
    setTab('settings');
  };

  if (booting) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.center}>
          <ActivityIndicator size="large" />
          <Text style={styles.muted}>Loading ICARUS Mobile…</Text>
        </View>
      </SafeAreaView>
    );
  }

  const assets = status?.assets || [];
  const connected = Boolean(settings.baseUrl);

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>DIVINE PROVIDENCE</Text>
          <Text style={styles.title}>ICARUS MOBILE</Text>
        </View>
        <View style={[styles.statusDot, connected && !error ? styles.dotGood : styles.dotBad]} />
      </View>

      <View style={styles.tabs}>
        {(['overview', 'intelligence', 'system', 'settings'] as Tab[]).map((item) => (
          <Pressable key={item} onPress={() => setTab(item)} style={[styles.tab, tab === item && styles.tabActive]}>
            <Text style={[styles.tabText, tab === item && styles.tabTextActive]}>{item.toUpperCase()}</Text>
          </Pressable>
        ))}
      </View>

      {error ? <Text style={styles.banner}>{error}</Text> : null}

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refreshPublic(true)} tintColor="#ffffff" />}
      >
        {tab === 'overview' ? (
          <>
            {!connected ? (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Gateway not configured</Text>
                <Text style={styles.body}>Open SETTINGS and enter the HTTPS URL for the ICARUS mobile gateway.</Text>
              </View>
            ) : null}
            <View style={styles.hero}>
              <Text style={styles.heroLabel}>ENGINE STATE</Text>
              <Text style={styles.heroValue}>{status?.paused ? 'PAUSED' : status?.all_warm ? 'LIVE' : 'WARMING'}</Text>
              <Text style={styles.muted}>{assets.length} assets · {audit?.status ? 'system ' + audit.status : 'audit pending'}</Text>
            </View>
            {assets.map((asset, i) => <AssetCard key={String(asset.symbol || i)} asset={asset} />)}
            <JsonPanel title="Briefing" data={briefing} />
          </>
        ) : null}

        {tab === 'intelligence' ? (
          <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Read-only intelligence</Text>
              <Text style={styles.body}>This first mobile slice observes ICARUS. Trade execution remains outside the mobile surface.</Text>
              <Pressable style={styles.primaryButton} onPress={() => void refreshIntelligence()}>
                <Text style={styles.primaryButtonText}>REFRESH INTELLIGENCE</Text>
              </Pressable>
            </View>
            <JsonPanel title="Adaptive Brain" data={brain} />
            <JsonPanel title="APEX Ω" data={apex} />
            <JsonPanel title="Learning Health" data={learning} />
          </>
        ) : null}

        {tab === 'system' ? (
          <>
            <JsonPanel title="Repository / Loop Audit" data={audit} />
            <JsonPanel title="Engine Control Snapshot" data={control} />
          </>
        ) : null}

        {tab === 'settings' ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Connection</Text>
            <Text style={styles.fieldLabel}>Gateway URL</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              placeholder="https://icarus.example.com"
              placeholderTextColor="#566078"
              value={draft.baseUrl}
              onChangeText={(baseUrl) => setDraft((x) => ({ ...x, baseUrl }))}
              style={styles.input}
            />
            <Text style={styles.fieldLabel}>Admin token</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry
              placeholder="Bearer token"
              placeholderTextColor="#566078"
              value={draft.token}
              onChangeText={(token) => setDraft((x) => ({ ...x, token }))}
              style={styles.input}
            />
            <Text style={styles.hint}>Credentials are stored with Expo SecureStore on the device. Use an HTTPS gateway in production; do not expose the loopback engine directly.</Text>
            <Pressable style={styles.primaryButton} onPress={() => void connect()}>
              <Text style={styles.primaryButtonText}>TEST + SAVE CONNECTION</Text>
            </Pressable>
            {connected ? (
              <Pressable style={styles.secondaryButton} onPress={() => void disconnect()}>
                <Text style={styles.secondaryButtonText}>FORGET CONNECTION</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#07090f' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14 },
  header: { paddingHorizontal: 18, paddingTop: 10, paddingBottom: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  eyebrow: { color: '#7e8aa8', fontSize: 10, letterSpacing: 2.4, fontWeight: '700' },
  title: { color: '#f7f9ff', fontSize: 24, letterSpacing: 1.2, fontWeight: '800' },
  statusDot: { width: 11, height: 11, borderRadius: 6 },
  dotGood: { backgroundColor: '#51d88a' },
  dotBad: { backgroundColor: '#ff5d73' },
  tabs: { flexDirection: 'row', paddingHorizontal: 10, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#1d2230' },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#90a7ff' },
  tabText: { color: '#66708a', fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
  tabTextActive: { color: '#dce3ff' },
  banner: { marginHorizontal: 14, marginTop: 10, borderRadius: 8, padding: 10, backgroundColor: '#35141c', color: '#ff9dac', fontSize: 12 },
  scroll: { flex: 1 },
  content: { padding: 14, gap: 12, paddingBottom: 42 },
  hero: { padding: 18, borderRadius: 16, backgroundColor: '#0d1220', borderWidth: 1, borderColor: '#24304a' },
  heroLabel: { color: '#71809e', fontSize: 10, letterSpacing: 1.6, fontWeight: '700' },
  heroValue: { color: '#eef2ff', fontSize: 34, fontWeight: '800', marginTop: 4 },
  card: { padding: 15, borderRadius: 14, backgroundColor: '#0c0f17', borderWidth: 1, borderColor: '#1b2130', gap: 10 },
  cardTitle: { color: '#f0f3ff', fontSize: 17, fontWeight: '800' },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  asset: { color: '#f4f6ff', fontSize: 22, fontWeight: '800' },
  pill: { borderRadius: 999, paddingHorizontal: 9, paddingVertical: 5 },
  pillGood: { backgroundColor: '#123725' },
  pillWarn: { backgroundColor: '#453415' },
  pillBad: { backgroundColor: '#431824' },
  pillText: { color: '#ffffff', fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
  metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  metric: { width: '47%', backgroundColor: '#090b11', borderRadius: 10, padding: 10 },
  metricLabel: { color: '#69748f', fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.7 },
  metricValue: { color: '#e9edff', fontSize: 15, fontWeight: '700', marginTop: 3 },
  muted: { color: '#7c869f', fontSize: 12 },
  body: { color: '#a8b0c3', fontSize: 13, lineHeight: 19 },
  errorText: { color: '#ff8498', fontSize: 11 },
  code: { color: '#aeb9d9', fontFamily: 'monospace', fontSize: 10, lineHeight: 15 },
  fieldLabel: { color: '#8e99b4', fontSize: 11, fontWeight: '700', marginTop: 4 },
  input: { backgroundColor: '#07090f', borderColor: '#273047', borderWidth: 1, borderRadius: 10, color: '#f4f6ff', paddingHorizontal: 12, paddingVertical: 12 },
  hint: { color: '#69748f', fontSize: 11, lineHeight: 16 },
  primaryButton: { backgroundColor: '#dfe6ff', borderRadius: 10, paddingVertical: 13, alignItems: 'center', marginTop: 4 },
  primaryButtonText: { color: '#11172a', fontWeight: '900', fontSize: 11, letterSpacing: 0.7 },
  secondaryButton: { borderColor: '#353d54', borderWidth: 1, borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  secondaryButtonText: { color: '#aeb8d2', fontWeight: '800', fontSize: 11 },
});
