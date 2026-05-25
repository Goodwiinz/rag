'use client';

import React, { useEffect, useRef, useState } from 'react';
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

export function InteractiveKnowledgeGraph() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let nodes: Node[] = [];
    const nodeCount = 12;

    // Define colors according to active theme
    const isDark = resolvedTheme === 'dark';
    const primaryGreen = isDark ? '#d4a039' : '#956f1b';
    const primaryCyan = isDark ? '#00d4ff' : '#0891b2';
    const primaryGold = isDark ? '#ffb700' : '#7a5c14';

    const colors = [primaryGreen, primaryCyan, primaryGold];
    const glowColors = [
      'rgba(212, 160, 57, 0.4)',
      'rgba(0, 212, 255, 0.4)',
      'rgba(255, 183, 0, 0.4)',
    ];

    // Resize handler
    const resizeCanvas = () => {
      const rect = containerRef.current?.getBoundingClientRect();
      canvas.width = rect?.width || 500;
      canvas.height = rect?.height || 128;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Initialize nodes
    const initNodes = () => {
      nodes = [];
      for (let i = 0; i < nodeCount; i++) {
        const colorIdx = i % colors.length;
        nodes.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          radius: Math.random() * 2.5 + 1.5,
          color: colors[colorIdx],
          glowColor: glowColors[colorIdx],
        });
      }
    };

    initNodes();

    // Mouse events
    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      setMousePos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    };

    const handleMouseLeave = () => {
      setMousePos(null);
    };

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseleave', handleMouseLeave);

    // Animation Loop
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw background grid lines (subtle overlay)
      ctx.strokeStyle = isDark ? 'rgba(255, 255, 255, 0.015)' : 'rgba(10, 10, 14, 0.025)';
      ctx.lineWidth = 1;
      const gridSize = 30;
      for (let x = 0; x < canvas.width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Update and draw connections first
      const connectionDist = 85;
      ctx.lineWidth = 0.75;

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < connectionDist) {
            const alpha = (1 - dist / connectionDist) * (isDark ? 0.12 : 0.08);
            ctx.strokeStyle = isDark
              ? `rgba(255, 255, 255, ${alpha})`
              : `rgba(10, 10, 14, ${alpha})`;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }

        // Connect to mouse if active
        if (mousePos) {
          const dx = nodes[i].x - mousePos.x;
          const dy = nodes[i].y - mousePos.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const mouseConnectionDist = 100;

          if (dist < mouseConnectionDist) {
            const alpha = (1 - dist / mouseConnectionDist) * (isDark ? 0.25 : 0.15);
            ctx.strokeStyle = isDark
              ? `rgba(212, 160, 57, ${alpha})`
              : `rgba(149, 111, 27, ${alpha})`;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(mousePos.x, mousePos.y);
            ctx.stroke();

            // Attract nodes slightly to the mouse
            nodes[i].vx += (dx / dist) * -0.005;
            nodes[i].vy += (dy / dist) * -0.005;
          }
        }
      }

      // Update and draw nodes
      nodes.forEach((node) => {
        // Move node
        node.x += node.vx;
        node.y += node.vy;

        // Friction to keep movement steady
        node.vx *= 0.99;
        node.vy *= 0.99;

        // Bounce off canvas boundaries
        if (node.x < 0 || node.x > canvas.width) {
          node.vx *= -1;
          node.x = node.x < 0 ? 0 : canvas.width;
        }
        if (node.y < 0 || node.y > canvas.height) {
          node.vy *= -1;
          node.y = node.y < 0 ? 0 : canvas.height;
        }

        // Draw node glow (subtle radial circle)
        ctx.beginPath();
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
        ctx.arc(node.x, node.y, node.radius * 3.5, 0, Math.PI * 2);
        ctx.fill();

        // Draw main node core
        ctx.beginPath();
        ctx.fillStyle = node.color;
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, [resolvedTheme]);

  return (
    <div ref={containerRef} className="w-full h-full min-h-[128px] relative overflow-hidden">
      <canvas ref={canvasRef} className="absolute inset-0 block cursor-crosshair" />
    </div>
  );
}
