"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
type View =
  | "overview"
  | "connections"
  | "forums"
  | "instagram"
  | "facebook"
  | "twitter" | "telegram";
export type Source = "forums" | "instagram" | "facebook" | "twitter" | "telegram";
type ForumPeriod = "24h" | "7d" | "30d" | "365d" | "all";
type ForumTab = "signals" | "severity";
type ForumFilters = { dateFrom: string; dateTo: string; minScore: string };
export type URLs = Record<Source, string>;
type Row = Record<string, unknown>;
export const defaults: URLs = {
  forums: "http://127.0.0.1:5000",
  instagram: "http://127.0.0.1:8104",
  facebook: "http://127.0.0.1:8103",
  twitter: "http://127.0.0.1:8102",
  telegram: "http://127.0.0.1:8200",
};
// Source order used across the overview, and each source's accent colour.
const SOURCES: Source[] = ["forums", "instagram", "facebook", "twitter", "telegram"];
const ACCENT: Record<Source, string> = {
  forums: "#ffb64a",
  instagram: "#ff5da2",
  facebook: "#4f93e6",
  twitter: "#43d0ff",
  telegram: "#29b6f6",
};
const nav: { id: View; label: string; glyph: string }[] = [
  { id: "overview", label: "Command Center", glyph: "~" },
  { id: "connections", label: "Connections", glyph: "+" },
  { id: "forums", label: "Dark Forums", glyph: "#" },
  { id: "instagram", label: "Instagram", glyph: "◈" },
  { id: "facebook", label: "Facebook", glyph: "f" },
  { id: "twitter", label: "X / Twitter", glyph: "X" },
  { id: "telegram", label: "Telegram", glyph: "➤" },
];
const tidy = (u: string) => u.replace(/\/$/, "");

function SecurityCore({ online }: { online: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const gl = c.getContext("webgl", { alpha: true });
    if (!gl) return;
    const make = (t: number, s: string) => {
      const x = gl.createShader(t)!;
      gl.shaderSource(x, s);
      gl.compileShader(x);
      return x;
    };
    const p = gl.createProgram()!;
    gl.attachShader(
      p,
      make(
        gl.VERTEX_SHADER,
        `attribute vec2 p;uniform float t;varying float z;void main(){float r=length(p);z=.5+.5*sin(t*2.+r*10.);gl_Position=vec4(p*(.78+.08*sin(t+r*5.)),0.,1.);gl_PointSize=2.2+z*2.;}`,
      ),
    );
    gl.attachShader(
      p,
      make(
        gl.FRAGMENT_SHADER,
        `precision mediump float;varying float z;void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;gl_FragColor=vec4(.62+z*.34,.10+z*.14,.20+z*.16,(1.-d*2.)*.82);}`,
      ),
    );
    gl.linkProgram(p);
    gl.useProgram(p);
    const a: number[] = [];
    for (let q = 0; q < Math.PI * 2; q += 0.07)
      for (let b = -1; b <= 1; b += 0.11) {
        const r = Math.sqrt(1 - b * b);
        a.push(Math.cos(q) * r, b);
      }
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(a), gl.STATIC_DRAW);
    const l = gl.getAttribLocation(p, "p");
    gl.enableVertexAttribArray(l);
    gl.vertexAttribPointer(l, 2, gl.FLOAT, false, 0, 0);
    const tm = gl.getUniformLocation(p, "t");
    let raf = 0,
      s = performance.now();
    const draw = () => {
      const d = devicePixelRatio || 1;
      c.width = c.clientWidth * d;
      c.height = c.clientHeight * d;
      gl.viewport(0, 0, c.width, c.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(tm, (performance.now() - s) / 1000);
      gl.drawArrays(gl.POINTS, 0, a.length / 2);
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <div className="core">
      <canvas ref={ref} />
      <div className="core-ring r1" />
      <div className="core-ring r2" />
      <div className="core-center">
        <b>{online}</b>
        <span>
          SOURCES
          <br />
          CONNECTED
        </span>
      </div>
    </div>
  );
}
function Sparkline({ color = "#ff2f4d" }: { color?: string }) {
  return (
    <div className="spark" style={{ "--spark": color } as React.CSSProperties}>
      {[42, 58, 37, 66, 49, 82, 63, 91, 55, 76, 88, 70].map((h, i) => (
        <i key={i} style={{ height: `${h}%` }} />
      ))}
    </div>
  );
}
async function json(url: string, init?: RequestInit) {
  const r = await fetch(url, { ...init, cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function Overview({
  setView,
  urls,
}: {
  setView: (v: View) => void;
  urls: URLs;
}) {
  const [counts, setCounts] = useState<Record<Source, number>>({
    forums: 0,
    instagram: 0,
    facebook: 0,
    twitter: 0,
    telegram: 0,
  });
  const [online, setOnline] = useState<Source[]>([]);
  useEffect(() => {
    const keys: Source[] = ["forums", "instagram", "facebook", "twitter", "telegram"];
    Promise.allSettled([
      json(`${tidy(urls.forums)}/api/data`),
      json(`${tidy(urls.instagram)}/leaks?limit=500`),
      json(`${tidy(urls.facebook)}/leaks?limit=500`),
      json(`${tidy(urls.twitter)}/leaks?limit=500`),
      json(`${tidy(urls.telegram)}/leaks?limit=500`),
    ]).then((r) => {
      const next: Record<Source, number> = {
        forums: 0,
        instagram: 0,
        facebook: 0,
        twitter: 0,
    telegram: 0,
      };
      const live: Source[] = [];
      r.forEach((x, i) => {
        if (x.status === "fulfilled") {
          const k = keys[i];
          live.push(k);
          next[k] = Array.isArray(x.value)
            ? x.value.length
            : Number(x.value.total ?? x.value.alerts?.length ?? 0);
        }
      });
      setCounts(next);
      setOnline(live);
    });
  }, [urls]);
  const total = SOURCES.reduce((sum, k) => sum + counts[k], 0);
  return (
    <>
      <div className={`demo-banner ${online.length ? "connected-banner" : ""}`}>
        <b>
          {online.length
            ? `${online.length}/${SOURCES.length} SOURCE APIS ONLINE`
            : "START COLLECTORS"}
        </b>
        <span>
          Findings are read from the five local Python APIs. Live collection
          requires configured accounts and monitoring targets.
        </span>
        <button onClick={() => setView("connections")}>CONNECTIONS</button>
      </div>
      <header className="hero">
        <div>
          <span className="eyebrow">REDTRACES AI / LIVE THREAT OPERATIONS</span>
          <h1>
            CYBER THREAT
            <br />
            <em>INTELLIGENCE</em>
          </h1>
          <p>Unified monitoring across X, Facebook, Instagram, Telegram and authorized forum sources.</p>
        </div>
        <SecurityCore online={online.length} />
      </header>
      <section className="metrics">
        {[
          ["TELEGRAM", String(counts.telegram), online.includes("telegram") ? "Online" : "Offline", ACCENT.telegram],
          ["THREAT DETECTIONS", String(total), "Across all collectors", "#ff2f4d"],
          [
            "DARK FORUMS",
            String(counts.forums),
            online.includes("forums") ? "Live" : "Offline",
            ACCENT.forums,
          ],
          [
            "INSTAGRAM",
            String(counts.instagram),
            online.includes("instagram") ? "Live" : "Offline",
            ACCENT.instagram,
          ],
          [
            "FACEBOOK",
            String(counts.facebook),
            online.includes("facebook") ? "Live" : "Offline",
            ACCENT.facebook,
          ],
          [
            "X / TWITTER",
            String(counts.twitter),
            online.includes("twitter") ? "Live" : "Offline",
            ACCENT.twitter,
          ],
        ].map((x) => (
          <article className="metric glass" key={x[0]}>
            <span>{x[0]}</span>
            <strong>{x[1]}</strong>
            <small style={{ color: x[3] }}>{x[2]}</small>
            <Sparkline color={x[3]} />
          </article>
        ))}
      </section>
      <section className="source-cards">
        {(
          [
            [
              "forums",
              "#",
              "DARK FORUMS",
              counts.forums,
              "Crawler alerts and evidence",
            ],
            [
              "instagram",
              "◈",
              "INSTAGRAM",
              counts.instagram,
              "Profiles, hashtags and captured posts",
            ],
            [
              "facebook",
              "f",
              "FACEBOOK",
              counts.facebook,
              "Pages, groups and captured posts",
            ],
            [
              "twitter",
              "X",
              "X / TWITTER",
              counts.twitter,
              "Accounts, keywords and captured posts",
            ],
            ["telegram", "➤", "TELEGRAM", counts.telegram, "Channels, messages and matched indicators"],
          ] as const
        ).map((x) => (
          <button
            className="source-card glass"
            key={x[0]}
            style={{ "--accent": ACCENT[x[0]] } as React.CSSProperties}
            onClick={() => setView(x[0])}
          >
            <span className="source-icon">{x[1]}</span>
            <div>
              <small>{x[2]}</small>
              <strong>{x[3]}</strong>
              <p>{x[4]}</p>
            </div>
            <aside>
              <b>{online.includes(x[0]) ? "ONLINE" : "OFFLINE"}</b>
              <span>OPEN MODULE</span>
            </aside>
          </button>
        ))}
      </section>
    </>
  );
}

export function ModuleView({ type, url }: { type: Source; url: string }) {
  const info = {
    telegram: {title: "TELEGRAM INTELLIGENCE", sub: "Channels / messages / matched indicators", color: ACCENT.telegram, unit: "CHANNELS"},
    forums: {
      title: "DARK FORUMS OPERATIONS",
      sub: "Automated source monitoring / findings / date and time",
      color: ACCENT.forums,
      unit: "FINDINGS",
    },
    instagram: {
      title: "INSTAGRAM INTELLIGENCE",
      sub: "Profiles / hashtags / captured posts",
      color: ACCENT.instagram,
      unit: "PROFILES",
    },
    facebook: {
      title: "FACEBOOK INTELLIGENCE",
      sub: "Pages / groups / captured posts",
      color: ACCENT.facebook,
      unit: "PAGES",
    },
    twitter: {
      title: "X / TWITTER INTELLIGENCE",
      sub: "Accounts / narratives / captured posts",
      color: ACCENT.twitter,
      unit: "ACCOUNTS",
    },
  }[type];
  const [rows, setRows] = useState<Row[]>([]);
  const [targets, setTargets] = useState<Row[]>([]);
  const [accounts, setAccounts] = useState<Row[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [monitoredSources, setMonitoredSources] = useState(0);
  const [forumPeriod, setForumPeriod] = useState<ForumPeriod>("all");
  const [forumTab, setForumTab] = useState<ForumTab>("signals");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [minScore, setMinScore] = useState("");
  const [severityStats, setSeverityStats] = useState<Record<string, number>>({
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  });
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [online, setOnline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [rangeText, setRangeText] = useState("");
  const forumRequest = useRef<AbortController | null>(null);
  const forumPeriodRef = useRef<ForumPeriod>("all");
  const forumFiltersRef = useRef<ForumFilters>({
    dateFrom: "",
    dateTo: "",
    minScore: "",
  });
  const base = tidy(url);
  const forumUrl = (
    selectedPeriod: ForumPeriod,
    searchText: string,
    filters = forumFiltersRef.current,
  ) => {
    const params = new URLSearchParams({
      limit: "150",
      period: selectedPeriod,
      search: searchText,
      _: String(Date.now()),
    });
    if (filters.dateFrom) params.set("date_from", filters.dateFrom);
    if (filters.dateTo) params.set("date_to", filters.dateTo);
    if (filters.minScore) params.set("min_score", filters.minScore);
    return `${base}/api/data?${params.toString()}`;
  };
  const load = async (
    periodOverride?: ForumPeriod,
    filterOverride?: ForumFilters,
  ) => {
    setBusy(true);
    try {
      if (type === "forums") {
        const selectedPeriod = periodOverride ?? forumPeriodRef.current;
        forumRequest.current?.abort();
        const controller = new AbortController();
        forumRequest.current = controller;
        const selectedFilters = filterOverride ?? forumFiltersRef.current;
        const d = await json(
          forumUrl(selectedPeriod, query, selectedFilters),
          { signal: controller.signal },
        );
        const expectedPeriod =
          selectedFilters.dateFrom || selectedFilters.dateTo
            ? "custom"
            : selectedPeriod;
        if (!d.period || d.period !== expectedPeriod) {
          throw new Error(
            "The Dark Forums collector is outdated. Close it and run START-PK-CERT.ps1 again.",
          );
        }
        setRows(d.alerts || []);
        setTotalRecords(Number(d.total ?? d.alerts?.length ?? 0));
        setMonitoredSources(Number(d.monitored_sources ?? 425));
        setSeverityStats(d.severity || {});
        setTargets([]);
        setRangeText(
          d.range_start_utc
            ? `${d.range_start_utc} to ${d.range_end_utc} UTC`
            : `All captured records through ${d.range_end_utc} UTC`,
        );
      } else {
        const [r, t] = await Promise.all([
          json(`${base}/leaks?limit=1000&_=${Date.now()}`),
          json(`${base}/channels?_=${Date.now()}`),
        ]);
        setRows(r);
        setTotalRecords(r.length);
        setMonitoredSources(t.length);
        setTargets(t);
        // Optional: older collectors have no worker pool, so a failure here
        // must not take the rest of the view offline.
        try {
          setAccounts(await json(`${base}/accounts?_=${Date.now()}`));
        } catch {
          setAccounts([]);
        }
      }
      setOnline(true);
      setError("");
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setOnline(false);
      setError(e instanceof Error ? e.message : "Connection failed");
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => {
      clearInterval(timer);
      if (type === "forums") forumRequest.current?.abort();
    };
  }, [base, type]);
  const selectForumPeriod = (period: ForumPeriod) => {
    forumPeriodRef.current = period;
    setForumPeriod(period);
    const nextFilters = { ...forumFiltersRef.current, dateFrom: "", dateTo: "" };
    forumFiltersRef.current = nextFilters;
    setDateFrom("");
    setDateTo("");
    void load(period, nextFilters);
  };
  const applyForumFilters = () => {
    const nextFilters = { dateFrom, dateTo, minScore };
    forumFiltersRef.current = nextFilters;
    void load(forumPeriod, nextFilters);
  };
  const clearForumFilters = () => {
    const empty = { dateFrom: "", dateTo: "", minScore: "" };
    forumFiltersRef.current = empty;
    setDateFrom("");
    setDateTo("");
    setMinScore("");
    void load(forumPeriod, empty);
  };
  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || type === "forums") return;
    setBusy(true);
    try {
      await json(`${base}/add-channel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(type === "telegram" ? { link: input } : { username: input }),
      });
      setInput("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Add failed");
    } finally {
      setBusy(false);
    }
  };
  const search = async (q = query) => {
    setQuery(q);
    setBusy(true);
    try {
      if (type === "forums") {
        const d = await json(
          forumUrl(forumPeriod, q),
        );
        const expectedPeriod =
          forumFiltersRef.current.dateFrom || forumFiltersRef.current.dateTo
            ? "custom"
            : forumPeriod;
        if (!d.period || d.period !== expectedPeriod) {
          throw new Error(
            "The Dark Forums collector is outdated. Close it and run START-PK-CERT.ps1 again.",
          );
        }
        setRows(d.alerts || []);
        setTotalRecords(Number(d.total ?? d.alerts?.length ?? 0));
        setMonitoredSources(Number(d.monitored_sources ?? 425));
        setSeverityStats(d.severity || {});
        setRangeText(
          d.range_start_utc
            ? `${d.range_start_utc} to ${d.range_end_utc} UTC`
            : `All captured records through ${d.range_end_utc} UTC`,
        );
      } else {
        const matches: Row[] = await json(
          `${base}/search-leaks?keyword=${encodeURIComponent(q)}`,
        );
        setRows(matches);
        setTotalRecords(matches.length);
      }
      setOnline(true);
      setError("");
      document
        .getElementById("keyword-results")
        ?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div
      className="module-page"
      style={{ "--accent": info.color } as React.CSSProperties}
    >
      <div className={`demo-banner ${online ? "connected-banner" : ""}`}>
        <b>{online ? "SOURCE API ONLINE" : "SOURCE API OFFLINE"}</b>
        <span>
          {online
            ? `Receiving live data from ${base}`
            : `Start the attached ${type} Python application at ${base}`}
        </span>
        <button onClick={() => void load()}>REFRESH</button>
      </div>
      <header className="module-head">
        <div>
          <span className="eyebrow">REDTRACES AI / LIVE SOURCE</span>
          <h1>{info.title}</h1>
          <p>{info.sub}</p>
        </div>
        <div className="radar">
          <i />
          <i />
          <i />
          <b>{type === "forums" ? totalRecords : targets.length}</b>
          <span>
            {type === "forums" ? "SIGNALS" : info.unit}
            <br />
            {type === "forums" ? "CAPTURED" : "MONITORED"}
          </span>
        </div>
      </header>
      {type === "forums" && (
        <>
          <div className="forum-tabs" role="tablist" aria-label="Dark Forums views">
            <button
              type="button"
              className={forumTab === "signals" ? "active" : ""}
              onClick={() => setForumTab("signals")}
              role="tab"
              aria-selected={forumTab === "signals"}
            >
              SIGNALS FEED
            </button>
            <button
              type="button"
              className={forumTab === "severity" ? "active" : ""}
              onClick={() => setForumTab("severity")}
              role="tab"
              aria-selected={forumTab === "severity"}
            >
              SEVERITY SCORE
            </button>
          </div>
          <section className="forum-filter glass" aria-label="Dark Forums filters">
            <div className="period-filter" aria-label="Preset time range">
              {(
                [
                  ["24h", "24 HOURS"],
                  ["7d", "WEEK"],
                  ["30d", "MONTH"],
                  ["365d", "YEAR"],
                  ["all", "ALL TIME"],
                ] as const
              ).map(([value, label]) => (
                <button
                  type="button"
                  key={value}
                  className={
                    forumPeriod === value && !dateFrom && !dateTo ? "active" : ""
                  }
                  onClick={() => selectForumPeriod(value)}
                  aria-pressed={forumPeriod === value && !dateFrom && !dateTo}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="custom-filter-grid">
              <label>
                FROM DATE &amp; TIME
                <input
                  type="datetime-local"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </label>
              <label>
                TO DATE &amp; TIME
                <input
                  type="datetime-local"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </label>
              <label>
                MINIMUM SEVERITY SCORE
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="0–100"
                  value={minScore}
                  onChange={(e) => setMinScore(e.target.value)}
                />
              </label>
              <button type="button" className="apply-filter" onClick={applyForumFilters}>
                APPLY FILTER
              </button>
              <button type="button" className="clear-filter" onClick={clearForumFilters}>
                CLEAR
              </button>
            </div>
            <p className="period-status">
              CAPTURE-TIME FILTER · {busy ? "UPDATING…" : `${totalRecords.toLocaleString()} SIGNALS`}
              {rangeText && <small>{rangeText}</small>}
            </p>
          </section>
        </>
      )}
      {error && (
        <div className="connection-notice">Connection error: {error}</div>
      )}
      {type === "forums" && forumTab === "severity" && (
        <section className="severity-grid">
          {([
            ["CRITICAL", "90–100", severityStats.critical || 0],
            ["HIGH", "70–89", severityStats.high || 0],
            ["MEDIUM", "40–69", severityStats.medium || 0],
            ["LOW", "0–39", severityStats.low || 0],
          ] as const).map(([label, band, count]) => (
            <article className={`glass severity-card ${label.toLowerCase()}`} key={label}>
              <span>{label} SEVERITY</span>
              <strong>{Number(count).toLocaleString()}</strong>
              <small>SCORE {band}</small>
            </article>
          ))}
        </section>
      )}
      {(type !== "forums" || forumTab === "signals") && <section className="module-stats">
        {(type === "forums"
          ? [
              ["CAPTURED SIGNALS", String(totalRecords)],
              [
                "TIME RANGE",
                {
                  "24h": "24 HOURS",
                  "7d": "WEEK",
                  "30d": "MONTH",
                  "365d": "YEAR",
                  all: "ALL TIME",
                }[forumPeriod],
              ],
              ["MONITORED SOURCES", String(monitoredSources)],
              ["SOURCE API", online ? "ONLINE" : "OFFLINE"],
            ]
          : [
              ["CAPTURED", String(totalRecords)],
              ["KEYWORD HITS", query ? String(totalRecords) : "--"],
              ["MONITORED", String(targets.length)],
              ["SOURCE API", online ? "ONLINE" : "OFFLINE"],
            ]
        ).map((m, i) => (
          <article className="glass" key={m[0]}>
            <span>{m[0]}</span>
            <strong className={i === 3 ? (online ? "online" : "offline") : ""}>
              {m[1]}
            </strong>
            <Sparkline color={info.color} />
          </article>
        ))}
      </section>}
      {(type !== "forums" || forumTab === "signals") && <section className="control-grid">
        <article className="glass controls">
          <div className="panel-title">
            <div>
              <span>COLLECTION CONTROL</span>
              <b>
                {type === "forums"
                  ? "Forum findings are supplied through the ingestion API"
                  : "Add and manage monitored sources"}
              </b>
            </div>
          </div>
          {type !== "forums" && (
            <form onSubmit={add}>
              <label>
                {type === "telegram"
                  ? "CHANNEL USERNAME OR T.ME LINK"
                  : type === "instagram"
                  ? "PROFILE USERNAME OR #HASHTAG"
                  : type === "facebook"
                    ? "PAGE OR GROUP USERNAME"
                    : "X ACCOUNT USERNAME"}
              </label>
              <div className="input-row">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={
                    type === "telegram"
                      ? "@channel or https://t.me/channel"
                      : type === "instagram"
                      ? "@profile or #hashtag"
                      : type === "facebook"
                        ? "page-name or group id"
                        : "@account"
                  }
                />
                <button disabled={busy}>+ ADD</button>
              </div>
            </form>
          )}
          <div className="targets">
            {targets.map((t, i) => (
              <div key={String(t.id || t.username || t.handle || i)}>
                <i />
                <b>{String(t.title || t.username || t.handle || "Source")}</b>
                <span>{type === "telegram" && !accounts.some((a) => a.active) ? "CONFIGURED" : "ACTIVE"}</span>
              </div>
            ))}
          </div>
          {type !== "forums" && accounts.length > 0 && (
            <>
              <div className="panel-title" style={{ marginTop: 20 }}>
                <div>
                  <span>WORKER ACCOUNTS</span>
                  <b>
                    {
                      accounts.filter((a) => a.status === "online").length
                    }{" "}
                    of {accounts.length} online — requests are rotated across
                    these logins/sessions to avoid rate limits
                  </b>
                </div>
              </div>
              <div className="targets">
                {accounts.map((a, i) => (
                  <div key={String(a.session_name || a.username || i)}>
                    <i />
                    <b>@{String(a.username || a.session_name || "session")}</b>
                    <span>
                      {String(a.status || "offline").toUpperCase()}
                      {a.note ? ` · ${String(a.note)}` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </article>
        <article className="glass search-panel">
          <div className="panel-title">
            <div>
              <span>KEYWORD SEARCH</span>
              <b>Queries the real collector database</b>
            </div>
          </div>
          <label>QUERY / INDICATOR</label>
          <div className="searchbox">
            <span>?</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              placeholder="credentials, malware, domain..."
            />
            <button disabled={busy} onClick={() => search()}>
              {busy ? "WAIT" : "SCAN"}
            </button>
          </div>
          <div className="chips">
            {["credentials", "ransomware", "database leak", "access sale"].map(
              (k) => (
                <button onClick={() => search(k)} key={k}>
                  {k}
                </button>
              ),
            )}
          </div>
          <div className="capture">
            <div>
              <span>LIVE RECORDS</span>
              <b>{totalRecords}</b>
            </div>
            <div className={`progress ${online ? "" : "empty"}`}>
              <i />
            </div>
            <small>
              {online
                ? "Collector database synchronized"
                : "Waiting for collector"}
            </small>
          </div>
        </article>
      </section>}
      <section className="glass results" id="keyword-results">
        <div className="panel-title">
          <div>
            <span>{type === "forums" && forumTab === "severity" ? "SEVERITY FINDINGS" : "KEYWORD RESULTS"}</span>
            <b>
              {query
                ? `Live matches for "${query}"`
                : "Newest collector records"}
            </b>
          </div>
          <button onClick={() => search(query)}>REFRESH</button>
        </div>
        {rows.length ? (
          <div className="table">
            <div className="tr th">
              <span>RISK</span>
              <span>SOURCE</span>
              <span>CAPTURED INTELLIGENCE</span>
              <span>TIME</span>
              <span>STATUS</span>
            </div>
            {rows.slice(0, 200).map((r, i) => (
              <div className="tr" key={String(r.id || i)}>
                <span
                  className={`risk ${String(r.severity || "low").toLowerCase()}`}
                >
                  {String(r.severity || "INFO")}
                  {type === "forums" && r.score !== undefined && (
                    <small>{Number(r.score).toFixed(0)}/100</small>
                  )}
                </span>
                <b>
                  {String(
                    r.channel ||
                      r.author_username ||
                      r.source ||
                      r.page_title ||
                      "Collector",
                  )}
                </b>
                <span>
                  {String(
                    r.text ||
                      r.content_snippet ||
                      r.matched_keywords ||
                      "Captured record",
                  )}
                </span>
                <span>
                  {String(
                    r.processed_at || r.message_date || r.tweet_date || r.first_seen_utc || "",
                  ).slice(0, 19)}
                </span>
                <em>STORED</em>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-results">
            <b>NO MATCHING RECORDS</b>
            <p>
              {online
                ? "The collector is connected but returned no matching data."
                : "Start the supplied Python collector, then refresh this module."}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

export function Connections({
  urls,
  setUrls,
}: {
  urls: URLs;
  setUrls: (v: URLs) => void;
}) {
  const [draft, setDraft] = useState(urls);
  const [status, setStatus] = useState<Record<Source, string>>({
    forums: "idle",
    instagram: "idle",
    facebook: "idle",
    twitter: "idle",
    telegram: "idle",
  });
  const test = async (s: Source) => {
    setStatus({ ...status, [s]: "testing" });
    try {
      await json(
        `${tidy(draft[s])}${s === "forums" ? "/api/data" : "/leaks?limit=1"}`,
      );
      setStatus((x) => ({ ...x, [s]: "online" }));
    } catch {
      setStatus((x) => ({ ...x, [s]: "offline" }));
    }
  };
  const save = () => {
    localStorage.setItem("redtraces-ai-collector-urls", JSON.stringify(draft));
    setUrls(draft);
  };
  return (
    <div className="connections-page">
      <header className="module-head">
        <div>
          <span className="eyebrow">REDTRACES AI / COLLECTOR BRIDGE</span>
          <h1>SOURCE CONNECTIONS</h1>
          <p>
            Account credentials and live polling are configured on the server. This
            page connects the dashboard to their local API addresses.
          </p>
        </div>
      </header>
      <section className="connection-grid">
        {(
          [
            [
              "forums",
              "#",
              "DARK FORUMS",
              "Docker starts the local forum API. Ingest alerts through /api/alerts.",
              "5000",
            ],
            [
              "instagram",
              "◈",
              "INSTAGRAM",
              "Docker starts the local API; live polling needs separate account setup.",
              "8104",
            ],
            [
              "facebook",
              "f",
              "FACEBOOK",
              "Docker starts the local API; add pages or groups as monitoring targets.",
              "8103",
            ],
            [
              "twitter",
              "X",
              "X / TWITTER",
              "Docker starts the local API. X polling is disabled until configured.",
              "8102",
            ],
            ["telegram", "➤", "TELEGRAM", "Local API with persistent channel targets. Live collection needs a Telegram session.", "8101"],
          ] as const
        ).map((x) => {
          const s = x[0];
          return (
            <article className="glass connection-card" key={s}>
              <span
                className="connection-icon"
                style={{ color: ACCENT[s] }}
              >
                {x[1]}
              </span>
              <h2>{x[2]}</h2>
              <p>{x[3]}</p>
              <label>COLLECTOR API ADDRESS</label>
              <input
                value={draft[s]}
                onChange={(e) => setDraft({ ...draft, [s]: e.target.value })}
              />
              <small className={`test-status ${status[s]}`}>
                {status[s] === "online"
                  ? "CONNECTED"
                  : status[s] === "offline"
                    ? "NOT REACHABLE"
                    : status[s] === "testing"
                      ? "TESTING..."
                      : `EXPECTED PORT ${x[4]}`}
              </small>
              <button onClick={() => test(s)}>TEST CONNECTION</button>
            </article>
          );
        })}
      </section>
      <button className="save-connections" onClick={save}>
        SAVE ALL CONNECTIONS
      </button>
      <aside className="safety-note">
        <b>Where keyword data appears</b>
        <p>
          X, Facebook, Instagram and Telegram use their supplied /search-leaks APIs.
          DarkForums loads /api/data and filters its real SQLite alert records.
          Results appear in each module&apos;s Keyword Results table.
        </p>
      </aside>
    </div>
  );
}

export default function Home() {
  const [view, setView] = useState<View>("overview");
  const [urls, setUrls] = useState<URLs>(defaults);
  useEffect(() => {
    try {
      const s = localStorage.getItem("redtraces-ai-collector-urls") ?? localStorage.getItem("hexsentry-collector-urls");
      if (s) setUrls({ ...defaults, ...JSON.parse(s) });
    } catch {}
  }, []);
  return (
    <main>
      <div className="noise" />
      <aside className="sidebar">
        <div className="brand">
          <svg
            width="42"
            height="42"
            viewBox="0 0 512 512"
            aria-label="RedTraces AI logo"
            style={{ filter: "drop-shadow(0 0 12px rgba(255,47,77,0.4))" }}
          >
            <g transform="translate(256,256)">
              <path
                d="M 78,-75 L 104,-60 L 104,60 L 0,120 L -104,60 L -104,-60 L 0,-120 L 26,-105"
                fill="none"
                stroke="#ff2f4d"
                strokeWidth="14"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M -44,-6 L -12,26 L 52,-42"
                fill="none"
                stroke="#ff2f4d"
                strokeWidth="16"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </g>
          </svg>
          <div>
            <b style={{ letterSpacing: "3px", fontSize: "16px" }}>REDTRACES AI</b>
            <small>THREAT INTELLIGENCE</small>
          </div>
        </div>
        <nav>
          {nav.map((n) => (
            <button
              className={view === n.id ? "active" : ""}
              onClick={() => setView(n.id)}
              key={n.id}
            >
              <span>{n.glyph}</span>
              {n.label}
              <i />
            </button>
          ))}
        </nav>
        <div className="system">
          <span>INTEGRATED SOURCES</span>
          <div>
            <i />
            ATTACHED COLLECTORS
          </div>
        </div>
        <button className="analyst">
          <span>PK</span>
          <div>
            <b>REDTRACES AI</b>
            <small>Secure console</small>
          </div>
          <i>...</i>
        </button>
      </aside>
      <section className="workspace">
        <div className="topbar">
          <div className="breadcrumb">
            REDTRACES AI <span>/</span>{" "}
            {nav.find((n) => n.id === view)?.label.toUpperCase()}
          </div>
          <div>
            <span className="clock">
              SECURE OPERATIONS <b>PAKISTAN</b>
            </span>
          </div>
        </div>
        <div className="content">
          {view === "overview" ? (
            <Overview setView={setView} urls={urls} />
          ) : view === "connections" ? (
            <Connections urls={urls} setUrls={setUrls} />
          ) : (
            <ModuleView type={view} url={urls[view]} />
          )}
        </div>
      </section>
    </main>
  );
}


