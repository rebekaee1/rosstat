// Лёгкая обёртка ECharts для сложных геометрий BI (sankey, sunburst,
// calendar-heatmap), которых нет в Recharts. Tree-shaken импорт через
// echarts/core: в бандл попадают только используемые чарты. Экземпляр
// живёт в ref, опции обновляются без пересоздания, ресайз — по контейнеру.
import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { SankeyChart, SunburstChart, HeatmapChart } from 'echarts/charts';
import {
  TooltipComponent, VisualMapComponent, CalendarComponent, GridComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  SankeyChart, SunburstChart, HeatmapChart,
  TooltipComponent, VisualMapComponent, CalendarComponent, GridComponent,
  CanvasRenderer,
]);

export default function EChart({ option, height = 320, className = '' }) {
  const nodeRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!nodeRef.current) return undefined;
    chartRef.current = echarts.init(nodeRef.current);
    const ro = new ResizeObserver(() => chartRef.current && chartRef.current.resize());
    ro.observe(nodeRef.current);
    return () => {
      ro.disconnect();
      if (chartRef.current) { chartRef.current.dispose(); chartRef.current = null; }
    };
  }, []);

  useEffect(() => {
    if (chartRef.current && option) chartRef.current.setOption(option, true);
  }, [option]);

  return <div ref={nodeRef} className={className} style={{ width: '100%', height }} />;
}
