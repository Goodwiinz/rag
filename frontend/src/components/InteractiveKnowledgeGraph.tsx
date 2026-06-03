'use client';

import React, { useEffect, useRef } from 'react';
import { useTheme } from 'next-themes';

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  glowColor: string;
}

interface InteractiveKnowledgeGraphProps {
  /** Number of entity nodes. Hero background uses a denser field. */
  nodeCount?: number;
  /** When false, the canvas ignores pointer input (decorative background use). */
  interactive?: boolean;
  className?: string;
}

// Warm-gold identity palette only. Canvas hex is the sanctioned data-viz
// exception (see DESIGN.md); the prior cyan/#00d4ff was phosphor-era drift.
const PALETTE = {
  dark: {
    cores: ['#d4a039', '#e8b84a', '#f5d680'], // Sol, Helios, Apollo
    glows: [
      'rgba(212, 160, 57, 0.40)',
      'rgba(232, 184, 74, 0.36)',
      'rgba(245, 214, 128, 0.30)',
    ],
    link: '245, 240, 232', // Ivory
    cursorLink: '232, 184, 74', // Helios
  },
  light: {
    cores: ['#996d1a', '#b9851f', '#a3781c'],
    glows: [
      'rgba(153, 109, 26, 0.28)',
      'rgba(185, 133, 31, 0.24)',
      'rgba(163, 120, 28, 0.20)',
    ],
    link: '10, 10, 14', // Erebus
    cursorLink: '153, 109, 26', // Sol-safe
  },
} as const;

export function InteractiveKnowledgeGraph({
  nodeCount = 14,
  interactive = true,
  className = '',
}: InteractiveKnowledgeGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const mousePosRef = useRef<{ x: number; y: number } | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const isDark = resolvedTheme !== 'light';
    const theme = isDark ? PALETTE.dark : PALETTE.light;
    const count = Math.max(4, Math.min(nodeCount, 48));

    const reduceMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    let animationFrameId = 0;
    let nodes: Node[] = [];

    const resizeCanvas = () => {
      const rect = containerRef.current?.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = rect?.width || 500;
      const h = rect?.height || 320;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const viewW = () =>
      canvas.width / Math.min(window.devicePixelRatio || 1, 2);
    const viewH = () =>
      canvas.height / Math.min(window.devicePixelRatio || 1, 2);

    const initNodes = () => {
      const w = viewW();
      const h = viewH();
      nodes = Array.from({ length: count }, (_, i) => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 2.5 + 1.5,
        color: theme.cores[i % theme.cores.length],
        glowColor: theme.glows[i % theme.glows.length],
      }));
    };

    resizeCanvas();
    initNodes();
    window.addEventListener('resize', resizeCanvas);

    // Track on window, not the canvas: under the full-bleed hero the canvas
    // sits behind a legibility mask and the text column, so canvas-local
    // listeners miss most of the viewport. Convert to canvas-local coords and
    // drop the cursor when it leaves the canvas box.
    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      mousePosRef.current =
        x >= 0 && x <= rect.width && y >= 0 && y <= rect.height
          ? { x, y }
          : null;
    };
    const handleMouseLeave = () => {
      mousePosRef.current = null;
    };

    if (interactive) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseout', handleMouseLeave);
    }

    const drawFrame = () => {
      const w = viewW();
      const h = viewH();
      ctx.clearRect(0, 0, w, h);

      // Scale link distances to node density so the graph reads as connected
      // at any size, from a small card to a full-bleed hero.
      const spacing = Math.sqrt((w * h) / nodes.length);
      const connectionDist = spacing * 1.5;
      const mouseConnectionDist = spacing * 2.4;
      ctx.lineWidth = 0.75;

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < connectionDist) {
            const alpha = (1 - dist / connectionDist) * (isDark ? 0.16 : 0.1);
            ctx.strokeStyle = `rgba(${theme.link}, ${alpha})`;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }

        const cursor = mousePosRef.current;
        if (interactive && cursor) {
          const dx = nodes[i].x - cursor.x;
          const dy = nodes[i].y - cursor.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < mouseConnectionDist) {
            const alpha =
              (1 - dist / mouseConnectionDist) * (isDark ? 0.32 : 0.2);
            ctx.strokeStyle = `rgba(${theme.cursorLink}, ${alpha})`;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(cursor.x, cursor.y);
            ctx.stroke();
            nodes[i].vx += (dx / dist) * -0.005;
            nodes[i].vy += (dy / dist) * -0.005;
          }
        }
      }

      nodes.forEach((node) => {
        const grad = ctx.createRadialGradient(
          node.x,
          node.y,
          0,
          node.x,
          node.y,
          node.radius * 3.5
        );
        grad.addColorStop(0, node.glowColor);
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius * 3.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = node.color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fill();
      });
    };

    const tick = () => {
      const w = viewW();
      const h = viewH();
      nodes.forEach((node) => {
        node.x += node.vx;
        node.y += node.vy;
        node.vx *= 0.99;
        node.vy *= 0.99;
        if (node.x < 0 || node.x > w) {
          node.vx *= -1;
          node.x = node.x < 0 ? 0 : w;
        }
        if (node.y < 0 || node.y > h) {
          node.vy *= -1;
          node.y = node.y < 0 ? 0 : h;
        }
      });
      drawFrame();
      animationFrameId = requestAnimationFrame(tick);
    };

    if (reduceMotion) {
      drawFrame(); // static single frame, no animation loop
    } else {
      tick();
    }

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    };
  }, [resolvedTheme, nodeCount, interactive]);

  return (
    <div
      ref={containerRef}
      className={`w-full h-full min-h-[128px] relative overflow-hidden ${className}`}
    >
      <canvas
        ref={canvasRef}
        className={`absolute inset-0 block h-full w-full ${interactive ? 'cursor-crosshair' : 'pointer-events-none'}`}
      />
    </div>
  );
}
