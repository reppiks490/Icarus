import React, { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Line, Rect } from 'react-native-svg';
import type { ChartPayload } from './types';

type Candle = [number, number, number, number, number, number?];

function validBar(row: number[]): row is Candle {
  return row.length >= 5 && row.slice(0, 5).every((value) => typeof value === 'number' && Number.isFinite(value));
}

export function PriceChart({ data }: { data: ChartPayload | null }) {
  const [width, setWidth] = useState(340);
  const bars = useMemo(
    () => (data?.bars || []).filter(validBar).slice(-90),
    [data],
  );
  if (!bars.length) {
    return <Text style={styles.empty}>No chart bars available.</Text>;
  }

  const highs = bars.map((bar) => bar[2]);
  const lows = bars.map((bar) => bar[3]);
  const hi = Math.max(...highs);
  const lo = Math.min(...lows);
  const range = Math.max(hi - lo, Number(data?.mintick || 0.01), 0.000001);
  const height = 220;
  const pad = 10;
  const innerHeight = height - pad * 2;
  const step = Math.max(2, (width - pad * 2) / bars.length);
  const bodyWidth = Math.max(1, Math.min(7, step * 0.64));
  const y = (price: number) => pad + ((hi - price) / range) * innerHeight;

  return (
    <View onLayout={(event) => setWidth(Math.max(240, event.nativeEvent.layout.width))}>
      <View style={styles.labels}>
        <Text style={styles.label}>{hi.toLocaleString(undefined, { maximumFractionDigits: 2 })}</Text>
        <Text style={styles.label}>{data?.symbol || ''} · {data?.tf || '—'}m</Text>
      </View>
      <Svg width="100%" height={height}>
        {bars.map((bar, index) => {
          const [, open, high, low, close] = bar;
          const x = pad + index * step + step / 2;
          const up = close >= open;
          const top = y(Math.max(open, close));
          const bottom = y(Math.min(open, close));
          const bodyHeight = Math.max(1.5, bottom - top);
          const stroke = up ? '#5de09a' : '#ff687d';
          return (
            <React.Fragment key={String(bar[0]) + '-' + index}>
              <Line x1={x} x2={x} y1={y(high)} y2={y(low)} stroke={stroke} strokeWidth={1} />
              <Rect
                x={x - bodyWidth / 2}
                y={top}
                width={bodyWidth}
                height={bodyHeight}
                fill={stroke}
                rx={0.5}
              />
            </React.Fragment>
          );
        })}
      </Svg>
      <Text style={styles.low}>{lo.toLocaleString(undefined, { maximumFractionDigits: 2 })}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  labels: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  label: { color: '#7d89a5', fontSize: 10, fontWeight: '700' },
  low: { color: '#65708a', fontSize: 10, marginTop: -4 },
  empty: { color: '#6f7890', fontSize: 12, paddingVertical: 28, textAlign: 'center' },
});
