import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
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
import { PriceChart } from './src/PriceChart';
import { clearCredentials, loadCredentials, saveCredentials } from './src/storage';
import type {
  ChartPayload,
  DeviceCredentials,
  GatewaySnapshot,
  IcarusAsset,
  JsonObject,
  TradeRow,
} from './src/types';

type Tab = 'overview' | 'intelligence' | 'system' | 'settings';

function errorText(error: unknown): string {
  if (error instanceof IcarusApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

function numberLabel(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '—';
}

function ageLabel(age: unknown): string {
  if (typeof age !== 'number' || !Number.isFinite(age)) return '—';
  if (age < 1) return '<1s';
  if (age < 60) return Math.round(age) + 's';
  return Math.round(age / 60) + 'm';
}

function timeLabel(epoch: unknown): string {
  if (typeof epoch !== 'number' || !Number.isFinite(epoch)) return '—';
  return new Date(epoch * 1000).toLocaleString();
}

function AssetCard({ asset, selected, onPress }: {
  asset: IcarusAsset;
  selected: boolean;
  onPress: () => void;
}) {
  const stale = typeof asset.poll_age === 'number' && asset.poll_age > 60;
  const bad = Boolean(asset.last_error);
  return (
    <Pressable onPress={onPress} style={[styles.card, selected && styles.cardSelected]}>
      <View style={styles.rowBetween}>
        <Text style={styles.asset}>{asset.symbol || 'UNKNOWN'}</Text>
        <View style={[styles.pill, bad ? styles.pillBad : stale ? styles.pillWarn : styles.pillGood]}>
          <Text style={styles.pillText}>
            {bad ? 'ERROR' : stale ? 'STALE' : asset.warm ? 'LIVE' : 'WARMING'}
          </Text>
        </View>
      </View>
      <View style={styles.metricGrid}>
        <Metric label="Last" value={numberLabel(asset.last)} />
        <Metric label="Feed age" value={ageLabel(asset.poll_age)} />
        <Metric label="Trades" value={numberLabel(asset.trades_total)} />
        <Metric label="Position" value={String(asset.position ?? '—')} />
      </View>
      {asset.last_error ? <Text style={styles.errorText}>{String(asset.last_error)}</Text> : null}
    </Pressable>
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
  let value = 'Not loaded';
  if (data) {
    try {
      const raw = JSON.stringify(data, null, 2);
      value = raw.length > 18000 ? raw.slice(0, 18000) + '\n…truncated on device' : raw;
    } catch {
      value = String(data);
    }
  }
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text selectable style={styles.code}>{value}</Text>
    </View>
  );
}

function TradeList({ trades }: { trades: TradeRow[] }) {
  if (!trades.length) return <Text style={styles.muted}>No closed trades returned.</Text>;
  return (
    <View style={styles.tradeList}>
      {trades.slice(-12).reverse().map((trade, index) => (
        <View key={String(trade.id || index) + '-' + String(trade.exit_ts || index)} style={styles.tradeRow}>
          <View style={styles.tradeMain}>
            <Text style={styles.tradeId}>{trade.id || trade.dir || 'trade'}</Text>
            <Text style={styles.tradeTime}>{timeLabel(trade.exit_ts)}</Text>
          </View>
          <View style={styles.tradeSide}>
            <Text style={styles.tradePrice}>{numberLabel(trade.entry)} → {numberLabel(trade.exit)}</Text>
            <Text style={[
              styles.tradePnl,
              typeof trade.profit === 'number' && trade.profit < 0 ? styles.negative : styles.positive,
            ]}>
              {typeof trade.profit === 'number' ? numberLabel(trade.profit) : '—'}
            </Text>
          </View>
        </View>
      ))}
    </View>
  );
}

export default function App() {
  const [credentials, setCredentials] = useState<DeviceCredentials | null>(null);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useState<Tab>('overview');
  const [snapshot, setSnapshot] = useState<GatewaySnapshot | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState('');
  const [chart, setChart] = useState<ChartPayload | null>(null);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [brain, setBrain] = useState<JsonObject | null>(null);
  const [apex, setApex] = useState<JsonObject | null>(null);
  const [learning, setLearning] = useState<JsonObject | null>(null);
  const [possibility, setPossibility] = useState<JsonObject | null>(null);
  const [control, setControl] = useState<JsonObject | null>(null);
  const [integrity, setIntegrity] = useState<JsonObject | null>(null);
  const [pairUrl, setPairUrl] = useState('');
  const [pairSecret, setPairSecret] = useState('');
  const [deviceName, setDeviceName] = useState('ICARUS ' + Platform.OS);
  const [pairBusy, setPairBusy] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    void loadCredentials().then((stored) => {
      if (!mounted.current) return;
      setCredentials(stored);
      setPairUrl(stored?.baseUrl || '');
      setBooting(false);
    });
    return () => {
      mounted.current = false;
    };
  }, []);

  const client = useMemo(() => {
    if (!credentials) return null;
    return new IcarusClient(credentials, async (next) => {
      await saveCredentials(next);
    });
  }, [credentials?.baseUrl, credentials?.deviceId]);

  const applySnapshot = (next: GatewaySnapshot) => {
    setSnapshot(next);
    if (next.error) setError(next.error);
    else setError('');
  };

  useEffect(() => {
    if (!client) return;
    let stopped = false;
    let cursor = '';
    let controller = new AbortController();

    const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    const run = async () => {
      while (!stopped) {
        try {
          const next = cursor
            ? await client.events(cursor, 25, controller.signal)
            : await client.snapshot(controller.signal);
          if (stopped) return;
          if (next) {
            cursor = next.cursor;
            applySnapshot(next);
          }
        } catch (reason) {
          if (stopped) return;
          setError(errorText(reason));
          await pause(2000);
          if (controller.signal.aborted && !stopped) controller = new AbortController();
        }
      }
    };

    void run();
    return () => {
      stopped = true;
      controller.abort();
    };
  }, [client]);

  const assets = snapshot?.status?.assets || [];

  useEffect(() => {
    if (!selectedAsset && assets[0]?.symbol) setSelectedAsset(String(assets[0].symbol));
  }, [assets, selectedAsset]);

  useEffect(() => {
    if (!client || !selectedAsset) {
      setChart(null);
      setTrades([]);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    void Promise.all([client.chart(selectedAsset, 180), client.trades(selectedAsset, 60)])
      .then(([nextChart, nextTrades]) => {
        if (cancelled) return;
        setChart(nextChart);
        setTrades(nextTrades);
      })
      .catch((reason) => {
        if (!cancelled) setError(errorText(reason));
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, selectedAsset]);

  useEffect(() => {
    if (!client || tab !== 'intelligence') return;
    let cancelled = false;
    void Promise.all([
      client.brain(),
      client.apex(),
      client.learningHealth(),
      client.possibility(),
    ]).then(([nextBrain, nextApex, nextLearning, nextPossibility]) => {
      if (cancelled) return;
      setBrain(nextBrain);
      setApex(nextApex);
      setLearning(nextLearning);
      setPossibility(nextPossibility);
    }).catch((reason) => {
      if (!cancelled) setError(errorText(reason));
    });
    return () => {
      cancelled = true;
    };
  }, [client, tab]);

  useEffect(() => {
    if (!client || tab !== 'system') return;
    let cancelled = false;
    void Promise.all([client.engineControl(), client.integrity()])
      .then(([nextControl, nextIntegrity]) => {
        if (cancelled) return;
        setControl(nextControl);
        setIntegrity(nextIntegrity);
      })
      .catch((reason) => {
        if (!cancelled) setError(errorText(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [client, tab]);

  const manualRefresh = async () => {
    if (!client) return;
    setRefreshing(true);
    try {
      applySnapshot(await client.snapshot());
      if (selectedAsset) {
        const [nextChart, nextTrades] = await Promise.all([
          client.chart(selectedAsset, 180),
          client.trades(selectedAsset, 60),
        ]);
        setChart(nextChart);
        setTrades(nextTrades);
      }
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setRefreshing(false);
    }
  };

  const pair = async () => {
    setPairBusy(true);
    try {
      const next = await IcarusClient.pair(pairUrl, deviceName, pairSecret);
      await saveCredentials(next);
      setCredentials(next);
      setPairSecret('');
      setError('');
      setTab('overview');
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setPairBusy(false);
    }
  };

  const forgetLocal = async () => {
    await clearCredentials();
    setCredentials(null);
    setSnapshot(null);
    setChart(null);
    setTrades([]);
    setSelectedAsset('');
    setTab('settings');
  };

  const revokeAndForget = async () => {
    if (!client) return;
    try {
      await client.revoke();
      await forgetLocal();
    } catch (reason) {
      setError(errorText(reason));
    }
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

  const status = snapshot?.status;
  const connected = Boolean(credentials);
  const selected = assets.find((asset) => asset.symbol === selectedAsset);

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>DIVINE PROVIDENCE</Text>
          <Text style={styles.title}>ICARUS MOBILE</Text>
        </View>
        <View style={styles.headerRight}>
          <Text style={styles.readOnly}>READ ONLY</Text>
          <View style={[styles.statusDot, connected && !error ? styles.dotGood : styles.dotBad]} />
        </View>
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
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => void manualRefresh()}
            tintColor="#ffffff"
            enabled={connected}
          />
        }
      >
        {tab === 'overview' ? (
          <>
            {!connected ? (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Pair this device</Text>
                <Text style={styles.body}>Open SETTINGS and pair this phone with the hardened ICARUS mobile gateway.</Text>
              </View>
            ) : (
              <>
                <View style={styles.hero}>
                  <Text style={styles.heroLabel}>ENGINE STATE</Text>
                  <Text style={styles.heroValue}>
                    {status?.paused ? 'PAUSED' : status?.all_warm ? 'LIVE' : 'WARMING'}
                  </Text>
                  <Text style={styles.muted}>
                    {assets.length} assets · {snapshot?.audit?.status ? 'system ' + snapshot.audit.status : 'audit pending'}
                  </Text>
                </View>
                {assets.map((asset, index) => (
                  <AssetCard
                    key={String(asset.symbol || index)}
                    asset={asset}
                    selected={asset.symbol === selectedAsset}
                    onPress={() => setSelectedAsset(String(asset.symbol || ''))}
                  />
                ))}
                {selected ? (
                  <View style={styles.card}>
                    <View style={styles.rowBetween}>
                      <Text style={styles.cardTitle}>{selectedAsset} market view</Text>
                      {detailLoading ? <ActivityIndicator size="small" /> : null}
                    </View>
                    <PriceChart data={chart} />
                    <Text style={styles.sectionLabel}>RECENT CLOSED TRADES</Text>
                    <TradeList trades={trades} />
                  </View>
                ) : null}
                <JsonPanel title="Briefing" data={snapshot?.briefing || null} />
              </>
            )}
          </>
        ) : null}

        {tab === 'intelligence' ? (
          <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>ICARUS intelligence</Text>
              <Text style={styles.body}>
                Mobile receives authenticated observation data through the gateway. No execution mutation routes are exposed.
              </Text>
            </View>
            <JsonPanel title="Adaptive Brain" data={brain} />
            <JsonPanel title="APEX Ω" data={apex} />
            <JsonPanel title="Learning Health" data={learning} />
            <JsonPanel title="Possibility Ψ" data={possibility} />
          </>
        ) : null}

        {tab === 'system' ? (
          <>
            <JsonPanel title="Repository / Loop Audit" data={snapshot?.audit || null} />
            <JsonPanel title="Engine Control Snapshot" data={control} />
            <JsonPanel title="Data Integrity" data={integrity} />
          </>
        ) : null}

        {tab === 'settings' ? (
          <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>{connected ? 'Paired device' : 'Gateway pairing'}</Text>
              {connected ? (
                <>
                  <Text style={styles.fieldLabel}>Gateway</Text>
                  <Text selectable style={styles.valueText}>{credentials?.baseUrl}</Text>
                  <Text style={styles.fieldLabel}>Device ID</Text>
                  <Text selectable style={styles.valueText}>{credentials?.deviceId}</Text>
                  <Text style={styles.hint}>
                    Session credentials are short-lived. The refresh credential is encrypted by the device SecureStore and rotates whenever a new session is issued.
                  </Text>
                  <Pressable style={styles.dangerButton} onPress={() => void revokeAndForget()}>
                    <Text style={styles.dangerButtonText}>REVOKE DEVICE + FORGET</Text>
                  </Pressable>
                  <Pressable style={styles.secondaryButton} onPress={() => void forgetLocal()}>
                    <Text style={styles.secondaryButtonText}>FORGET LOCAL CREDENTIALS ONLY</Text>
                  </Pressable>
                </>
              ) : (
                <>
                  <Text style={styles.fieldLabel}>Gateway URL</Text>
                  <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="url"
                    placeholder="https://mobile.example.com"
                    placeholderTextColor="#566078"
                    value={pairUrl}
                    onChangeText={setPairUrl}
                    style={styles.input}
                  />
                  <Text style={styles.fieldLabel}>Device name</Text>
                  <TextInput
                    autoCorrect={false}
                    placeholder="ICARUS iPhone"
                    placeholderTextColor="#566078"
                    value={deviceName}
                    onChangeText={setDeviceName}
                    style={styles.input}
                  />
                  <Text style={styles.fieldLabel}>One-time pairing secret</Text>
                  <TextInput
                    autoCapitalize="none"
                    autoCorrect={false}
                    secureTextEntry
                    placeholder="Pairing secret"
                    placeholderTextColor="#566078"
                    value={pairSecret}
                    onChangeText={setPairSecret}
                    style={styles.input}
                  />
                  <Text style={styles.hint}>
                    The pairing secret is used once and is not stored after successful pairing. Production gateways should be behind HTTPS.
                  </Text>
                  <Pressable
                    style={[styles.primaryButton, pairBusy && styles.buttonDisabled]}
                    disabled={pairBusy}
                    onPress={() => void pair()}
                  >
                    <Text style={styles.primaryButtonText}>{pairBusy ? 'PAIRING…' : 'PAIR THIS DEVICE'}</Text>
                  </Pressable>
                </>
              )}
            </View>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#07090f' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14 },
  header: {
    paddingHorizontal: 18,
    paddingTop: 10,
    paddingBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  eyebrow: { color: '#7e8aa8', fontSize: 10, letterSpacing: 2.4, fontWeight: '700' },
  title: { color: '#f7f9ff', fontSize: 24, letterSpacing: 1.2, fontWeight: '800' },
  readOnly: { color: '#8895b6', fontSize: 9, fontWeight: '900', letterSpacing: 0.9 },
  statusDot: { width: 11, height: 11, borderRadius: 6 },
  dotGood: { backgroundColor: '#51d88a' },
  dotBad: { backgroundColor: '#ff5d73' },
  tabs: {
    flexDirection: 'row',
    paddingHorizontal: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: '#1d2230',
  },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#90a7ff' },
  tabText: { color: '#66708a', fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
  tabTextActive: { color: '#dce3ff' },
  banner: {
    marginHorizontal: 14,
    marginTop: 10,
    borderRadius: 8,
    padding: 10,
    backgroundColor: '#35141c',
    color: '#ff9dac',
    fontSize: 12,
  },
  scroll: { flex: 1 },
  content: { padding: 14, gap: 12, paddingBottom: 42 },
  hero: { padding: 18, borderRadius: 16, backgroundColor: '#0d1220', borderWidth: 1, borderColor: '#24304a' },
  heroLabel: { color: '#71809e', fontSize: 10, letterSpacing: 1.6, fontWeight: '700' },
  heroValue: { color: '#eef2ff', fontSize: 34, fontWeight: '800', marginTop: 4 },
  card: { padding: 15, borderRadius: 14, backgroundColor: '#0c0f17', borderWidth: 1, borderColor: '#1b2130', gap: 10 },
  cardSelected: { borderColor: '#7287c7' },
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
  sectionLabel: { color: '#71809e', fontSize: 10, fontWeight: '800', letterSpacing: 1.1, marginTop: 4 },
  tradeList: { gap: 7 },
  tradeRow: { backgroundColor: '#090b11', borderRadius: 9, padding: 10, flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  tradeMain: { flex: 1, gap: 3 },
  tradeSide: { alignItems: 'flex-end', gap: 3 },
  tradeId: { color: '#dce2f7', fontSize: 12, fontWeight: '800' },
  tradeTime: { color: '#626d86', fontSize: 9 },
  tradePrice: { color: '#a8b2cb', fontSize: 10 },
  tradePnl: { fontSize: 12, fontWeight: '800' },
  positive: { color: '#5de09a' },
  negative: { color: '#ff687d' },
  fieldLabel: { color: '#8e99b4', fontSize: 11, fontWeight: '700', marginTop: 4 },
  valueText: { color: '#e7ebfb', fontSize: 12 },
  input: {
    backgroundColor: '#07090f',
    borderColor: '#273047',
    borderWidth: 1,
    borderRadius: 10,
    color: '#f4f6ff',
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  hint: { color: '#69748f', fontSize: 11, lineHeight: 16 },
  primaryButton: { backgroundColor: '#dfe6ff', borderRadius: 10, paddingVertical: 13, alignItems: 'center', marginTop: 4 },
  primaryButtonText: { color: '#11172a', fontWeight: '900', fontSize: 11, letterSpacing: 0.7 },
  buttonDisabled: { opacity: 0.55 },
  secondaryButton: { borderColor: '#353d54', borderWidth: 1, borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  secondaryButtonText: { color: '#aeb8d2', fontWeight: '800', fontSize: 11 },
  dangerButton: { backgroundColor: '#451925', borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  dangerButtonText: { color: '#ffb0bd', fontWeight: '900', fontSize: 11 },
});
