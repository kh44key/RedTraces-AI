"use client";
import { useEffect, useRef } from "react";

/** Decorative visualization only: never encodes fabricated geographic source data. */
export function TelemetryGlobe({ running }: { running: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = 480 * ratio;
    canvas.height = 350 * ratio;
    ctx.scale(ratio, ratio);
    const points: [number, number, number][] = [];
    for (let lat = -82; lat <= 82; lat += 8) {
      for (let lon = 0; lon < 360; lon += 9) {
        const p = (lat * Math.PI) / 180,
          t = (lon * Math.PI) / 180;
        points.push([
          Math.cos(p) * Math.cos(t),
          Math.sin(p),
          Math.cos(p) * Math.sin(t),
        ]);
      }
    }
    let frame = 0,
      rotation = 0,
      last = 0,
      inView = true;
    const paint = () => {
      ctx.clearRect(0, 0, 480, 350);
      const light = ctx.createRadialGradient(210, 125, 5, 240, 175, 156);
      light.addColorStop(0, "#29815e40");
      light.addColorStop(0.7, "#1f6d5840");
      light.addColorStop(1, "#0d393900");
      ctx.fillStyle = light;
      ctx.beginPath();
      ctx.arc(240, 175, 153, 0, Math.PI * 2);
      ctx.fill();
      for (const [x, y, z] of points) {
        const rx = x * Math.cos(rotation) + z * Math.sin(rotation);
        const rz = z * Math.cos(rotation) - x * Math.sin(rotation);
        if (rz < -0.25) continue;
        const tilt = -0.19,
          py = y * Math.cos(tilt) - rx * Math.sin(tilt),
          px = rx * Math.cos(tilt) + y * Math.sin(tilt);
        const alpha = 0.13 + Math.max(0, rz) * 0.72;
        ctx.fillStyle = `rgba(139,187,146,${alpha})`;
        ctx.beginPath();
        ctx.arc(
          240 + px * 148,
          175 + py * 148,
          0.75 + Math.max(0, rz) * 0.9,
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }
    };
    const tick = (t: number) => {
      if (t - last >= 33) {
        rotation += Math.min(t - last, 60) * 0.00012;
        last = t;
        paint();
      }
      frame = requestAnimationFrame(tick);
    };
    const update = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      paint();
      if (running && !reduced.matches && !document.hidden && inView) {
        last = performance.now();
        frame = requestAnimationFrame(tick);
      }
    };
    const observer = new IntersectionObserver(([e]) => {
      inView = e.isIntersecting;
      update();
    });
    observer.observe(canvas);
    document.addEventListener("visibilitychange", update);
    reduced.addEventListener("change", update);
    update();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("visibilitychange", update);
      reduced.removeEventListener("change", update);
    };
  }, [running]);
  return (
    <canvas ref={ref} className="rt-telemetry-canvas" aria-hidden="true" />
  );
}

export function CountUp({ value }: { value: number | string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const counted = useRef(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof value !== "number") return;
    if (counted.current) { el.textContent = value.toLocaleString(); return; }
    let frame = 0;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finish = () => {
      cancelAnimationFrame(frame);
      el.textContent = value.toLocaleString();
    };
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      observer.disconnect();
      counted.current = true;
      if (reduced.matches || el.closest(".rt-reduced")) {
        finish();
        return;
      }
      const start = performance.now();
      const tick = (now: number) => {
        if (reduced.matches || el.closest(".rt-reduced")) {
          finish();
          return;
        }
        const p = Math.min((now - start) / 1100, 1);
        el.textContent = Math.round(
          value * (1 - Math.pow(1 - p, 4)),
        ).toLocaleString();
        if (p < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [value]);
  return (
    <span
      aria-label={typeof value === "number" ? value.toLocaleString() : value}
    >
      <span ref={ref} aria-hidden="true">
        {typeof value === "number" ? value.toLocaleString() : value}
      </span>
    </span>
  );
}
