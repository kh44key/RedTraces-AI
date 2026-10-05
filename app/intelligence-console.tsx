"use client";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { CountUp, TelemetryGlobe } from "./telemetry-motion";
import { useAgencyMotion, IntelligenceStory } from "./agency-motion";
import {
  Connections,
  ModuleView,
  defaults,
  type URLs,
  type Source,
} from "./legacy-collectors";
import {
  countsBy,
  downloadFile,
  emptyData,
  filterPeriod,
  initialCandidates,
  initialWatches,
  makeDemo,
  observableBundle,
  platformColors,
  type Candidate,
  type DataSet,
  type Indicator,
  type Signal,
  type Watch,
} from "./intelligence-data";

type View =
  | "overview"
  | "signals"
  | "watchlists"
  | "discovery"
  | "qualification"
  | "tracing"
  | "iocs"
  | "stix"
  | "confidence"
  | "risk"
  | "attack"
  | "correlation"
  | "noise"
  | "rules"
  | "siem"
  | "review"
  | "report"
  | "sources"
  | "connections"
  | Source;
type Detail = { title: string; label: string; body: ReactNode } | null;
const menu: { section: string; items: [View, string, string][] }[] = [
  {
    section: "WORKSPACE",
    items: [
      ["overview", "Overview", "grid"],
      ["signals", "Live signals", "pulse"],
      ["watchlists", "Target watchlists", "target"],
      ["discovery", "Auto-discovery", "compass"],
    ],
  },
  {
    section: "INTELLIGENCE",
    items: [
      ["iocs", "IOC explorer", "scan"],
      ["qualification", "Source qualification", "check"],
      ["tracing", "Forward tracing", "branch"],
      ["noise", "Noise filtering", "filter"],
      ["confidence", "Evidence confidence", "layers"],
      ["risk", "Risk scoring", "shield"],
      ["attack", "ATT&CK heatmap", "grid"],
      ["correlation", "Source correlation", "network"],
    ],
  },
  {
    section: "OPERATIONS",
    items: [
      ["stix", "STIX store", "cube"],
      ["rules", "Rule library", "code"],
      ["siem", "SIEM deployments", "send"],
      ["review", "Artifact review", "check"],
      ["report", "Current report", "file"],
    ],
  },
  {
    section: "COLLECTION",
    items: [
      ["sources", "All sources", "layers"],
      ["telegram", "Telegram", "send"],
      ["forums", "Dark forums", "globe"],
      ["twitter", "X / Twitter", "pulse"],
      ["facebook", "Facebook", "users"],
      ["instagram", "Instagram", "scan"],
      ["connections", "Connections", "settings"],
    ],
  },
];
const descriptions: Partial<Record<View, string>> = {
  overview: "Connect the signals. Understand the threat.",
  signals: "Collected content with its source, context and review status.",
  watchlists: "Give your investigations a focus, not just a keyword.",
  discovery:
    "Find candidate sources by the conversations happening inside them.",
  qualification: "Inspect content relevance before deciding what to monitor.",
  tracing: "Follow visible forwarding evidence. Never invent missing hops.",
  iocs: "Extracted observables are a starting point, not proof of compromise.",
  stix: "Portable intelligence, with context and provenance preserved.",
  confidence: "Evidence strength is not the probability of maliciousness.",
  risk: "Explainable review priorities, not a guarantee of compromise.",
  attack: "Technique coverage supported by the selected dataset.",
  correlation:
    "Explore source relationships without assuming a shared attacker.",
  noise: "Less repetition. More context. A clearer signal.",
  rules: "Author detection drafts. Validate before deploying.",
  siem: "An auditable handoff from intelligence to detection.",
  review: "Human review is the last mile of reliable intelligence.",
  report: "A concise, exportable snapshot of this workspace.",
  sources: "Collection coverage and observable yield in one place.",
  connections: "Your existing collector services, in one workspace.",
};
const paths: Record<string, ReactNode> = {
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z" />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </>
  ),
  pulse: <path d="M2 12h4l3-7 5 14 3-7h5" />,
  target: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" />
    </>
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m16 8-2 6-6 2 2-6Z" />
    </>
  ),
  scan: (
    <>
      <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M3 12h18" />
    </>
  ),
  check: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  branch: (
    <>
      <circle cx="6" cy="5" r="2" />
      <circle cx="6" cy="19" r="2" />
      <circle cx="18" cy="5" r="2" />
      <path d="M6 7v10m0-4c8 0 12-1 12-6" />
    </>
  ),
  filter: <path d="M3 5h18l-7 8v6l-4 2v-8Z" />,
  layers: (
    <>
      <path d="m3 8 9-5 9 5-9 5Zm0 5 9 5 9-5m-18 5 9 5 9-5" />
    </>
  ),
  network: (
    <>
      <circle cx="12" cy="5" r="3" />
      <circle cx="5" cy="19" r="3" />
      <circle cx="19" cy="19" r="3" />
      <path d="m10 8-4 8m8-8 4 8M8 19h8" />
    </>
  ),
  cube: (
    <>
      <path d="m12 2 9 5v10l-9 5-9-5V7Zm0 10v10M3 7l9 5 9-5M7 5l10 5" />
    </>
  ),
  code: (
    <>
      <path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-14-2 18" />
    </>
  ),
  send: (
    <>
      <path d="m3 3 19 8-8 3-3 8Z" />
      <path d="m3 3 11 11" />
    </>
  ),
  file: (
    <>
      <path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8m-8 4h6" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <ellipse cx="12" cy="12" rx="4" ry="9" />
      <path d="M3 12h18" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 21v-3a6 6 0 0 1 12 0v3m0-16a3 3 0 0 1 0 6m3 3c3 0 3 4 3 7" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h16M4 17h16" />
      <circle cx="8" cy="7" r="3" />
      <circle cx="16" cy="17" r="3" />
    </>
  ),
  search: (
    <>
      <circle cx="10" cy="10" r="6" />
      <path d="m15 15 5 5" />
    </>
  ),
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  down: <path d="m7 10 5 5 5-5" />,
  plus: <path d="M12 4v16M4 12h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  download: (
    <>
      <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />
    </>
  ),
  bell: (
    <>
      <path d="M5 17h14l-2-4V9A5 5 0 0 0 7 9v4Zm5 3h4" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 6v6l4 2" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 7v5h-5M4 17v-5h5M5 7a8 8 0 0 1 13-2l2 3M4 16l2 3a8 8 0 0 0 13-2" />
    </>
  ),
  bolt: <path d="m13 2-9 12h7l-1 8 10-13h-7Z" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  pause: (
    <>
      <path d="M8 5v14M16 5v14" />
    </>
  ),
  play: <path d="m7 4 14 8-14 8Z" />,
};
function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.shield}
    </svg>
  );
}
function Pill({ children, tone = "" }: { children: ReactNode; tone?: string }) {
  return <span className={`rt-pill ${tone}`}>{children}</span>;
}
function Button({
  children,
  onClick,
  primary,
  icon,
  disabled = false,
}: {
  children: ReactNode;
  onClick?: () => void;
  primary?: boolean;
  icon?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={`rt-btn ${primary ? "rt-primary" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {icon && <Icon name={icon} size={16} />}
      {children}
    </button>
  );
}
function Panel({
  title,
  sub,
  action,
  children,
  className = "",
}: {
  title?: string;
  sub?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rt-panel ${className}`}>
      {title && (
        <header className="rt-panel-head">
          <div>
            <h2>{title}</h2>
            {sub && <p>{sub}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
function Empty({
  title = "No records in this view",
  text = "Try another time range or connect a collection source.",
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="rt-empty">
      <Icon name="layers" size={32} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
function Score({
  value,
  color = "var(--rt-purple)",
}: {
  value: number | null;
  color?: string;
}) {
  return value === null ? (
    <span className="rt-muted">Not scored</span>
  ) : (
    <span className="rt-score">
      <b>{value}</b>
      <span>
        <i style={{ width: `${Math.min(100, value)}%`, background: color }} />
      </span>
    </span>
  );
}
function timeAgo(date: string) {
  const m = Math.max(0, Math.floor((Date.now() - Date.parse(date)) / 60000));
  return !Number.isFinite(m)
    ? "Unknown time"
    : m < 60
      ? `${m}m ago`
      : m < 1440
        ? `${Math.floor(m / 60)}h ago`
        : `${Math.floor(m / 1440)}d ago`;
}
function Stat({
  label,
  value,
  sub,
  icon,
  index = 0,
}: {
  label: string;
  value: number | string;
  sub: string;
  icon: string;
  index?: number;
}) {
  return (
    <article className="rt-stat" style={{ "--i": index } as CSSProperties}>
      <div className="rt-stat-label">
        {label}
        <span>
          <Icon name={icon} />
        </span>
      </div>
      <strong>
        <CountUp value={value} />
      </strong>
      <div className="rt-stat-foot">
        <Icon name="clock" size={11} />
        {sub}
      </div>
    </article>
  );
}
function Orbit({ motion }: { motion: boolean }) {
  const dots: { x: number; y: number; opacity: number; radius: number }[] = [];
  for (let lat = -80; lat <= 80; lat += 8) {
    for (let lon = -88; lon <= 88; lon += 8) {
      const phi = (lat * Math.PI) / 180,
        theta = (lon * Math.PI) / 180;
      const depth = Math.cos(phi) * Math.cos(theta);
      dots.push({
        x: 240 + 150 * Math.cos(phi) * Math.sin(theta),
        y: 175 + 150 * Math.sin(phi),
        opacity: 0.13 + depth * 0.52,
        radius: depth > 0.75 ? 1.65 : 1,
      });
    }
  }
  return (
    <div className="rt-globe-scene" aria-hidden="true">
      <TelemetryGlobe running={motion} />
      <svg className="rt-globe" viewBox="0 0 480 350" fill="none">
        <defs>
          <radialGradient id="globe-light" cx=".35" cy=".3" r=".75">
            <stop stopColor="#8bbb92" stopOpacity=".3" />
            <stop offset=".7" stopColor="#368a65" stopOpacity=".1" />
            <stop offset="1" stopColor="#0c3133" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="route-light">
            <stop stopColor="#b0d0b5" stopOpacity="0" />
            <stop offset=".55" stopColor="#f2f7f3" />
            <stop offset="1" stopColor="#dfece1" />
          </linearGradient>
          <filter id="node-glow">
            <feGaussianBlur stdDeviation="4" />
          </filter>
        </defs>
        <circle
          cx="240"
          cy="175"
          r="150"
          fill="url(#globe-light)"
          stroke="#cde2d0"
          strokeOpacity=".14"
        />
        <g className="rt-globe-lattice">
          {dots.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={p.radius}
              fill="#dfece1"
              opacity={p.opacity}
            />
          ))}
        </g>
        <ellipse
          cx="240"
          cy="175"
          rx="177"
          ry="55"
          stroke="#d9e8db"
          strokeOpacity=".17"
          transform="rotate(-30 240 175)"
        />
        <ellipse
          cx="240"
          cy="175"
          rx="172"
          ry="58"
          stroke="#d9e8db"
          strokeOpacity=".13"
          transform="rotate(38 240 175)"
        />
        <path
          className="rt-globe-route"
          d="M119 224 Q230 -15 348 127 M170 94 Q323 114 312 278 M119 224 Q285 317 348 127"
          stroke="url(#route-light)"
          strokeWidth="1.4"
        />
        <path
          className="rt-packet-route"
          d="M119 224 Q230 -15 348 127"
          stroke="#8bbb92"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <path
          className="rt-packet-route packet-two"
          d="M170 94 Q323 114 312 278"
          stroke="#8bbb92"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle
          className="rt-globe-scan"
          cx="240"
          cy="175"
          r="154"
          stroke="#8bbb92"
          strokeWidth="1"
          strokeDasharray="45 922"
        />
        {[
          [119, 224],
          [170, 94],
          [348, 127],
          [312, 278],
        ].map(([x, y], i) => (
          <g
            key={x}
            className="rt-globe-beacon"
            style={{ animationDelay: `${i * 0.7}s` }}
          >
            <circle
              cx={x}
              cy={y}
              r="11"
              fill="#f2f7f3"
              opacity=".45"
              filter="url(#node-glow)"
            />
            <circle cx={x} cy={y} r="6" stroke="#f2f7f3" strokeOpacity=".5" />
            <circle cx={x} cy={y} r="2.5" fill="#f2f7f3" />
          </g>
        ))}
      </svg>
      <div className="rt-globe-caption gc-top">
        <span className="rt-caption-icon">
          <Icon name="network" size={16} />
        </span>
        <div>
          <b>Connected intelligence</b>
          <small>Signals become context</small>
        </div>
      </div>
      <div className="rt-globe-caption gc-bottom">
        <Icon name="check" size={15} />
        <span>Evidence, not assumptions.</span>
      </div>
    </div>
  );
}
function ActivityChart({ signals, days }: { signals: Signal[]; days: number }) {
  const [active, setActive] = useState<number | null>(null);
  const buckets = Array.from(
    { length: days === 1 ? 12 : days === 7 ? 7 : 10 },
    (_, i) => i,
  );
  const now = Date.now(),
    start = now - days * 86400000,
    span = (days * 86400000) / buckets.length;
  const values = buckets.map(
    (i) =>
      signals.filter(
        (s) =>
          Date.parse(s.date) >= start + i * span &&
          Date.parse(s.date) < start + (i + 1) * span,
      ).length,
  );
  const max = Math.max(...values, 4),
    W = 640,
    H = 178;
  const pts = values.map((v, i) => ({
    x: 36 + (i * (W - 52)) / (values.length - 1),
    y: 22 + ((max - v) / max) * (H - 38),
  }));
  const line = pts
    .map((p, i) =>
      i
        ? `C ${pts[i - 1].x + 28} ${pts[i - 1].y}, ${p.x - 28} ${p.y}, ${p.x} ${p.y}`
        : `M ${p.x} ${p.y}`,
    )
    .join(" ");
  const priorityValues = buckets.map(
    (i) =>
      signals.filter(
        (s) =>
          ["High", "Critical"].includes(s.severity) &&
          Date.parse(s.date) >= start + i * span &&
          Date.parse(s.date) < start + (i + 1) * span,
      ).length,
  );
  const priorityPoints = priorityValues.map((v, i) => ({
    x: pts[i].x,
    y: 22 + ((max - v) / max) * (H - 38),
  }));
  const priorityLine = priorityPoints
    .map((p, i) =>
      i
        ? `C ${priorityPoints[i - 1].x + 28} ${priorityPoints[i - 1].y}, ${p.x - 28} ${p.y}, ${p.x} ${p.y}`
        : `M ${p.x} ${p.y}`,
    )
    .join(" ");
  return (
    <div className="rt-chart">
      <div className="rt-chart-summary">
        <strong>
          {signals.length}
          <small> signals</small>
        </strong>
        <span>
          <i className="rt-dot" /> All signals
          <i className="rt-dot rt-priority-dot" /> High priority
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H + 38}`}
        role="img"
        aria-label={`${signals.length} signals across the last ${days} days`}
      >
        <defs>
          <linearGradient id="activity-fill" x1="0" x2="0" y1="0" y2="1">
            <stop stopColor="#ecf4ed" stopOpacity=".35" />
            <stop offset="1" stopColor="#ecf4ed" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <line
              x1="36"
              x2={W - 10}
              y1={22 + i * 47}
              y2={22 + i * 47}
              stroke="#dae9dd"
              strokeDasharray="3 5"
            />
            <text x="0" y={26 + i * 47} fill="#579d77" fontSize="10">
              {Math.round(max * (1 - i / 3))}
            </text>
          </g>
        ))}
        <path
          d={`${line} L ${pts.at(-1)?.x} ${H} L 36 ${H} Z`}
          fill="url(#activity-fill)"
        />
        <path
          className="rt-draw-line"
          d={line}
          fill="none"
          stroke="#abceb0"
          strokeWidth="2.5"
        />
        <path
          className="rt-priority-line"
          d={priorityLine}
          fill="none"
          stroke="#85b78f"
          strokeWidth="1.8"
          strokeDasharray="4 5"
        />
        {pts.map((p, i) => (
          <g
            key={i}
            tabIndex={0}
            role="button"
            aria-label={`${new Date(start + i * span).toLocaleDateString("en-GB", { month: "short", day: "numeric" })}: ${values[i]} signals`}
            onFocus={() => setActive(i)}
            onBlur={() => setActive(null)}
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
          >
            <rect x={p.x - 20} y="5" width="40" height={H} fill="transparent" />
            <circle
              cx={p.x}
              cy={p.y}
              r={active === i ? 6 : 3}
              fill="#abceb0"
              stroke="#ffffff"
              strokeWidth="3"
            />
            <text
              x={p.x}
              y={H + 26}
              textAnchor="middle"
              fill="#67a67f"
              fontSize="10"
            >
              {days === 1
                ? new Date(start + i * span).getHours() + ":00"
                : new Date(start + i * span).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                  })}
            </text>
          </g>
        ))}
        {active !== null && (
          <g pointerEvents="none">
            <rect
              x={Math.min(pts[active].x - 38, W - 90)}
              y="0"
              width="80"
              height="25"
              rx="7"
              fill="#175d52"
            />
            <text
              x={Math.min(pts[active].x + 2, W - 50)}
              y="17"
              fill="#f2f7f3"
              fontSize="11"
              textAnchor="middle"
            >
              {values[active]} signals
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}
function SourceDonut({ signals }: { signals: Signal[] }) {
  const data = countsBy(signals, (s) => s.platform);
  let cumulative = 0;
  const stops = data
    .map(([p, n]) => {
      const a = cumulative;
      cumulative += (n / Math.max(signals.length, 1)) * 100;
      return `${platformColors[p] || "#dae9dd"} ${a}% ${cumulative}%`;
    })
    .join(",");
  return (
    <div className="rt-source-chart">
      <div
        className="rt-donut"
        style={{
          background: signals.length
            ? `conic-gradient(from -90deg, ${stops})`
            : "#114d49",
        }}
        role="img"
        aria-label={data.map(([p, n]) => `${p}: ${n}`).join(",")}
      >
        <div>
          <strong>{data.length}</strong>
          <span>platforms</span>
        </div>
      </div>
      <div className="rt-legend">
        {data.map(([p, n]) => (
          <div key={p}>
            <span>
              <i style={{ background: platformColors[p] || "#dae9dd" }} />
              {p}
            </span>
            <b>{n}</b>
            <small>{Math.round((n / signals.length) * 100)}%</small>
          </div>
        ))}
      </div>
    </div>
  );
}
function Dialog({
  detail,
  close,
}: {
  detail: NonNullable<Detail>;
  close: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "Tab") {
        const els = ref.current?.querySelectorAll<HTMLElement>(
          'button,input,select,textarea,[tabindex="0"]',
        );
        if (!els?.length) return;
        const first = els[0],
          last = els[els.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handle);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handle);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [close]);
  return (
    <div className="rt-modal-backdrop" onClick={close}>
      <div
        ref={ref}
        tabIndex={-1}
        className="rt-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <span className="rt-eyebrow">{detail.label}</span>
          <button
            className="rt-icon-btn"
            aria-label="Close details"
            onClick={close}
          >
            <Icon name="close" />
          </button>
        </header>
        <h2 id="detail-title">{detail.title}</h2>
        <div className="rt-dialog-body">{detail.body}</div>
      </div>
    </div>
  );
}
function WatchForm({ save }: { save: (w: Watch) => void }) {
  const [name, setName] = useState(""),
    [domain, setDomain] = useState(""),
    [keywords, setKeywords] = useState("");
  return (
    <form
      className="rt-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim() && keywords.trim())
          save({
            name: name.trim(),
            domain: domain.trim(),
            keywords: keywords.trim(),
            enabled: true,
          });
      }}
    >
      <label>
        Organization or investigation
        <input
          required
          maxLength={80}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Aster Bank"
        />
      </label>
      <label>
        Domain or identifier
        <input
          maxLength={120}
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="aster.example"
        />
      </label>
      <label>
        Aliases and context keywords
        <textarea
          required
          maxLength={500}
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="Brand aliases, exposure claims, access-sale context…"
        />
      </label>
      <p className="rt-notice">
        This demo watchlist is saved only in this browser. It does not start
        crawlers or join channels.
      </p>
      <button className="rt-btn rt-primary" type="submit">
        Save demo watchlist <Icon name="arrow" size={16} />
      </button>
    </form>
  );
}

export default function IntelligenceConsole() {
  const [view, setView] = useState<View>("overview"),
    [demo, setDemo] = useState(true),
    [ready, setReady] = useState(false),
    [days, setDays] = useState(7),
    [query, setQuery] = useState(""),
    [platform, setPlatform] = useState("All platforms"),
    [motion, setMotion] = useState(true),
    [mobile, setMobile] = useState(false);
  const [data, setData] = useState<DataSet>(emptyData),
    [urls, setUrls] = useState<URLs>(defaults),
    [busy, setBusy] = useState(false),
    [detail, setDetail] = useState<Detail>(null),
    [toast, setToast] = useState(""),
    [refresh, setRefresh] = useState(0);
  const [watches, setWatches] = useState<Watch[]>(initialWatches),
    [candidates, setCandidates] = useState<Candidate[]>(initialCandidates),
    [reviews, setReviews] = useState<Record<string, string>>({}),
    [noiseFilter, setNoiseFilter] = useState("All decisions");
  const [ruleType, setRuleType] = useState("Sigma"),
    [ruleName, setRuleName] = useState("Network observable review"),
    [ruleValue, setRuleValue] = useState("203.0.113.42");
  const searchRef = useRef<HTMLInputElement>(null);
  const agencyMotion = useAgencyMotion(view, ready, busy, motion);
  useEffect(() => {
    try {
      const u = localStorage.getItem("redtraces-ai-collector-urls");
      if (u) setUrls({ ...defaults, ...JSON.parse(u) });
      const d = localStorage.getItem("redtraces-demo-mode");
      if (d) setDemo(d !== "false");
      const w = localStorage.getItem("redtraces-demo-watches");
      if (w) setWatches(JSON.parse(w));
      const c = localStorage.getItem("redtraces-demo-candidates");
      if (c) setCandidates(JSON.parse(c));
      const r = localStorage.getItem("redtraces-demo-reviews");
      if (r) setReviews(JSON.parse(r));
      setMotion(
        localStorage.getItem("redtraces-motion") !== "false" &&
          !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      );
    } catch {}
    setReady(true);
  }, []);
  useEffect(() => {
    if (ready) {
      localStorage.setItem("redtraces-demo-watches", JSON.stringify(watches));
      localStorage.setItem(
        "redtraces-demo-candidates",
        JSON.stringify(candidates),
      );
      localStorage.setItem("redtraces-demo-reviews", JSON.stringify(reviews));
    }
  }, [watches, candidates, reviews, ready]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (!ready) return;
    let alive = true;
    const controller = new AbortController();
    setBusy(true);
    setData(emptyData());
    if (demo) {
      setData(makeDemo());
      setBusy(false);
      return;
    }
    const next = emptyData();
    const get = async (path: string, label: string) => {
      try {
        const res = await fetch(path, {
          signal: AbortSignal.any([
            controller.signal,
            AbortSignal.timeout(8000),
          ]),
        });
        if (!res.ok) throw Error(String(res.status));
        return await res.json();
      } catch {
        if (!controller.signal.aborted) next.errors.push(label);
        return null;
      }
    };
    const core = urls.telegram.replace(/\/$/, "");
    Promise.all([
      get(`${core}/api/messages?limit=200`, "Telegram signals"),
      get(`${core}/api/intelligence/iocs?limit=1000`, "IOC store"),
      get(`${core}/api/artifacts`, "Artifacts"),
      get(`${core}/api/layer2/metrics`, "Noise metrics"),
      get(`${core}/api/siem/push-log`, "SIEM log"),
      ...(["forums", "twitter", "facebook", "instagram"] as Source[]).map((s) =>
        get(
          urls[s].replace(/\/$/, "") +
            (s === "forums"
              ? "/api/data?limit=150&period=all"
              : "/leaks?limit=1000"),
          s,
        ),
      ),
    ]).then(([messages, iocs, artifacts, noise, siem, ...social]) => {
      type Row = Record<string, unknown>;
      const normalize = (r: Row, p: string, i: number): Signal => {
        const metadata =
          r.metadata && typeof r.metadata === "object"
            ? (r.metadata as Row)
            : {};
        const iocs =
          metadata.iocs && typeof metadata.iocs === "object"
            ? (metadata.iocs as Row)
            : {};
        const extracted = Object.values(iocs).flatMap((v) =>
          Array.isArray(v)
            ? v.filter((item): item is string => typeof item === "string")
            : [],
        );
        return {
          id: `${p}-${String(r.id ?? i)}`,
          title: String(
            r.title ??
              r.page_title ??
              r.raw_text ??
              r.text ??
              r.content ??
              r.content_snippet ??
              r.message ??
              r.description ??
              "Collected post",
          ).slice(0, 110),
          text: String(
            r.raw_text ??
              r.text ??
              r.content ??
              r.content_snippet ??
              r.message ??
              r.description ??
              r.title ??
              "",
          ),
          source: String(
            r.source ??
              r.url ??
              r.channel ??
              r.channel_name ??
              r.username ??
              r.platform ??
              p,
          ),
          platform: p,
          date: String(
            r.posted_at ??
              r.message_date ??
              r.collected_at ??
              r.processed_at ??
              r.timestamp ??
              r.first_seen_utc ??
              r.created_at ??
              r.date ??
              "",
          ),
          severity: String(r.severity ?? "Unrated"),
          score: null,
          status: "Unreviewed",
          topic: "Collected content",
          indicators: extracted,
          forwardedFrom: undefined,
        };
      };
      next.signals = (messages?.items || []).map((r: Row, i: number) =>
        normalize(
          r,
          String(r.platform || "Telegram").replace(/^telegram$/, "Telegram"),
          i,
        ),
      );
      social.forEach((d, i) => {
        const rows = Array.isArray(d) ? d : d?.alerts || [];
        next.signals.push(
          ...rows.map((r: Row, j: number) =>
            normalize(r, ["Dark web", "X", "Facebook", "Instagram"][i], j),
          ),
        );
      });
      next.indicators = (iocs?.items || []).map((r: Row) => ({
        id: String(r.stix_id),
        value: String(r.ioc_value),
        type: String(r.ioc_type),
        sightings: Number(r.sighting_count || 0),
        source: String(r.source_id || "Unknown"),
        date: String(r.last_seen || ""),
        score: null,
        confidence: null,
      }));
      next.artifacts = (artifacts?.items || []).map((r: Row) => ({
        name: String(r.name),
        type: String(r.artifact_type),
        status: String(r.status),
        size: Number(r.size_bytes),
      }));
      next.deployments = siem?.items || [];
      if (noise?.available) next.noise = noise;
      next.loaded = true;
      if (alive) {
        setData(next);
        setBusy(false);
      }
    });
    return () => {
      alive = false;
      controller.abort();
    };
  }, [demo, ready, urls, refresh]);
  const notify = (s: string) => setToast(s);
  const go = (v: View) => {
    setView(v);
    setMobile(false);
    setQuery("");
    setPlatform("All platforms");
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const setMode = (d: boolean) => {
    setDemo(d);
    localStorage.setItem("redtraces-demo-mode", String(d));
    setQuery("");
    setDetail(null);
  };
  const baseSignals = useMemo(
    () => filterPeriod(data.signals, days),
    [data.signals, days],
  );
  const signals = baseSignals.filter(
    (s) =>
      (platform === "All platforms" || s.platform === platform) &&
      `${s.title} ${s.text} ${s.source} ${s.id}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const indicators = filterPeriod(data.indicators, days).filter((i) =>
    `${i.value} ${i.type} ${i.source}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const sources = countsBy(signals, (s) => s.source);
  const high = signals.filter(
    (s) => s.severity === "High" || s.severity === "Critical",
  ).length;
  const label =
    menu.flatMap((m) => m.items).find((x) => x[0] === view)?.[1] || view;
  const detailSignal = (s: Signal) =>
    setDetail({
      title: s.title,
      label: `${demo ? "SYNTHETIC DEMO" : "COLLECTED EVIDENCE"} · ${s.id}`,
      body: (
        <>
          <div className="rt-row rt-gap">
            <Pill tone={s.severity.toLowerCase()}>{s.severity}</Pill>
            <Pill>{s.platform}</Pill>
            <Pill>{reviews[s.id] || s.status}</Pill>
          </div>
          <p className="rt-evidence-text">{s.text}</p>
          <dl className="rt-dl">
            <dt>Source</dt>
            <dd>{s.source}</dd>
            <dt>Observed</dt>
            <dd>{s.date ? new Date(s.date).toLocaleString() : "Unknown"}</dd>
            <dt>Source claim</dt>
            <dd>Not independently verified</dd>
            <dt>Relevance score</dt>
            <dd>
              {s.score ?? "Unavailable"}
              {s.score !== null ? " / 100 · simulated" : ""}
            </dd>
            <dt>Forward origin</dt>
            <dd>{s.forwardedFrom || "Not available in this record"}</dd>
          </dl>
          <h3>Extracted observables</h3>
          {s.indicators.length ? (
            s.indicators.map((i) => (
              <code className="rt-code-chip" key={i}>
                {i}
              </code>
            ))
          ) : (
            <p className="rt-muted">
              No associated observable values supplied.
            </p>
          )}
          <p className="rt-notice">
            A relevant post or repeated claim is not proof of a breach. Verify
            context and provenance before taking action.
          </p>
          {demo && (
            <div className="rt-row rt-gap">
              <Button
                primary
                icon="check"
                onClick={() => {
                  setReviews((r) => ({ ...r, [s.id]: "Reviewed" }));
                  setDetail(null);
                  notify("Demo evidence marked as reviewed.");
                }}
              >
                Mark reviewed
              </Button>
              <Button
                onClick={() => {
                  setReviews((r) => ({ ...r, [s.id]: "Dismissed" }));
                  setDetail(null);
                  notify("Demo evidence dismissed.");
                }}
              >
                Dismiss
              </Button>
            </div>
          )}
        </>
      ),
    });
  const signalTable = (rows: Signal[], compact = false) => (
    <div className="rt-table-wrap">
      <table className="rt-table">
        <thead>
          <tr>
            <th>Signal / context</th>
            <th>Source</th>
            <th>Priority</th>
            {!compact && <th>Observed</th>}
            <th>
              <span className="rt-sr">Details</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td>
                <button
                  className="rt-title-link"
                  onClick={() => detailSignal(s)}
                >
                  {s.title}
                </button>
                <small>
                  {s.id} <span>·</span> {reviews[s.id] || s.status}
                </small>
              </td>
              <td>
                <span
                  className="rt-source-dot"
                  style={
                    {
                      "--source": platformColors[s.platform] || "#ebf3ec",
                    } as CSSProperties
                  }
                />
                {s.platform}
                <small>{s.source}</small>
              </td>
              <td>
                <Pill tone={s.severity.toLowerCase()}>{s.severity}</Pill>
              </td>
              {!compact && <td className="rt-muted">{timeAgo(s.date)}</td>}
              <td>
                <button
                  className="rt-icon-btn"
                  aria-label={`Inspect ${s.id}`}
                  onClick={() => detailSignal(s)}
                >
                  <Icon name="arrow" size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <Empty />}
    </div>
  );
  const exportReport = () => {
    downloadFile(
      `redtraces-${demo ? "demo" : "live"}-report.json`,
      JSON.stringify(
        {
          mode: demo ? "synthetic-demo" : "live",
          generated_at: new Date().toISOString(),
          range_days: days,
          scope:
            "Currently loaded records filtered by time and search; not the entire database",
          signals,
          indicators,
          artifacts: data.artifacts,
        },
        null,
        2,
      ),
    );
    notify("Report exported with its data mode and scope.");
  };
  const demoOnly = (body: ReactNode) =>
    demo ? (
      body
    ) : (
      <Panel>
        <Empty
          title="No live records are exposed for this module"
          text="The connected API does not currently provide this workflow. Switch to Demo to explore it; no sample results are mixed into live data."
        />
      </Panel>
    );
  const candidateCards = () => (
    <div className="rt-card-grid">
      {candidates
        .filter((c) =>
          `${c.name} ${c.reason}`.toLowerCase().includes(query.toLowerCase()),
        )
        .map((c) => (
          <Panel key={c.name} className="rt-candidate">
            <div className="rt-row rt-between">
              <span
                className="rt-source-icon"
                style={{ color: platformColors[c.platform] }}
              >
                <Icon
                  name={c.platform === "Telegram" ? "send" : "globe"}
                  size={22}
                />
              </span>
              <Pill tone={c.state === "Rejected" ? "low" : "purple"}>
                {c.state}
              </Pill>
            </div>
            <h3>{c.name}</h3>
            <p>{c.reason}</p>
            <div className="rt-candidate-score">
              <span>Content relevance</span>
              <Score value={c.score} />
            </div>
            <div className="rt-row rt-between rt-muted">
              <span>
                {c.relevant} relevant / {c.posts} sampled posts
              </span>
              <span>{c.platform}</span>
            </div>
            <div className="rt-row rt-gap rt-card-actions">
              <Button
                primary
                disabled={c.state === "Monitoring"}
                icon="plus"
                onClick={() => {
                  setCandidates((a) =>
                    a.map((x) =>
                      x.name === c.name ? { ...x, state: "Monitoring" } : x,
                    ),
                  );
                  notify("Demo source retained. No real channel was joined.");
                }}
              >
                Retain source
              </Button>
              <Button
                disabled={c.state === "Rejected"}
                onClick={() => {
                  setCandidates((a) =>
                    a.map((x) =>
                      x.name === c.name ? { ...x, state: "Rejected" } : x,
                    ),
                  );
                  notify("Demo source rejected.");
                }}
              >
                Reject
              </Button>
            </div>
          </Panel>
        ))}
    </div>
  );
  let content: ReactNode;
  if (view === "overview")
    content = (
      <>
        <section className="rt-hero">
          <div className="rt-hero-copy">
            <span className="rt-eyebrow">
              <i className="rt-dot" /> THE INTELLIGENCE ADVANTAGE
            </span>
            <h2>
              <span className="rt-hero-line">Less noise.</span>
              <span className="rt-hero-line"><em>More perspective.</em></span>
            </h2>
            <p className="rt-hero-description">
              Bring scattered signals into focus. Discover what matters, connect
              the evidence, and move your investigation forward.
            </p>
            <div className="rt-row rt-gap rt-hero-actions">
              <span className="rt-magnetic">
              <Button primary icon="compass" onClick={() => go("discovery")}>
                Start exploring
              </Button>
              </span>
              <button className="rt-text-btn" onClick={() => go("watchlists")}>
                Manage watchlists <Icon name="arrow" size={16} />
              </button>
            </div>
            <div className="rt-hero-meta">
              <span>
                <Icon name="shield" size={13} /> Evidence-led analysis
              </span>
              <span>
                <Icon name="globe" size={13} /> Cross-platform context
              </span>
            </div>
          </div>
          <div className="rt-portrait-reveal">
            <div className="rt-portrait-parallax" data-parallax>
              <img src="/images/cyber-portrait.jpg" width="1500" height="1128" alt="White cybernetic portrait with precision mechanical details" fetchPriority="high" decoding="async" />
            </div>
            <span className="rt-image-credit">GABRIELE MALASPINA / UNSPLASH</span>
            <span className="rt-art-caption">HUMAN INSIGHT.<br/>MACHINE PRECISION.</span>
          </div>
        </section>
        <div className="rt-stats">
          <Stat
            label="Collected signals"
            value={signals.length}
            sub={`In the last ${days} ${days === 1 ? "day" : "days"}`}
            icon="pulse"
            index={0}
          />
          <Stat
            label="High-priority signals"
            value={high}
            sub="Ready for analyst review"
            icon="shield"
            index={1}
          />
          <Stat
            label="Extracted observables"
            value={indicators.length}
            sub="Context verification required"
            icon="scan"
            index={2}
          />
          <Stat
            label="Observed sources"
            value={sources.length}
            sub="In the selected signal set"
            icon="network"
            index={3}
          />
        </div>
        <div className="rt-chart-grid">
          <Panel
            title="Signal activity"
            sub="Your collection footprint over time"
            action={
              <Pill>
                Last {days} {days === 1 ? "day" : "days"}
              </Pill>
            }
          >
            <ActivityChart signals={signals} days={days} />
          </Panel>
          <Panel
            title="Source distribution"
            sub="Where your intelligence comes from"
            action={<Icon name="globe" />}
          >
            <SourceDonut signals={signals} />
          </Panel>
        </div>
        <div className="rt-lower-grid">
          <Panel
            title="Signals worth a closer look"
            sub={
              demo
                ? "Synthetic scenarios · unverified claims"
                : "Loaded evidence · review before action"
            }
            action={
              <button className="rt-text-btn" onClick={() => go("signals")}>
                View all <Icon name="arrow" size={14} />
              </button>
            }
          >
            {signalTable(signals.slice(0, 4), true)}
          </Panel>
          <Panel
            title="Investigation focus"
            sub="Turn monitoring into a mission"
            className="rt-focus-panel"
          >
            {(demo ? watches.filter((w) => w.enabled) : [])
              .slice(0, 3)
              .map((w, i) => (
                <button
                  key={w.name}
                  className="rt-focus-item"
                  onClick={() => {
                    go("signals");
                    setQuery(w.name.split(" ")[0]);
                  }}
                >
                  <span className="rt-focus-avatar">
                    {w.name
                      .split(" ")
                      .map((s) => s[0])
                      .join("")
                      .slice(0, 2)}
                  </span>
                  <span>
                    <b>{w.name}</b>
                    <small>
                      {
                        signals.filter((s) =>
                          (s.title + " " + s.text)
                            .toLowerCase()
                            .includes(w.name.toLowerCase()),
                        ).length
                      }{" "}
                      matching signals
                    </small>
                  </span>
                  <Icon name="arrow" size={15} />
                </button>
              ))}
            {!demo && (
              <p className="rt-muted">
                Live watchlist execution is not connected.
              </p>
            )}
            <button className="rt-add-focus" onClick={() => go("watchlists")}>
              <Icon name="plus" size={16} /> Create a focused watchlist
            </button>
          </Panel>
        </div>
        <IntelligenceStory motion={agencyMotion} onNavigate={(next)=>go(next as View)} />
      </>
    );
  else if (view === "signals")
    content = (
      <Panel
        title="Collected signals"
        sub={`${signals.length} records in this view`}
        action={
          <select
            aria-label="Filter by platform"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
          >
            <option>All platforms</option>
            {Object.keys(platformColors).map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        }
      >
        {signalTable(signals)}
      </Panel>
    );
  else if (view === "watchlists")
    content = demoOnly(
      <>
        <div className="rt-inline-note">
          <Icon name="target" />
          <span>
            Watchlists capture organizations, aliases and context. Demo changes
            are browser-local.
          </span>
          <Button
            primary
            icon="plus"
            onClick={() =>
              setDetail({
                title: "New target watchlist",
                label: "FOCUSED MONITORING · DEMO",
                body: (
                  <WatchForm
                    save={(w) => {
                      setWatches((a) => [...a, w]);
                      setDetail(null);
                      notify("Demo watchlist saved.");
                    }}
                  />
                ),
              })
            }
          >
            New watchlist
          </Button>
        </div>
        <div className="rt-card-grid">
          {watches.map((w, i) => (
            <Panel key={i} className="rt-watch-card">
              <div className="rt-row rt-between">
                <span className="rt-focus-avatar">
                  {w.name.slice(0, 2).toUpperCase()}
                </span>
                <button
                  role="switch"
                  aria-checked={w.enabled}
                  aria-label={`Enable ${w.name}`}
                  className={`rt-switch ${w.enabled ? "on" : ""}`}
                  onClick={() =>
                    setWatches((a) =>
                      a.map((v, j) =>
                        j === i ? { ...v, enabled: !v.enabled } : v,
                      ),
                    )
                  }
                >
                  <i />
                </button>
              </div>
              <h3>{w.name}</h3>
              <code>{w.domain || "No domain specified"}</code>
              <p>{w.keywords}</p>
              <div className="rt-row rt-between">
                <Pill tone={w.enabled ? "purple" : ""}>
                  {w.enabled ? "Monitoring · demo" : "Paused"}
                </Pill>
                <button
                  className="rt-text-btn"
                  onClick={() => {
                    go("signals");
                    setQuery(w.name.split(" ")[0]);
                  }}
                >
                  View signals <Icon name="arrow" size={14} />
                </button>
              </div>
            </Panel>
          ))}
        </div>
      </>,
    );
  else if (view === "discovery" || view === "qualification")
    content = demoOnly(
      <>
        <section className="rt-pipeline">
          {[
            ["target", "Define scope", "Aliases + context"],
            ["search", "Discover sources", "Public candidate feeds"],
            ["filter", "Sample content", "Relevance over names"],
            ["check", "Retain & monitor", "Review-backed decisions"],
          ].map((s, i) => (
            <div key={s[1]}>
              <span>0{i + 1}</span>
              <Icon name={s[0]} size={23} />
              <h3>{s[1]}</h3>
              <p>{s[2]}</p>
              {i < 3 && <Icon name="arrow" />}
            </div>
          ))}
        </section>
        <div className="rt-inline-note">
          <Icon name="compass" />
          <span>
            Simulated qualification. Scores reflect sample content, not the
            channel name. Real joining remains disabled.
          </span>
          <Button
            icon="refresh"
            onClick={() => {
              setCandidates(initialCandidates);
              notify("Demo candidate sample reset. No network discovery ran.");
            }}
          >
            Reset sample
          </Button>
        </div>
        {candidateCards()}
      </>,
    );
  else if (["iocs", "confidence", "risk", "stix"].includes(view))
    content = (
      <>
        <div className="rt-stats three">
          <Stat
            label="Loaded observables"
            value={indicators.length}
            sub="Filtered by selected date range"
            icon="scan"
          />
          <Stat
            label="Recorded sightings"
            value={indicators.reduce((a, i) => a + i.sightings, 0)}
            sub="Repeated observations included"
            icon="layers"
            index={1}
          />
          <Stat
            label={view === "stix" ? "STIX artifacts" : "Observable types"}
            value={
              view === "stix"
                ? data.artifacts.filter((a) => a.type === "stix").length
                : new Set(indicators.map((i) => i.type)).size
            }
            sub={demo ? "Synthetic demonstration" : "Connected store records"}
            icon="cube"
            index={2}
          />
        </div>
        <Panel
          title={
            view === "confidence"
              ? "Evidence-ranked observables"
              : view === "risk"
                ? "Review priority"
                : view === "stix"
                  ? "Structured intelligence store"
                  : "Observable inventory"
          }
          sub={
            view === "risk"
              ? "Demo priority combines type, recency and sightings; no real-world risk probability."
              : view === "confidence"
                ? "Demo evidence scores are illustrative, not model predictions."
                : "An extracted domain, URL or IP is not automatically malicious."
          }
          action={
            <Button
              icon="download"
              onClick={() => {
                downloadFile(
                  `redtraces-${demo ? "demo" : "live"}-observables.json`,
                  JSON.stringify(
                    view === "stix"
                      ? observableBundle(indicators, demo)
                      : indicators,
                    null,
                    2,
                  ),
                );
                notify(
                  view === "stix"
                    ? "STIX observable bundle downloaded. Unsupported types are omitted."
                    : "Observables exported.",
                );
              }}
            >
              Export {view === "stix" ? "STIX" : "JSON"}
            </Button>
          }
        >
          <div className="rt-table-wrap">
            <table className="rt-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Observable</th>
                  <th>Sightings</th>
                  <th>
                    {view === "confidence"
                      ? "Evidence score"
                      : "Priority score"}
                  </th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {[...indicators]
                  .sort(
                    (a, b) =>
                      (view === "confidence"
                        ? b.confidence || 0
                        : b.score || 0) -
                      (view === "confidence"
                        ? a.confidence || 0
                        : a.score || 0),
                  )
                  .map((i) => (
                    <tr key={i.id}>
                      <td>
                        <Pill>{i.type}</Pill>
                      </td>
                      <td>
                        <button
                          className="rt-title-link rt-mono"
                          onClick={() =>
                            setDetail({
                              title: i.value,
                              label: "OBSERVABLE EVIDENCE",
                              body: (
                                <>
                                  <dl className="rt-dl">
                                    <dt>Type</dt>
                                    <dd>{i.type}</dd>
                                    <dt>Source</dt>
                                    <dd>{i.source}</dd>
                                    <dt>Sightings</dt>
                                    <dd>{i.sightings}</dd>
                                    <dt>Last observed</dt>
                                    <dd>{i.date}</dd>
                                    <dt>Assessment</dt>
                                    <dd>
                                      {demo
                                        ? "Synthetic example; not malicious infrastructure"
                                        : "Unverified observable"}
                                    </dd>
                                  </dl>
                                  <p className="rt-notice">
                                    Repeat sightings strengthen evidence of
                                    observation, not evidence of malicious
                                    intent.
                                  </p>
                                </>
                              ),
                            })
                          }
                        >
                          {i.value}
                        </button>
                        <small>{i.id}</small>
                      </td>
                      <td>{i.sightings}×</td>
                      <td>
                        <Score
                          value={view === "confidence" ? i.confidence : i.score}
                        />
                      </td>
                      <td className="rt-muted">{i.source}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            {!indicators.length && <Empty />}
          </div>
        </Panel>
        {view === "stix" && (
          <p className="rt-footnote">
            Exports use STIX 2.1 cyber-observable objects for supported IPs,
            domains and URLs. No maliciousness assertion is added.
          </p>
        )}
      </>
    );
  else if (view === "noise")
    content = (
      <>
        <div className="rt-stats three">
          <Stat
            label="Processed messages"
            value={data.noise.processed}
            sub="Pipeline lifetime counters"
            icon="layers"
          />
          <Stat
            label="Accepted"
            value={data.noise.accepted}
            sub="Retained for downstream analysis"
            icon="check"
          />
          <Stat
            label="Filtered out"
            value={data.noise.rejected}
            sub="Duplicates, off-topic and spam"
            icon="filter"
          />
        </div>
        <div className="rt-chart-grid">
          <Panel
            title="Why content was filtered"
            sub="Click a category to inspect demo decisions"
          >
            <div className="rt-bars">
              {Object.entries(data.noise.reasons).map(([reason, n]) => (
                <button
                  key={reason}
                  onClick={() => setNoiseFilter(reason)}
                  className={noiseFilter === reason ? "active" : ""}
                >
                  <span>{reason}</span>
                  <span className="rt-bar-track">
                    <i
                      style={{
                        width: `${(n / Math.max(data.noise.rejected, 1)) * 100}%`,
                      }}
                    />
                  </span>
                  <b>{n}</b>
                </button>
              ))}
            </div>
            {!data.noise.rejected && (
              <Empty title="No filtering counters reported" />
            )}
          </Panel>
          <Panel
            title="Processing stages"
            sub="Counts reported for each detector"
          >
            <div className="rt-step-list">
              {Object.entries(data.noise.detectors).map(([n, v], i) => (
                <div key={n}>
                  <span>0{i + 1}</span>
                  <b>{n}</b>
                  <Pill>{v}</Pill>
                </div>
              ))}
            </div>
            <p className="rt-footnote">
              {demo
                ? "Illustrative counters, not evidence of a deployed BERT or FastText model."
                : "Live counters are reported by the collector; availability depends on Redis configuration."}
            </p>
          </Panel>
        </div>
        {demo && (
          <Panel
            title="Decision inspection"
            action={
              <Button onClick={() => setNoiseFilter("All decisions")}>
                All decisions
              </Button>
            }
          >
            <div className="rt-decision-list">
              {["Duplicates", "Off-topic", "Spam"]
                .filter(
                  (r) => noiseFilter === "All decisions" || noiseFilter === r,
                )
                .map((r) => (
                  <article key={r}>
                    <Pill tone="low">{r}</Pill>
                    <div>
                      <h3>
                        {
                          (
                            {
                              Duplicates:
                                "Previously seen report reposted without new context",
                              "Off-topic":
                                "Product promotion with no threat context",
                              Spam: "Repeated referral links and advertisements",
                            } as Record<string, string>
                          )[r]
                        }
                      </h3>
                      <p>
                        Example decision · retained in the audit trail, excluded
                        from the analyst feed.
                      </p>
                    </div>
                    <Icon name="filter" />
                  </article>
                ))}
            </div>
          </Panel>
        )}
      </>
    );
  else if (view === "tracing")
    content = demoOnly(
      <>
        <Panel
          title="Visible provenance"
          sub="Observed forward metadata, with an explicit boundary around what is unknown"
        >
          <div className="rt-trace-flow">
            {[
              ["Research Archive", "Source message · available"],
              ["Signal Exchange", "Observed forward · available"],
              ["RedTraces", "Collection record · preserved"],
            ].map((n, i) => (
              <div key={n[0]}>
                <span className="rt-trace-node">
                  <Icon name={i === 2 ? "shield" : "send"} size={25} />
                </span>
                <h3>{n[0]}</h3>
                <p>{n[1]}</p>
                {i < 2 && (
                  <span className="rt-trace-arrow">
                    Visible edge <Icon name="arrow" />
                  </span>
                )}
              </div>
            ))}
          </div>
          <p className="rt-notice">
            Synthetic path. Telegram forwarding metadata does not expose a
            complete hop history. Hidden or copied origins remain unknown; this
            is not person attribution.
          </p>
        </Panel>
        <Panel
          title="Forwarded sample messages"
          sub="Inspect each record for its reported source"
        >
          {signalTable(signals.filter((s) => s.forwardedFrom))}
        </Panel>
      </>,
    );
  else if (view === "attack")
    content = demoOnly(
      <Panel
        title="ATT&CK technique coverage"
        sub="Illustrative technique labels on synthetic messages; not an automatic ATT&CK classifier"
      >
        <div className="rt-heatmap">
          {[
            ["Initial access", "T1566", "T1190"],
            ["Execution", "T1059", "T1204"],
            ["Persistence", "T1078", "T1136"],
            ["Credential access", "T1003", "T1110"],
            ["Discovery", "T1087", "T1046"],
            ["Exfiltration", "T1041", "T1567"],
          ].map(([t, ...ids]) => (
            <div key={t}>
              <h3>{t}</h3>
              {ids.map((id) => {
                const count = signals.filter((s) => s.technique === id).length;
                return (
                  <button
                    key={id}
                    style={
                      {
                        "--strength": count
                          ? Math.min(0.8, 0.12 + count / 40)
                          : 0.025,
                      } as CSSProperties
                    }
                    onClick={() =>
                      setDetail({
                        title: `${id} · ${t}`,
                        label: "DEMO TECHNIQUE MAPPING",
                        body: (
                          <>
                            <p>
                              These mappings are sample annotations, not
                              verified detections.
                            </p>
                            {signalTable(
                              signals.filter((s) => s.technique === id),
                              true,
                            )}
                          </>
                        ),
                      })
                    }
                  >
                    <b>{id}</b>
                    <span>{count} signals</span>
                    <Icon name="arrow" size={14} />
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        <div className="rt-heat-legend">
          <span>No coverage</span>
          {[0.05, 0.2, 0.4, 0.6, 0.8].map((n) => (
            <i key={n} style={{ background: `rgba(235,243,236,${n})` }} />
          ))}
          <span>More observations</span>
        </div>
      </Panel>,
    );
  else if (view === "correlation")
    content = (
      <>
        <Panel
          title="Source constellation"
          sub="Source-to-platform membership only; edges do not imply shared actors or campaigns"
        >
          <div className="rt-constellation">
            <div className="rt-constellation-center">
              <Icon name="shield" size={34} />
              <b>{signals.length}</b>
              <span>signals</span>
            </div>
            {countsBy(signals, (s) => s.platform).map(([p, n], i) => (
              <button
                key={p}
                className="rt-constellation-node"
                style={
                  {
                    "--n": i,
                    "--angle": `${i * 60}deg`,
                    "--source": platformColors[p],
                  } as CSSProperties
                }
                onClick={() => {
                  go("signals");
                  setPlatform(p);
                }}
              >
                <Icon name={p === "Telegram" ? "send" : "globe"} size={21} />
                <b>{p}</b>
                <span>{n} signals</span>
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Observed source relationships">
          <div className="rt-source-grid">
            {sources.map(([s, n]) => (
              <button
                key={s}
                className="rt-source-tile"
                onClick={() => {
                  go("signals");
                  setQuery(s);
                }}
              >
                <Icon name="network" />
                <b>{s}</b>
                <span>{n} collected signals</span>
                <Icon name="arrow" size={16} />
              </button>
            ))}
          </div>
        </Panel>
      </>
    );
  else if (view === "sources")
    content = (
      <Panel
        title="Source inventory"
        sub="Select a source to inspect its collected messages"
      >
        <div className="rt-source-grid">
          {sources.map(([s, n]) => (
            <button
              key={s}
              className="rt-source-tile"
              onClick={() => {
                go("signals");
                setQuery(s);
              }}
            >
              <Icon name="globe" />
              <b>{s}</b>
              <span>{n} signals</span>
              <Icon name="arrow" size={16} />
            </button>
          ))}
        </div>
        {!sources.length && <Empty />}
      </Panel>
    );
  else if (view === "rules")
    content = (
      <>
        <Panel
          title="Detection rule workbench"
          sub="Sigma matches log events. YARA matches file content. Both need testing before use."
        >
          <form
            className="rt-rule-form"
            onSubmit={(e) => {
              e.preventDefault();
              const escaped = JSON.stringify(ruleValue);
              const content =
                ruleType === "Sigma"
                  ? `title: ${JSON.stringify(ruleName)}\nid: ${crypto.randomUUID()}\nstatus: experimental\ndescription: Local draft for analyst review; not deployed.\nlogsource:\n  category: network_connection\n  product: windows\ndetection:\n  selection:\n    DestinationIp: ${escaped}\n  condition: selection\nfalsepositives:\n  - Legitimate connections to the same destination\nlevel: low\n`
                  : `rule redtraces_local_draft {\n  meta:\n    description = ${JSON.stringify(ruleName)}\n    status = "Draft - review required"\n  strings:\n    $observable = ${escaped} ascii wide\n  condition:\n    $observable\n}\n`;
              downloadFile(
                `redtraces-draft.${ruleType === "Sigma" ? "yml" : "yar"}`,
                content,
                "text/plain",
              );
              notify("Local draft downloaded. Nothing was deployed.");
            }}
          >
            <label>
              Rule format
              <select
                value={ruleType}
                onChange={(e) => setRuleType(e.target.value)}
              >
                <option>Sigma</option>
                <option>YARA</option>
              </select>
            </label>
            <label>
              Rule title
              <input
                required
                maxLength={120}
                value={ruleName}
                onChange={(e) => setRuleName(e.target.value)}
              />
            </label>
            <label>
              {ruleType === "Sigma"
                ? "Destination IPv4 (log field)"
                : "Literal string to match"}
              <input
                required
                maxLength={200}
                pattern={
                  ruleType === "Sigma"
                    ? "(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
                    : undefined
                }
                value={ruleValue}
                onChange={(e) => setRuleValue(e.target.value)}
              />
            </label>
            <button className="rt-btn rt-primary" type="submit">
              <Icon name="download" size={16} /> Download draft
            </button>
          </form>
          <p className="rt-notice">
            Drafts are generated locally. Sigma requires matching telemetry
            fields; YARA string matches are not proof of malware. Review false
            positives in a lab.
          </p>
        </Panel>
        <Panel title="Available artifacts">
          <div className="rt-artifacts">
            {data.artifacts
              .filter((a) => a.type !== "stix")
              .map((a) => (
                <article key={a.name}>
                  <span className="rt-source-icon">
                    <Icon name="code" />
                  </span>
                  <div>
                    <h3>{a.name}</h3>
                    <p>{a.status}</p>
                  </div>
                  <Pill>{a.type.toUpperCase()}</Pill>
                </article>
              ))}
          </div>
        </Panel>
      </>
    );
  else if (view === "siem")
    content = (
      <Panel
        title="Deployment audit"
        sub="Read-only deployment history. This interface does not push rules into production."
      >
        <div className="rt-table-wrap">
          <table className="rt-table">
            <thead>
              <tr>
                <th>Artifact</th>
                <th>Destination</th>
                <th>Status</th>
                <th>Attempted</th>
              </tr>
            </thead>
            <tbody>
              {data.deployments.map((d, i) => (
                <tr key={i}>
                  <td>{String(d.artifact_id || "—")}</td>
                  <td>{String(d.siem_type || "—")}</td>
                  <td>
                    <Pill>{String(d.status || "Unknown")}</Pill>
                  </td>
                  <td>{String(d.attempted_at || "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.deployments.length && (
            <Empty
              title="No deployments recorded"
              text="Generated drafts are not deployed automatically."
            />
          )}
        </div>
      </Panel>
    );
  else if (view === "review")
    content = (
      <Panel
        title="Review queue"
        sub="Inspect evidence and record a browser-local review decision"
      >
        {signalTable(
          signals.filter((s) => s.status === "Needs review" && !reviews[s.id]),
        )}
      </Panel>
    );
  else if (view === "report")
    content = (
      <Panel
        title="Intelligence situation report"
        sub={`${demo ? "Synthetic demonstration" : "Loaded live data"} · generated ${new Date().toLocaleDateString("en-GB")}`}
        action={
          <Button primary icon="download" onClick={exportReport}>
            Export report
          </Button>
        }
      >
        <div className="rt-report">
          <h3>Scope and collection</h3>
          <p>
            This view contains {signals.length} messages from {sources.length}{" "}
            observed sources over the selected {days}-day period. It includes{" "}
            {indicators.length} extracted observables and {high} high-priority
            messages. Counts refer to loaded, filtered records, not the entire
            database.
          </p>
          <h3>Analyst interpretation</h3>
          <p>
            Source claims require verification. Observables support
            investigation but do not establish maliciousness. Repeated posts and
            visible forwards can preserve context without proving an actor
            relationship or a complete propagation history.
          </p>
          <h3>Outputs and readiness</h3>
          <p>
            {data.artifacts.length} artifacts are listed. Detection drafts
            require independent testing and approval.{" "}
            {demo
              ? "All data in this report is synthetic. No collection, joining, model training or SIEM deployment was performed by the demonstration."
              : "Live mode displays only records returned by connected APIs. Missing modules are shown as unavailable rather than filled with sample records."}
          </p>
          <h3>Next review actions</h3>
          <ol>
            <li>Verify claims and inspect their source context.</li>
            <li>Validate observables before creating detection content.</li>
            <li>Review irrelevant sources and duplicate content.</li>
            <li>Document gaps in provenance and model evaluation.</li>
          </ol>
        </div>
      </Panel>
    );
  else if (view === "connections")
    content = (
      <div className="rt-legacy">
        <Connections urls={urls} setUrls={setUrls} />
      </div>
    );
  else {
    const p = (
      {
        telegram: "Telegram",
        forums: "Dark web",
        twitter: "X",
        facebook: "Facebook",
        instagram: "Instagram",
      } as Record<string, string>
    )[view];
    content = demo ? (
      <Panel
        title={`${p} collection preview`}
        sub="Synthetic sample feed. Switch to Live to use the existing collector controls."
      >
        {signalTable(signals.filter((s) => s.platform === p))}
      </Panel>
    ) : (
      <div className="rt-legacy">
        <ModuleView
          key={view + urls[view as Source]}
          type={view as Source}
          url={urls[view as Source]}
        />
      </div>
    );
  }
  return (
    <div className={`rt-app rt-agency ${agencyMotion ? "" : "rt-reduced"}`}>
      <div className="rt-scroll-progress" aria-hidden="true" />
      <a className="rt-skip" href="#rt-content">
        Skip to content
      </a>
      {mobile && (
        <button
          className="rt-sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`rt-sidebar ${mobile ? "is-open" : ""}`}>
        <button className="rt-brand" onClick={() => go("overview")}>
          <span className="rt-brand-mark">
            <Icon name="shield" size={24} />
          </span>
          <span>
            <span className="rt-wordmark">Red<span>Traces</span></span><small>INTELLIGENCE WORKSPACE</small>
          </span>
        </button>
        <div className="rt-workspace-chip">
          <span className="rt-team-avatar">R</span>
          <div>
            <b>Research workspace</b>
            <small>Threat intelligence team</small>
          </div>
          <Icon name="down" size={14} />
        </div>
        <nav aria-label="Main navigation">
          {menu.map((g) => (
            <div className="rt-nav-group" key={g.section}>
              <span>{g.section}</span>
              {g.items.map(([id, name, icon]) => (
                <button
                  key={id}
                  className={view === id ? "is-active" : ""}
                  aria-current={view === id ? "page" : undefined}
                  onClick={() => go(id)}
                >
                  <Icon name={icon} size={17} />
                  <span>{name}</span>
                  {id === "signals" && <small>{baseSignals.length}</small>}
                  {id === "discovery" && <small className="rt-new">NEW</small>}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="rt-sidebar-bottom">
          <span className="rt-avatar">RT</span>
          <div>
            <b>Threat analyst</b>
            <small>Local workspace</small>
          </div>
          <button
            className="rt-icon-btn"
            aria-label="Open connections"
            onClick={() => go("connections")}
          >
            <Icon name="settings" size={17} />
          </button>
        </div>
      </aside>
      <div className="rt-workspace">
        <header className="rt-topbar">
          <div className="rt-breadcrumb">
            <button
              className="rt-icon-btn rt-mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Icon name="menu" />
            </button>
            <span>Workspace</span>
            <span>/</span>
            <b>{label}</b>
          </div>
          <div className="rt-top-actions">
            <label className="rt-search">
              <Icon name="search" size={16} />
              <input
                ref={searchRef}
                aria-label="Search current view"
                placeholder="Search intelligence…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <kbd>⌘ K</kbd>
            </label>
            <button
              className="rt-icon-btn"
              title={motion ? "Reduce animations" : "Enable animations"}
              aria-label={motion ? "Reduce animations" : "Enable animations"}
              onClick={() => {
                setMotion(!motion);
                localStorage.setItem("redtraces-motion", String(!motion));
              }}
            >
              <Icon name={motion ? "pause" : "play"} size={16} />
            </button>
            <button
              className="rt-notification rt-icon-btn"
              aria-label="Open review queue"
              onClick={() => go("review")}
            >
              <Icon name="bell" />
              {signals.some(
                (s) => s.status === "Needs review" && !reviews[s.id],
              ) && <i />}
            </button>
            <span className="rt-avatar rt-top-avatar">RT</span>
          </div>
        </header>
        <main id="rt-content" className="rt-main">
          <div className="rt-page-head">
            <div>
              <div className="rt-eyebrow">
                REDTRACES /{" "}
                {view === "overview"
                  ? "COMMAND CENTER"
                  : menu.find((g) => g.items.some((x) => x[0] === view))
                      ?.section}
              </div>
              <h1>
                {view === "overview" ? "Intelligence overview" : label}
                <span className="rt-heading-dot" />
              </h1>
              <p>
                {descriptions[view] ||
                  "Your existing collection tools, connected to the intelligence workspace."}
              </p>
            </div>
            <div className="rt-page-actions">
              <label className="rt-period">
                <Icon name="clock" size={15} />
                <select
                  aria-label="Time range"
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                >
                  <option value={1}>Last 24 hours</option>
                  <option value={7}>Last 7 days</option>
                  <option value={30}>Last 30 days</option>
                </select>
              </label>
              <Button icon="download" onClick={exportReport}>
                Export
              </Button>
            </div>
          </div>
          <div className="rt-mode-banner">
            <span>
              <i className={`rt-status-dot ${demo ? "demo" : ""}`} />
              <b>{demo ? "Demo workspace" : "Live workspace"}</b>
              <span className="rt-mode-explainer">
                {demo
                  ? "Synthetic data. Real possibilities. No external actions."
                  : "Connected API records only. No sample fallback."}
              </span>
            </span>
            <div className="rt-row rt-gap">
              <button
                className={`rt-refresh ${busy ? "spinning" : ""}`}
                aria-label="Refresh workspace data"
                disabled={busy}
                onClick={() => setRefresh((n) => n + 1)}
              >
                <Icon name="refresh" size={14} />
              </button>
              <div className="rt-mode-switch" aria-label="Data mode">
                <button
                  className={demo ? "active" : ""}
                  aria-pressed={demo}
                  onClick={() => setMode(true)}
                >
                  Demo
                </button>
                <button
                  className={!demo ? "active" : ""}
                  aria-pressed={!demo}
                  onClick={() => setMode(false)}
                >
                  Live
                </button>
              </div>
            </div>
          </div>
          {!demo && data.errors.length > 0 && (
            <div className="rt-error" role="status">
              <Icon name="shield" />
              <span>
                Some services are unavailable: {data.errors.join(", ")}. Other
                connected data remains visible.
              </span>
              <button className="rt-text-btn" onClick={() => go("connections")}>
                Check connections
              </button>
            </div>
          )}
          {!ready || busy ? (
            <Panel>
              <div className="rt-loading" role="status">
                <span />
                <h3>Connecting the signals</h3>
                <p>Reading the selected workspace…</p>
              </div>
            </Panel>
          ) : (
            <div key={`${view}-${demo}`} className="rt-view">
              {content}
            </div>
          )}
          <footer className="rt-footer">
            <span>
              <Icon name="shield" size={13} /> RedTraces · Intelligence with
              context
            </span>
            <span>
              {demo ? "DEMONSTRATION DATA" : "LIVE API MODE"} <i />{" "}
              {signals.length} loaded signals in range
            </span>
          </footer>
        </main>
      </div>
      {detail && <Dialog detail={detail} close={() => setDetail(null)} />}
      <div className="rt-toast-region" role="status" aria-live="polite">
        {toast && (
          <div className="rt-toast">
            <Icon name="check" size={18} />
            {toast}
          </div>
        )}
      </div>
    </div>
  );
}
