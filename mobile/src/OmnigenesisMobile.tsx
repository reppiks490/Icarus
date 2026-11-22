/** OMNIGENESIS ∞ — native mobile research-only animated observatory.
 * RN native-driver transform animations, no WebView, no external code,
 * no execution permissions and no fabricated study counts.
 */
import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import type { JsonObject } from './types';

type Props = { data: JsonObject | null };
type Node = { key: string; name: string; artifact: boolean };

const sparks = Array.from({ length: 22 }, (_, i) => {
  const angle = i * 2.3999632297;
  const radial = 45 + Math.sqrt(i) * 20;
  return { id: i, x: Math.cos(angle) * radial, y: Math.sin(angle) * radial * .72,
           size: i % 5 === 0 ? 3 : 2 };
});

function label(value: unknown): string {
  if (typeof value === 'string') return value.slice(0, 120);
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return '—';
}

export function OmnigenesisMobile({ data }: Props) {
  const spin = useRef(new Animated.Value(0)).current;
  const heartbeat = useRef(new Animated.Value(0)).current;
  const reverse = spin.interpolate({ inputRange: [0, 1], outputRange: ['360deg', '0deg'] });
  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  const scale = heartbeat.interpolate({ inputRange: [0, 1], outputRange: [.84, 1.24] });
  const glow = heartbeat.interpolate({ inputRange: [0, 1], outputRange: [.38, .94] });

  useEffect(() => {
    const rotation = Animated.loop(Animated.timing(spin, {
      toValue: 1, duration: 28000, easing: Easing.linear, useNativeDriver: true,
    }));
    const pulse = Animated.loop(Animated.sequence([
      Animated.timing(heartbeat, {
        toValue: 1, duration: 2100, easing: Easing.inOut(Easing.sine),
        useNativeDriver: true,
      }),
      Animated.timing(heartbeat, {
        toValue: 0, duration: 2100, easing: Easing.inOut(Easing.sine),
        useNativeDriver: true,
      }),
    ]));
    rotation.start();
    pulse.start();
    return () => { rotation.stop(); pulse.stop(); };
  }, [spin, heartbeat]);

  const studies = Array.isArray(data?.recent_studies) ? data.recent_studies : [];
  const artifacts = Array.isArray(data?.recent_artifacts) ? data.recent_artifacts : [];
  const records = useMemo<Node[]>(() => {
    const studyNodes: Node[] = studies.slice(0, 15).map((entry: unknown, i: number) => {
      const row = entry && typeof entry === 'object' ? entry as JsonObject : {};
      return { key: label(row.study_id) + String(i), name: label(row.asset),
               artifact: false };
    });
    const artifactNodes: Node[] = artifacts.slice(0, 15).map((entry: unknown, i: number) => {
      const row = entry && typeof entry === 'object' ? entry as JsonObject : {};
      return { key: label(row.artifact_id) + String(i), name: label(row.kind),
               artifact: true };
    });
    return [...studyNodes, ...artifactNodes].slice(0, 22);
  }, [data]);

  const valid = data?.schema_version === 'icarus-omnigenesis-snapshot-v1'
    && data?.status === 'RESEARCH_ONLY'
    && data?.authority !== null
    && typeof data?.authority === 'object'
    && !Array.isArray(data?.authority)
    && (data?.authority as JsonObject)?.execution_authorized === false;

  const researchCount = valid && typeof data?.study_count === 'number'
    ? data.study_count : null;
  const artifactCount = valid && typeof data?.artifact_count === 'number'
    ? data.artifact_count : null;
  const visibleNodes = valid ? records : [];

  return (
    <View style={s.panel}>
      <View style={s.header}>
        <View>
          <Text style={s.kicker}>ICARUS ΩG / SCIENTIFIC CIVILIZATION</Text>
          <Text style={s.title}>OMNIGENESIS ∞</Text>
          <Text style={s.subtitle}>MATHEMATICAL UNIVERSE OBSERVATORY</Text>
        </View>
        <Text style={s.badge}>SHADOW ONLY</Text>
      </View>
      <View style={s.scene} accessible accessibilityLabel="Decoratively animated scientific rings around observed research nodes">
        <Animated.View style={[s.outerRing, { transform: [{ rotate }, { rotateX: '65deg' }] }]} />
        <Animated.View style={[s.midRing, { transform: [{ rotate: reverse }, { rotateY: '67deg' }] }]} />
        <Animated.View style={[s.innerRing, { transform: [{ rotate }, { rotateX: '30deg' }] }]} />
        <Animated.View style={[s.particleWorld, { transform: [{ rotate: reverse }] }]}>
          {sparks.map((part) => (
            <View key={part.id} style={[s.spark, {
              width: part.size, height: part.size, borderRadius: part.size,
              left: 160 + part.x, top: 145 + part.y,
              backgroundColor: part.id % 5 === 0 ? '#ffd5a6' : '#f04a7c',
            }]} />
          ))}
        </Animated.View>
        <Animated.View style={[s.dataNodes, { transform: [{ rotate }] }]}>
          {visibleNodes.map((node, i) => {
            const a = i * 2.3999632297;
            const r = 72 + Math.sqrt(i) * 28;
            return <View key={node.key} style={[s.realNode, {
              left: 154 + Math.cos(a) * r, top: 141 + Math.sin(a) * r * .68,
              backgroundColor: node.artifact ? '#c1bbff' : '#f1bd92',
            }]} />;
          })}
        </Animated.View>
        <Animated.View style={[s.centerAura, { opacity: glow, transform: [{ scale }] }]} />
        <Animated.View style={[s.centerCore, { transform: [{ rotate: reverse }, { scale }] }]}>
          <Text style={s.omega}>Ω</Text>
        </Animated.View>
        {visibleNodes.length === 0 ? (
          <View style={s.emptyHint}>
            <Text style={s.emptyText}>NO RECORDED RESEARCH NODES</Text>
          </View>
        ) : null}
      </View>
      <View style={s.metricRow}>
        <View style={s.metric}><Text style={s.metricValue}>{researchCount === null ? '—' : researchCount}</Text><Text style={s.metricLabel}>STUDIES</Text></View>
        <View style={s.metric}><Text style={s.metricValue}>{artifactCount === null ? '—' : artifactCount}</Text><Text style={s.metricLabel}>ARTIFACTS</Text></View>
        <View style={s.metric}><Text style={[s.metricValue, s.research]}>OFF</Text><Text style={s.metricLabel}>EXECUTION</Text></View>
      </View>
      <Text style={s.disclaimer}>
        {valid
          ? 'Research records verified through the gateway. Motion is decorative, not AI-agent or market activity.'
          : 'Research evidence unavailable or unverifiable. This scene is decorative only.'}
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  panel: { backgroundColor:'#0b0711', borderColor:'#79324d', borderWidth:1,
           borderRadius:16, marginVertical:10, overflow:'hidden' },
  header: { flexDirection:'row', justifyContent:'space-between',
            padding:18, backgroundColor:'#190b18' },
  kicker: { color:'#edcaaf', fontSize:9, fontWeight:'700', letterSpacing:1.5 },
  title: { color:'#fff0f1', fontWeight:'800', fontSize:20, letterSpacing:1.5,
           marginTop:7 },
  subtitle: { color:'#b68ba4', fontSize:9, letterSpacing:1.1, marginTop:5 },
  badge: { color:'#ffa8c2', borderColor:'#ab3c67', borderWidth:1,
           fontSize:9, padding:5, height:29, borderRadius:3, overflow:'hidden' },
  scene: { height:290, alignItems:'center', justifyContent:'center',
           backgroundColor:'#0b0711', overflow:'hidden' },
  outerRing: { position:'absolute', width:270, height:270, borderRadius:135,
               borderWidth:1.2, borderColor:'#f5547b9c' },
  midRing: { position:'absolute', width:215, height:215, borderRadius:110,
             borderWidth:2, borderColor:'#b43a8a7f' },
  innerRing: { position:'absolute', width:137, height:137, borderRadius:75,
               borderWidth:1, borderColor:'#e9c3a9a0' },
  particleWorld: { position:'absolute', width:320, height:290 },
  spark: { position:'absolute' },
  dataNodes: { position:'absolute', width:320, height:290 },
  realNode: { position:'absolute', height:8, width:8, borderRadius:4 },
  centerAura: { width:92, height:92, borderRadius:46, backgroundColor:'#c02e5a29',
                position:'absolute' },
  centerCore: { width:52, height:52, borderRadius:26,
                alignItems:'center', justifyContent:'center', position:'absolute',
                backgroundColor:'#d22e65', borderWidth:2, borderColor:'#ffd7d1' },
  omega: { fontSize:26, fontWeight:'800', color:'#fff2e9', textShadowColor:'#fff',
           textShadowRadius:11 },
  emptyHint: { position:'absolute', bottom:13, alignItems:'center' },
  emptyText: { color:'#aa8299', fontSize:9, letterSpacing:1.5 },
  metricRow: { display:'flex', flexDirection:'row', padding:14,
               borderTopColor:'#5a223b', borderTopWidth:1 },
  metric: { flex:1, alignItems:'center' },
  metricValue: { color:'#fff0f2', fontSize:23, fontWeight:'800' },
  metricLabel: { color:'#b58ca3', fontSize:9, letterSpacing:1.5, marginTop:3 },
  research: { color:'#ffa3b6' },
  disclaimer: { color:'#a18c9b', fontSize:10, paddingHorizontal:17,
                paddingBottom:15, lineHeight:17 },
});
