import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Bell,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  Database,
  Hash,
  LayoutDashboard,
  LifeBuoy,
  Radio,
  Search,
  ServerCrash,
  Settings,
  ShieldCheck,
  Moon,
  Sun,
  UsersRound,
  Wifi,
} from "lucide-react";
import { DEMO_MESSAGES, DEMO_STATS } from "./mockData";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);
const DEMO_MODE =
  String(import.meta.env.VITE_DEMO_MODE || "").toLowerCase() === "true";
// Load the API's maximum page on first view so lower-volume sources (such as
// auto-discovery) remain visible alongside a Telegram backfill.
const PAGE_SIZE = 200;

type Message = {
  id: string;
  platform:
    | "telegram"
    | "discord"
    | "reddit"
    | "darkweb"
    | "autodiscovery";
  source: string;
  raw_text: string;
  author: string | null;
  url: string | null;
  collected_at: string;
  posted_at: string | null;
  metadata: Record<string, unknown>;
  attachments: Array<Record<string, string>>;
};

type MessagePage = {
  items: Message[];
  total: number;
  limit: number;
  offset: number;
};

type Stats = {
  total: number;
  last_hour: number;
  unique_channels: number;
};

type Layer2Metrics = {
  available: boolean;
  processed: number;
  accepted: number;
  rejected: number;
  languages: Record<string, number>;
  detectors: Record<string, number>;
  reasons: Record<string, number>;
};

type IOC = { type: string; value: string };
type WorkspaceView = "dashboard" | "signals" | "iocs" | "sources";

const IOC_LABELS: Record<string, string> = {
  sha256: "SHA-256",
  sha1: "SHA-1",
  md5: "MD5",
  urls: "URLs",
  ipv4: "IPv4",
  ipv6: "IPv6",
  domains: "Domains",
};

const PLATFORM_STYLES: Record<
  Message["platform"],
  { label: string; badge: string; icon: string }
> = {
  telegram: {
    label: "Telegram",
    badge: "bg-[#e8f4ff] text-[#1876a8]",
    icon: "bg-[#e8f4ff] text-[#1876a8]",
  },
  reddit: {
    label: "Reddit",
    badge: "bg-[#fff0e9] text-[#c64b18]",
    icon: "bg-[#fff0e9] text-[#c64b18]",
  },
  discord: {
    label: "Discord",
    badge: "bg-[#eeefff] text-[#5865c7]",
    icon: "bg-[#eeefff] text-[#5865c7]",
  },
  darkweb: {
    label: "Dark web",
    badge: "bg-[#f2ecf8] text-[#70459a]",
    icon: "bg-[#f2ecf8] text-[#70459a]",
  },
  autodiscovery: {
    label: "Discovery",
    badge: "bg-[#fff5d9] text-[#9b6b00]",
    icon: "bg-[#fff5d9] text-[#9b6b00]",
  },
};

function sourceLabel(message: Message): string {
  if (message.platform === "reddit") return `r/${message.source}`;
  if (message.platform === "discord") return `#${message.source}`;
  if (message.platform === "telegram") return `@${message.source}`;
  return message.source;
}

function messageIocs(message: Message): IOC[] {
  const raw = message.metadata.iocs;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  return Object.entries(raw as Record<string, unknown>).flatMap(([type, values]) =>
    Array.isArray(values)
      ? values
          .filter((value): value is string => typeof value === "string")
          .map((value) => ({ type, value }))
      : [],
  );
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) throw new Error(`Request failed with ${response.status}`);
  return response.json() as Promise<T>;
}

function relativeTime(value: string): string {
  const seconds = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 1000),
  );
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function NavItem({
  icon: Icon,
  label,
  active = false,
  count,
  onClick,
}: {
  icon: typeof Activity;
  label: string;
  active?: boolean;
  count?: number;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`nav-item ${active ? "nav-item-active" : ""}`}
    >
      <Icon size={17} strokeWidth={1.7} />
      <span>{label}</span>
      {count !== undefined && (
        <span className="ml-auto rounded-md bg-[#fee2e2] px-1.5 py-0.5 font-mono text-[9px] font-semibold text-[#c1121f]">
          {count}
        </span>
      )}
    </button>
  );
}

function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  primary = false,
}: {
  label: string;
  value: number;
  detail: string;
  icon: typeof Activity;
  primary?: boolean;
}) {
  return (
    <section
      className={`rounded-[22px] border p-5 ${
        primary
          ? "border-[#991b1b] bg-gradient-to-br from-[#7f1d1d] to-[#dc2626] text-white shadow-[0_16px_30px_rgba(153,27,27,0.20)]"
          : "border-[#f0dfe1] bg-white text-[#231113]"
      }`}
    >
      <div className="flex items-center justify-between">
        <p className={`text-[13px] font-semibold ${primary ? "text-white/85" : ""}`}>
          {label}
        </p>
        <span
          className={`grid h-8 w-8 place-items-center rounded-full ${
            primary ? "bg-white text-[#991b1b]" : "border border-[#ead5d8]"
          }`}
        >
          <Icon size={14} strokeWidth={1.8} />
        </span>
      </div>
      <p className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.05em]">
        {value.toLocaleString()}
      </p>
      <p
        className={`mt-3 text-[10px] ${
          primary ? "text-[#fecaca]" : "text-[#977177]"
        }`}
      >
        {detail}
      </p>
    </section>
  );
}

function MessageRow({ message }: { message: Message }) {
  const [expanded, setExpanded] = useState(false);
  const iocs = messageIocs(message);
  const timestamp = message.posted_at || message.collected_at;
  const longMessage = message.raw_text.length > 230;
  const body =
    longMessage && !expanded
      ? `${message.raw_text.slice(0, 230).trim()}…`
      : message.raw_text;
  const platformStyle = PLATFORM_STYLES[message.platform];

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.24 }}
      className="group border-b border-[#f0dfe1] px-1 py-5 last:border-b-0"
    >
      <div className="flex gap-3.5">
        <div
          className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${platformStyle.icon}`}
        >
          <Radio size={17} strokeWidth={1.8} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <h3 className="truncate text-[13px] font-semibold text-[#17221c]">
                {sourceLabel(message)}
              </h3>
              <span
                className={`rounded-md px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] ${platformStyle.badge}`}
              >
                {platformStyle.label}
              </span>
            </div>
            <time
              dateTime={timestamp}
              title={new Date(timestamp).toLocaleString()}
              className="shrink-0 text-[10px] text-[#a18488]"
            >
              {relativeTime(timestamp)}
            </time>
          </div>

          <p className="mt-2 whitespace-pre-wrap break-words text-[12px] leading-[1.7] text-[#5b3a40]">
            {body || <span className="italic text-[#b69da0]">Media only</span>}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 font-mono text-[9px] text-[#a98f93]">
              <Hash size={9} />
              {String(message.metadata.message_id ?? message.id)}
            </span>
            {message.author && (
              <span className="text-[9px] text-[#a98f93]">by {message.author}</span>
            )}
            {iocs.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-md bg-[#fff0f0] px-2 py-1 text-[9px] font-semibold text-[#b42332]">
                <ShieldCheck size={10} />
                {iocs.length} fetched IOC{iocs.length === 1 ? "" : "s"}
              </span>
            )}
          </div>

          {iocs.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {iocs.slice(0, expanded ? iocs.length : 4).map((ioc) => (
                <span
                  key={`${ioc.type}:${ioc.value}`}
                  title={ioc.value}
                  className="max-w-full truncate rounded-lg border border-[#efdfe1] bg-[#fffafa] px-2 py-1 font-mono text-[8px] text-[#705257]"
                >
                  <b className="mr-1 font-medium text-[#c1121f]">
                    {IOC_LABELS[ioc.type] || ioc.type}
                  </b>
                  {ioc.value}
                </span>
              ))}
              {!expanded && iocs.length > 4 && (
                <span className="px-1 py-1 text-[9px] text-[#a18488]">
                  +{iocs.length - 4} more
                </span>
              )}
            </div>
          )}

          {longMessage && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="mt-3 inline-flex items-center gap-1 text-[10px] font-semibold text-[#c1121f]"
            >
              {expanded ? "Show less" : "Read full message"}
              <ChevronDown
                size={11}
                className={`transition ${expanded ? "rotate-180" : ""}`}
              />
            </button>
          )}
        </div>
      </div>
    </motion.article>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("dashboard");
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = window.localStorage.getItem("redtraces-theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  });
  const [liveMessages, setLiveMessages] = useState<Message[]>([]);
  const [selectedChannel, setSelectedChannel] = useState("all");
  const [search, setSearch] = useState("");
  const [iocOnly, setIocOnly] = useState(false);
  const [streamOnline, setStreamOnline] = useState(DEMO_MODE);
  const [, setClock] = useState(0);

  const history = useInfiniteQuery({
    queryKey: ["messages", "all"],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      getJson<MessagePage>(
        `/api/messages?limit=${PAGE_SIZE}&offset=${pageParam}`,
      ),
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.items.length;
      return next < lastPage.total ? next : undefined;
    },
    enabled: !DEMO_MODE,
  });

  const stats = useQuery({
    queryKey: ["stats", "all"],
    queryFn: () => getJson<Stats>("/api/stats"),
    refetchInterval: 15_000,
    enabled: !DEMO_MODE,
  });

  const layer2 = useQuery({
    queryKey: ["layer2-metrics"],
    queryFn: () => getJson<Layer2Metrics>("/api/layer2/metrics"),
    refetchInterval: 15_000,
    enabled: !DEMO_MODE,
  });

  useEffect(() => {
    const timer = window.setInterval(() => setClock((value) => value + 1), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem("redtraces-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (DEMO_MODE) return;
    const stream = new EventSource(`${API_URL}/api/messages/stream`);
    stream.onopen = () => setStreamOnline(true);
    stream.onerror = () => setStreamOnline(false);
    stream.addEventListener("message", (event) => {
      const incoming = JSON.parse((event as MessageEvent).data) as Message;
      setLiveMessages((current) => [
        incoming,
        ...current.filter((message) => message.id !== incoming.id),
      ]);
      void queryClient.invalidateQueries({ queryKey: ["stats", "all"] });
      void queryClient.invalidateQueries({ queryKey: ["layer2-metrics"] });
    });
    return () => stream.close();
  }, [queryClient]);

  const messages = useMemo(() => {
    if (DEMO_MODE) return DEMO_MESSAGES as Message[];
    const historical = history.data?.pages.flatMap((page) => page.items) ?? [];
    const seen = new Set<string>();
    return [...liveMessages, ...historical].filter((message) => {
      if (seen.has(message.id)) return false;
      seen.add(message.id);
      return true;
    });
  }, [history.data, liveMessages]);

  const displayedStats = DEMO_MODE ? DEMO_STATS : stats.data;
  const channels = useMemo(
    () => [...new Set(messages.map((message) => message.source))].sort(),
    [messages],
  );
  const allIocs = useMemo(() => messages.flatMap(messageIocs), [messages]);
  const iocDistribution = useMemo(() => {
    const counts = new Map<string, number>();
    allIocs.forEach((ioc) => counts.set(ioc.type, (counts.get(ioc.type) || 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [allIocs]);
  const maxIocCount = Math.max(1, ...iocDistribution.map(([, count]) => count));
  const iocRows = useMemo(
    () =>
      messages.flatMap((message) =>
        messageIocs(message).map((ioc) => ({
          ...ioc,
          messageId: message.id,
          platform: message.platform,
          source: message.source,
          timestamp: message.posted_at || message.collected_at,
        })),
      ),
    [messages],
  );
  const sourceRows = useMemo(() => {
    const rows = new Map<
      string,
      {
        platform: Message["platform"];
        source: string;
        messages: number;
        iocs: number;
        lastSeen: string;
      }
    >();
    messages.forEach((message) => {
      const key = `${message.platform}:${message.source}`;
      const timestamp = message.posted_at || message.collected_at;
      const current = rows.get(key);
      if (!current) {
        rows.set(key, {
          platform: message.platform,
          source: message.source,
          messages: 1,
          iocs: messageIocs(message).length,
          lastSeen: timestamp,
        });
        return;
      }
      current.messages += 1;
      current.iocs += messageIocs(message).length;
      if (new Date(timestamp) > new Date(current.lastSeen)) current.lastSeen = timestamp;
    });
    return [...rows.values()].sort(
      (a, b) => new Date(b.lastSeen).getTime() - new Date(a.lastSeen).getTime(),
    );
  }, [messages]);

  const visibleMessages = messages.filter((message) => {
    const matchesChannel =
      selectedChannel === "all" || message.source === selectedChannel;
    const needle = search.trim().toLowerCase();
    const matchesSearch =
      !needle ||
      message.raw_text.toLowerCase().includes(needle) ||
      message.source.toLowerCase().includes(needle) ||
      messageIocs(message).some((ioc) => ioc.value.toLowerCase().includes(needle));
    return matchesChannel && matchesSearch && (!iocOnly || messageIocs(message).length > 0);
  });
  const normalizedSearch = search.trim().toLowerCase();
  const visibleIocRows = iocRows.filter(
    (ioc) =>
      !normalizedSearch ||
      ioc.value.toLowerCase().includes(normalizedSearch) ||
      ioc.type.toLowerCase().includes(normalizedSearch) ||
      ioc.source.toLowerCase().includes(normalizedSearch) ||
      ioc.platform.toLowerCase().includes(normalizedSearch),
  );
  const visibleSourceRows = sourceRows.filter(
    (source) =>
      !normalizedSearch ||
      source.source.toLowerCase().includes(normalizedSearch) ||
      source.platform.toLowerCase().includes(normalizedSearch),
  );

  return (
    <div className="red-theme min-h-screen bg-[#f8f4f4] p-2 text-[#2b1115] sm:p-4">
      <div className="mx-auto flex min-h-[calc(100vh-16px)] max-w-[1560px] overflow-hidden rounded-[28px] border border-white/80 bg-[#fcf8f8] shadow-[0_24px_70px_rgba(82,25,32,0.12)] sm:min-h-[calc(100vh-32px)]">
        <aside className="hidden w-[224px] shrink-0 flex-col border-r border-[#f0e2e4] bg-[#fffafa] px-4 py-6 lg:flex">
          <div className="flex items-center gap-2.5 px-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#c1121f] text-white shadow-[0_8px_18px_rgba(193,18,31,0.24)]">
              <CircleDot size={18} />
            </span>
            <div>
              <p className="text-[15px] font-semibold tracking-[-0.02em]">RedTraces</p>
              <p className="text-[8px] uppercase tracking-[0.18em] text-[#ab8d92]">
                CTI workspace
              </p>
            </div>
          </div>

          <p className="mb-2 mt-10 px-2 text-[9px] font-medium uppercase tracking-[0.16em] text-[#b99da1]">
            Workspace
          </p>
          <nav className="space-y-1">
            <NavItem
              icon={LayoutDashboard}
              label="Dashboard"
              active={workspaceView === "dashboard"}
              onClick={() => setWorkspaceView("dashboard")}
            />
            <NavItem
              icon={Radio}
              label="Live signals"
              count={messages.length}
              active={workspaceView === "signals"}
              onClick={() => setWorkspaceView("signals")}
            />
            <NavItem
              icon={ShieldCheck}
              label="IOC explorer"
              count={allIocs.length}
              active={workspaceView === "iocs"}
              onClick={() => setWorkspaceView("iocs")}
            />
            <NavItem
              icon={Database}
              label="Sources"
              active={workspaceView === "sources"}
              onClick={() => setWorkspaceView("sources")}
            />
          </nav>

          <p className="mb-2 mt-8 px-2 text-[9px] font-medium uppercase tracking-[0.16em] text-[#b99da1]">
            Channels
          </p>
          <div className="max-h-[270px] space-y-1 overflow-y-auto">
            <button
              type="button"
              onClick={() => setSelectedChannel("all")}
              className={`channel-button ${selectedChannel === "all" ? "channel-active" : ""}`}
            >
              <span>All channels</span>
              <span>{messages.length}</span>
            </button>
            {channels.map((channel) => (
              <button
                type="button"
                key={channel}
                onClick={() => setSelectedChannel(channel)}
                className={`channel-button ${selectedChannel === channel ? "channel-active" : ""}`}
              >
                <span className="truncate">@{channel}</span>
                <span>
                  {messages.filter((message) => message.source === channel).length}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-auto">
            <div className="mb-4 rounded-[18px] bg-[#2b1115] p-4 text-white">
              <div className="flex items-center gap-2 text-[10px] text-white/65">
                <Wifi size={12} />
                Collector status
              </div>
              <p className="mt-2 text-[13px] font-semibold">
                {DEMO_MODE ? "Demo workspace" : streamOnline ? "Stream online" : "Reconnecting"}
              </p>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                <div className="h-full w-[78%] rounded-full bg-[#fb7185]" />
              </div>
            </div>
            <NavItem icon={Settings} label="Settings" />
            <NavItem icon={LifeBuoy} label="Help center" />
          </div>
        </aside>

        <div className="min-w-0 flex-1 p-3 sm:p-4">
          <header className="flex h-[72px] items-center gap-3 rounded-[20px] bg-white px-4 shadow-[0_4px_18px_rgba(25,43,33,0.025)] sm:px-5">
            <div className="relative max-w-[430px] flex-1">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#a5878c]"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search signals, sources or IOCs"
                aria-label="Search signals"
                className="h-10 w-full rounded-xl bg-[#fff9f9] pl-9 pr-3 text-[11px] outline-none placeholder:text-[#b79ca1] focus:ring-2 focus:ring-[#c1121f]/15"
              />
            </div>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={() =>
                  setTheme((current) => (current === "light" ? "dark" : "light"))
                }
                aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
                title={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
                className="grid h-10 w-10 place-items-center rounded-xl border border-[#edf0ee] text-[#506057] transition hover:bg-[#f6f8f7]"
              >
                {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
              </button>
              <button
                type="button"
                aria-label="Notifications"
                className="grid h-10 w-10 place-items-center rounded-xl border border-[#f0dfe1] text-[#67474d]"
              >
                <Bell size={15} />
              </button>
              <div className="hidden items-center gap-2.5 border-l border-[#f0dfe1] pl-3 sm:flex">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-[#ffe4e6] text-[12px] font-semibold text-[#c1121f]">
                  RT
                </span>
                <div>
                  <p className="text-[11px] font-semibold">Threat Analyst</p>
                  <p className="text-[9px] text-[#ac9095]">
                    {DEMO_MODE ? "Demo environment" : "Live environment"}
                  </p>
                </div>
              </div>
            </div>
          </header>

          {workspaceView === "dashboard" && (
          <main className="px-1 pb-3 pt-6 sm:px-2">
            <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#c1121f]">
                  Intelligence overview
                </p>
                <h1 className="mt-1 text-[30px] font-semibold tracking-[-0.045em]">
                  Security dashboard
                </h1>
                <p className="mt-1 text-[11px] text-[#a6878c]">
                  Monitor incoming signals and extracted indicators in one place.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIocOnly((value) => !value)}
                aria-pressed={iocOnly}
                className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-[11px] font-semibold transition ${
                  iocOnly
                    ? "bg-[#c1121f] text-white shadow-[0_8px_18px_rgba(22,116,73,0.18)]"
                    : "border border-[#e7cfd3] bg-white text-[#5b3a40]"
                }`}
              >
                <ShieldCheck size={14} />
                {iocOnly ? "Showing fetched IOCs" : "Fetched IOCs only"}
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Total signals"
                value={displayedStats?.total ?? 0}
                detail="All normalized messages"
                icon={Activity}
                primary
              />
              <StatCard
                label="Last 60 minutes"
                value={displayedStats?.last_hour ?? 0}
                detail="Recently collected"
                icon={Clock3}
              />
              <StatCard
                label="Active channels"
                value={displayedStats?.unique_channels ?? 0}
                detail="Unique monitored sources"
                icon={UsersRound}
              />
              <StatCard
                label="Fetched IOCs"
                value={allIocs.length}
                detail="From currently loaded signals"
                icon={ShieldCheck}
              />
            </div>

            <section className="mt-3 rounded-[22px] border border-[#f0dfe1] bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-[14px] font-semibold">Layer 2 · Noise filtering</h2>
                  <p className="mt-1 text-[10px] text-[#a18488]">
                    Decisions are made before a signal enters the live feed.
                  </p>
                </div>
                <span
                  className={`rounded-lg px-2.5 py-1 text-[8px] font-semibold uppercase tracking-[0.1em] ${
                    layer2.data?.available
                      ? "bg-[#fff1f2] text-[#c1121f]"
                      : "bg-[#f5f3f4] text-[#997d82]"
                  }`}
                >
                  {layer2.data?.available ? "Live counters" : "Connecting"}
                </span>
              </div>
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {[
                  ["Processed", layer2.data?.processed ?? 0, "Evaluated by Layer 2"],
                  ["Accepted", layer2.data?.accepted ?? 0, "Passed into the dashboard"],
                  ["Filtered", layer2.data?.rejected ?? 0, "Noise or duplicate removed"],
                ].map(([label, value, detail]) => (
                  <div key={String(label)} className="rounded-xl bg-[#fff7f7] p-3">
                    <p className="text-[9px] font-medium text-[#977177]">{label}</p>
                    <p className="mt-1 text-[20px] font-semibold tracking-[-0.04em]">
                      {Number(value).toLocaleString()}
                    </p>
                    <p className="mt-1 text-[8px] text-[#a18488]">{detail}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-[9px]">
                <span className="rounded-md border border-[#efdfe1] bg-[#fffafa] px-2 py-1 text-[#705257]">
                  FastText language detection: {layer2.data?.detectors.fasttext_lid176 ?? 0}
                </span>
                <span className="rounded-md border border-[#efdfe1] bg-[#fffafa] px-2 py-1 text-[#705257]">
                  MinHash/LSH near duplicates: {layer2.data?.reasons.near_duplicate ?? 0}
                </span>
                <span className="rounded-md border border-[#efdfe1] bg-[#fffafa] px-2 py-1 text-[#705257]">
                  Redis 24h cache duplicates: {layer2.data?.reasons.duplicate_cache ?? 0}
                </span>
                <span className="rounded-md border border-[#efdfe1] bg-[#fffafa] px-2 py-1 text-[#705257]">
                  Spam model: test-only until CTI-labelled training data is approved
                </span>
              </div>
            </section>

            <div className="mt-3 grid gap-3 xl:grid-cols-12">
              <section className="rounded-[22px] border border-[#f0dfe1] bg-white p-5 xl:col-span-8">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-[14px] font-semibold">Live signal feed</h2>
                    <p className="mt-1 text-[10px] text-[#a18488]">
                      {selectedChannel === "all"
                        ? DEMO_MODE
                          ? "Synthetic Telegram, Reddit and Discord intelligence"
                          : "All monitored collection sources"
                        : `Filtered to ${selectedChannel}`}
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#fff1f2] px-2.5 py-1.5 text-[9px] font-semibold text-[#c1121f]">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#e11d48]" />
                    {visibleMessages.length} visible
                  </span>
                </div>

                {!DEMO_MODE && history.isError ? (
                  <div className="grid min-h-60 place-items-center text-center">
                    <div>
                      <ServerCrash className="mx-auto text-[#cbb5b9]" size={24} />
                      <p className="mt-3 text-[12px] font-semibold">Feed unavailable</p>
                      <button
                        type="button"
                        onClick={() => void history.refetch()}
                        className="mt-2 text-[10px] font-semibold text-[#c1121f]"
                      >
                        Retry connection
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3">
                    <AnimatePresence initial={false}>
                      {visibleMessages.map((message) => (
                        <MessageRow key={message.id} message={message} />
                      ))}
                    </AnimatePresence>
                    {!DEMO_MODE && history.isLoading && (
                      <div className="space-y-3 py-4">
                        {[0, 1, 2].map((item) => (
                          <div
                            key={item}
                            className="h-28 animate-pulse rounded-xl bg-[#fff7f7]"
                          />
                        ))}
                      </div>
                    )}
                    {(!history.isLoading || DEMO_MODE) &&
                      visibleMessages.length === 0 && (
                        <div className="grid min-h-52 place-items-center text-center">
                          <div>
                            <Radio className="mx-auto text-[#cfb7bb]" size={22} />
                            <p className="mt-3 text-[11px] text-[#96787d]">
                              No signals match this view
                            </p>
                          </div>
                        </div>
                      )}
                    {!DEMO_MODE && history.hasNextPage && (
                      <button
                        type="button"
                        disabled={history.isFetchingNextPage}
                        onClick={() => void history.fetchNextPage()}
                        className="mt-4 w-full rounded-xl border border-[#eedee0] py-2.5 text-[10px] font-semibold text-[#705257]"
                      >
                        {history.isFetchingNextPage
                          ? "Loading archive…"
                          : "Load older signals"}
                      </button>
                    )}
                  </div>
                )}
              </section>

              <div className="space-y-3 xl:col-span-4">
                <section className="rounded-[22px] border border-[#f0dfe1] bg-white p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-[14px] font-semibold">IOC overview</h2>
                      <p className="mt-1 text-[10px] text-[#a18488]">
                        Indicator composition
                      </p>
                    </div>
                    <span className="grid h-8 w-8 place-items-center rounded-full border border-[#e1e6e3]">
                      <ChevronRight size={14} />
                    </span>
                  </div>
                  <div className="mt-5 flex items-center gap-5">
                    <div
                      className="relative grid h-28 w-28 shrink-0 place-items-center rounded-full"
                      style={{
                        background: `conic-gradient(#c1121f 0 68%, #ffe4e6 68% 82%, #f4e7e8 82% 100%)`,
                      }}
                    >
                      <div className="grid h-[76px] w-[76px] place-items-center rounded-full bg-white text-center">
                        <div>
                          <p className="text-[24px] font-semibold leading-none tracking-[-0.05em]">
                            {allIocs.length}
                          </p>
                          <p className="mt-1 text-[8px] text-[#ab8d92]">Extracted</p>
                        </div>
                      </div>
                    </div>
                    <div className="min-w-0 flex-1 space-y-3">
                      {iocDistribution.slice(0, 4).map(([type, count]) => (
                        <div key={type}>
                          <div className="mb-1 flex justify-between text-[9px]">
                            <span className="text-[#806267]">
                              {IOC_LABELS[type] || type}
                            </span>
                            <span className="font-semibold">{count}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-[#edf1ef]">
                            <div
                              className="h-full rounded-full bg-[#e11d48]"
                              style={{ width: `${(count / maxIocCount) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                      {iocDistribution.length === 0 && (
                        <p className="text-[10px] text-[#a18488]">
                          No IOCs in this view yet.
                        </p>
                      )}
                    </div>
                  </div>
                </section>

                <section className="rounded-[22px] border border-[#f0dfe1] bg-white p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-[14px] font-semibold">Source health</h2>
                      <p className="mt-1 text-[10px] text-[#a18488]">
                        Collector connectivity
                      </p>
                    </div>
                    <span className="rounded-lg bg-[#fff1f2] px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.1em] text-[#c1121f]">
                      {DEMO_MODE ? "Demo" : "Live"}
                    </span>
                  </div>
                  <div className="mt-5 space-y-4">
                    {[
                      ["Telegram", "Streaming", true],
                      ["Discord", DEMO_MODE ? "Sample mode" : "Streaming", true],
                      ["Reddit", DEMO_MODE ? "Sample mode" : "Polling", true],
                      ["Auto-discovery", DEMO_MODE ? "Sample mode" : "Scheduled", true],
                      ["Dark web", DEMO_MODE ? "Sample mode" : "Tor routed", DEMO_MODE],
                    ].map(([name, detail, online]) => (
                      <div key={String(name)} className="flex items-center gap-3">
                        <span
                          className={`grid h-8 w-8 place-items-center rounded-lg ${
                            online
                              ? "bg-[#fff1f2] text-[#c1121f]"
                              : "bg-[#f2f3f2] text-[#9aa49e]"
                          }`}
                        >
                          <Database size={13} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-semibold">{name}</p>
                          <p className="text-[9px] text-[#98a39d]">{detail}</p>
                        </div>
                        <span
                          className={`h-2 w-2 rounded-full ${
                            online ? "bg-[#f43f5e]" : "bg-[#cfb9bd]"
                          }`}
                        />
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          </main>
          )}

          {workspaceView === "signals" && (
            <main className="px-1 pb-3 pt-6 sm:px-2">
              <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#167449]">
                    Collection workspace
                  </p>
                  <h1 className="mt-1 text-[30px] font-semibold tracking-[-0.045em]">
                    Live signals
                  </h1>
                  <p className="mt-1 text-[11px] text-[#85938b]">
                    Review the normalized cross-platform message stream.
                  </p>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-[#edf7f1] px-3 py-2 text-[10px] font-semibold text-[#167449]">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#1e9b62]" />
                  {visibleMessages.length} signals visible
                </span>
              </div>
              <section className="rounded-[22px] border border-[#edf0ee] bg-white p-5">
                <AnimatePresence initial={false}>
                  {visibleMessages.map((message) => (
                    <MessageRow key={message.id} message={message} />
                  ))}
                </AnimatePresence>
                {visibleMessages.length === 0 && (
                  <div className="grid min-h-64 place-items-center text-center text-[11px] text-[#87958d]">
                    No signals match the selected source or search.
                  </div>
                )}
              </section>
            </main>
          )}

          {workspaceView === "iocs" && (
            <main className="px-1 pb-3 pt-6 sm:px-2">
              <div className="mb-5">
                <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#167449]">
                  Extraction workspace
                </p>
                <h1 className="mt-1 text-[30px] font-semibold tracking-[-0.045em]">
                  IOC explorer
                </h1>
                <p className="mt-1 text-[11px] text-[#85938b]">
                  Search every indicator extracted from the loaded intelligence.
                </p>
              </div>
              <div className="mb-3 grid gap-3 sm:grid-cols-3">
                <StatCard
                  label="Indicators"
                  value={iocRows.length}
                  detail="All extracted values"
                  icon={ShieldCheck}
                  primary
                />
                <StatCard
                  label="Indicator types"
                  value={iocDistribution.length}
                  detail="Hashes, network and domains"
                  icon={Hash}
                />
                <StatCard
                  label="Affected sources"
                  value={new Set(iocRows.map((ioc) => ioc.source)).size}
                  detail="Sources with at least one IOC"
                  icon={Database}
                />
              </div>
              <section className="overflow-hidden rounded-[22px] border border-[#edf0ee] bg-white">
                <div className="grid grid-cols-[110px_minmax(220px,1fr)_150px_110px] gap-3 border-b border-[#edf0ee] bg-[#f8faf9] px-5 py-3 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#8a9890]">
                  <span>Type</span>
                  <span>Indicator</span>
                  <span>Source</span>
                  <span>Observed</span>
                </div>
                <div className="max-h-[610px] overflow-auto">
                  {visibleIocRows.map((ioc, index) => (
                    <div
                      key={`${ioc.messageId}:${ioc.type}:${ioc.value}:${index}`}
                      className="grid grid-cols-[110px_minmax(220px,1fr)_150px_110px] items-center gap-3 border-b border-[#f0f2f1] px-5 py-3.5 last:border-b-0"
                    >
                      <span className="w-fit rounded-md bg-[#edf7f1] px-2 py-1 text-[8px] font-semibold text-[#167449]">
                        {IOC_LABELS[ioc.type] || ioc.type}
                      </span>
                      <span className="break-all font-mono text-[10px] text-[#425149]">
                        {ioc.value}
                      </span>
                      <span className="truncate text-[10px] text-[#65746c]">
                        {ioc.platform} · {ioc.source}
                      </span>
                      <span className="text-[9px] text-[#93a098]">
                        {relativeTime(ioc.timestamp)}
                      </span>
                    </div>
                  ))}
                  {visibleIocRows.length === 0 && (
                    <div className="grid min-h-52 place-items-center text-[11px] text-[#87958d]">
                      No indicators match your search.
                    </div>
                  )}
                </div>
              </section>
            </main>
          )}

          {workspaceView === "sources" && (
            <main className="px-1 pb-3 pt-6 sm:px-2">
              <div className="mb-5">
                <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#167449]">
                  Collection workspace
                </p>
                <h1 className="mt-1 text-[30px] font-semibold tracking-[-0.045em]">
                  Sources
                </h1>
                <p className="mt-1 text-[11px] text-[#85938b]">
                  Coverage, message volume and IOC yield by monitored source.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {visibleSourceRows.map((source) => {
                  const style = PLATFORM_STYLES[source.platform];
                  return (
                    <section
                      key={`${source.platform}:${source.source}`}
                      className="rounded-[20px] border border-[#edf0ee] bg-white p-5 transition hover:-translate-y-0.5 hover:shadow-[0_12px_30px_rgba(31,52,40,0.07)]"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <span
                            className={`inline-flex rounded-md px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.1em] ${style.badge}`}
                          >
                            {style.label}
                          </span>
                          <h2 className="mt-3 truncate text-[14px] font-semibold">
                            {source.platform === "reddit"
                              ? `r/${source.source}`
                              : source.platform === "discord"
                                ? `#${source.source}`
                                : source.platform === "telegram"
                                  ? `@${source.source}`
                                  : source.source}
                          </h2>
                        </div>
                        <span className="h-2.5 w-2.5 rounded-full bg-[#26a86b] shadow-[0_0_0_4px_#e8f6ef]" />
                      </div>
                      <div className="mt-5 grid grid-cols-2 gap-2">
                        <div className="rounded-xl bg-[#f7f9f8] p-3">
                          <p className="text-[9px] text-[#8c9992]">Signals</p>
                          <p className="mt-1 text-[20px] font-semibold">{source.messages}</p>
                        </div>
                        <div className="rounded-xl bg-[#f7f9f8] p-3">
                          <p className="text-[9px] text-[#8c9992]">IOCs</p>
                          <p className="mt-1 text-[20px] font-semibold">{source.iocs}</p>
                        </div>
                      </div>
                      <p className="mt-4 flex items-center gap-1.5 text-[9px] text-[#94a098]">
                        <Clock3 size={10} />
                        Last signal {relativeTime(source.lastSeen)}
                      </p>
                    </section>
                  );
                })}
              </div>
              {visibleSourceRows.length === 0 && (
                <div className="mt-3 grid min-h-64 place-items-center rounded-[22px] border border-[#edf0ee] bg-white text-[11px] text-[#87958d]">
                  No sources match your search.
                </div>
              )}
            </main>
          )}
        </div>
      </div>
    </div>
  );
}
