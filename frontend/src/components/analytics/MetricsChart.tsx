import React, { useRef, useEffect } from 'react';

interface DataPoint {
  label: string;
  value: number;
  timestamp?: string;
}

interface MetricsChartProps {
  data: DataPoint[];
  title: string;
  type?: 'line' | 'bar' | 'area';
  color?: string;
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
}

const MetricsChart: React.FC<MetricsChartProps> = ({
  data,
  title,
  type = 'line',
  color = '#3B82F6',
  height = 300,
  showGrid = true,
  showLegend = true
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || data.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    // Clear canvas
    ctx.clearRect(0, 0, rect.width, rect.height);

    // Chart dimensions
    const padding = { top: 20, right: 20, bottom: 40, left: 60 };
    const chartWidth = rect.width - padding.left - padding.right;
    const chartHeight = rect.height - padding.top - padding.bottom;

    // Find min and max values
    const values = data.map(d => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1;

    // Draw grid
    if (showGrid) {
      ctx.strokeStyle = '#E5E7EB';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);

      // Horizontal grid lines
      for (let i = 0; i <= 5; i++) {
        const y = padding.top + (chartHeight * i) / 5;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + chartWidth, y);
        ctx.stroke();

        // Y-axis labels
        const value = maxValue - (valueRange * i) / 5;
        ctx.fillStyle = '#6B7280';
        ctx.font = '12px system-ui';
        ctx.textAlign = 'right';
        ctx.fillText(value.toFixed(1), padding.left - 10, y + 4);
      }

      ctx.setLineDash([]);
    }

    // Draw axes
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();

    // Draw data
    if (type === 'line' || type === 'area') {
      // Line chart
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();

      data.forEach((point, index) => {
        const x = padding.left + (chartWidth * index) / (data.length - 1);
        const y = padding.top + chartHeight - ((point.value - minValue) / valueRange) * chartHeight;

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();

      // Fill area for area chart
      if (type === 'area') {
        ctx.fillStyle = color + '20'; // Add transparency
        ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
        ctx.lineTo(padding.left, padding.top + chartHeight);
        ctx.closePath();
        ctx.fill();
      }

      // Draw points
      ctx.fillStyle = color;
      data.forEach((point, index) => {
        const x = padding.left + (chartWidth * index) / (data.length - 1);
        const y = padding.top + chartHeight - ((point.value - minValue) / valueRange) * chartHeight;

        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fill();
      });

    } else if (type === 'bar') {
      // Bar chart
      const barWidth = chartWidth / data.length * 0.6;
      const barSpacing = chartWidth / data.length * 0.4;

      ctx.fillStyle = color;
      data.forEach((point, index) => {
        const x = padding.left + (chartWidth * index) / (data.length - 1) - barWidth / 2;
        const barHeight = ((point.value - minValue) / valueRange) * chartHeight;
        const y = padding.top + chartHeight - barHeight;

        ctx.fillRect(x, y, barWidth, barHeight);
      });
    }

    // X-axis labels
    ctx.fillStyle = '#6B7280';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    data.forEach((point, index) => {
      const x = padding.left + (chartWidth * index) / (data.length - 1);
      const y = padding.top + chartHeight + 20;
      ctx.fillText(point.label, x, y);
    });

  }, [data, type, color, height, showGrid]);

  return (
    <div className="metrics-chart">
      <div className="chart-header mb-4">
        <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        {showLegend && (
          <div className="flex items-center mt-2">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: color }}
            ></div>
            <span className="ml-2 text-sm text-gray-600">Metric Value</span>
          </div>
        )}
      </div>
      <div className="chart-container" style={{ height: `${height}px` }}>
        <canvas
          ref={canvasRef}
          className="w-full h-full"
          style={{ display: 'block' }}
        />
      </div>
    </div>
  );
};

export default MetricsChart;