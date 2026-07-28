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
const PAGE_SIZE = 50;

type Message = {
  id: string;
  platform: "telegram" | "reddit" | "darkweb";
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

type IOC = { type: string; value: string };

const IOC_LABELS: Record<string, string> = {
  sha256: "SHA-256",
  sha1: "SHA-1",
  md5: "MD5",
  urls: "URLs",
  ipv4: "IPv4",
  ipv6: "IPv6",
  domains: "Domains",
};

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
}: {
  icon: typeof Activity;
  label: string;
  active?: boolean;
  count?: number;
}) {
  return (
    <button
      type="button"
      className={`nav-item ${active ? "nav-item-active" : ""}`}
    >
      <Icon size={17} strokeWidth={1.7} />
      <span>{label}</span>
      {count !== undefined && (
        <span className="ml-auto rounded-md bg-[#dff3e8] px-1.5 py-0.5 font-mono text-[9px] font-semibold text-[#167449]">
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
          ? "border-[#126b43] bg-gradient-to-br from-[#0e5336] to-[#1f8b59] text-white shadow-[0_16px_30px_rgba(18,107,67,0.18)]"
          : "border-[#edf0ee] bg-white text-[#142019]"
      }`}
    >
      <div className="flex items-center justify-between">
        <p className={`text-[13px] font-semibold ${primary ? "text-white/85" : ""}`}>
          {label}
        </p>
        <span
          className={`grid h-8 w-8 place-items-center rounded-full ${
            primary ? "bg-white text-[#145d3d]" : "border border-[#dfe5e1]"
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
          primary ? "text-[#a9e8c7]" : "text-[#789086]"
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

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.24 }}
      className="group border-b border-[#edf0ee] px-1 py-5 last:border-b-0"
    >
      <div className="flex gap-3.5">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#e7f4ed] text-[#167449]">
          <Radio size={17} strokeWidth={1.8} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <h3 className="truncate text-[13px] font-semibold text-[#17221c]">
                @{message.source}
              </h3>
              <span className="rounded-md bg-[#eef7f2] px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] text-[#167449]">
                Telegram
              </span>
            </div>
            <time
              dateTime={timestamp}
              title={new Date(timestamp).toLocaleString()}
              className="shrink-0 text-[10px] text-[#91a098]"
            >
              {relativeTime(timestamp)}
            </time>
          </div>

          <p className="mt-2 whitespace-pre-wrap break-words text-[12px] leading-[1.7] text-[#536259]">
            {body || <span className="italic text-[#a4afa9]">Media only</span>}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 font-mono text-[9px] text-[#9aa69f]">
              <Hash size={9} />
              {String(message.metadata.message_id ?? message.id)}
            </span>
            {message.author && (
              <span className="text-[9px] text-[#9aa69f]">by {message.author}</span>
            )}
            {iocs.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-md bg-[#fff5d9] px-2 py-1 text-[9px] font-semibold text-[#9b6b00]">
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
                  className="max-w-full truncate rounded-lg border border-[#e7ebe8] bg-[#f7f9f8] px-2 py-1 font-mono text-[8px] text-[#64746b]"
                >
                  <b className="mr-1 font-medium text-[#167449]">
                    {IOC_LABELS[ioc.type] || ioc.type}
                  </b>
                  {ioc.value}
                </span>
              ))}
              {!expanded && iocs.length > 4 && (
                <span className="px-1 py-1 text-[9px] text-[#91a098]">
                  +{iocs.length - 4} more
                </span>
              )}
            </div>
          )}

          {longMessage && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="mt-3 inline-flex items-center gap-1 text-[10px] font-semibold text-[#167449]"
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
  const [liveMessages, setLiveMessages] = useState<Message[]>([]);
  const [selectedChannel, setSelectedChannel] = useState("all");
  const [search, setSearch] = useState("");
  const [iocOnly, setIocOnly] = useState(false);
  const [streamOnline, setStreamOnline] = useState(DEMO_MODE);
  const [, setClock] = useState(0);

  const history = useInfiniteQuery({
    queryKey: ["messages", "telegram"],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      getJson<MessagePage>(
        `/api/messages?platform=telegram&limit=${PAGE_SIZE}&offset=${pageParam}`,
      ),
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.items.length;
      return next < lastPage.total ? next : undefined;
    },
    enabled: !DEMO_MODE,
  });

  const stats = useQuery({
    queryKey: ["stats", "telegram"],
    queryFn: () => getJson<Stats>("/api/stats?platform=telegram"),
    refetchInterval: 15_000,
    enabled: !DEMO_MODE,
  });

  useEffect(() => {
    const timer = window.setInterval(() => setClock((value) => value + 1), 30_000);
    return () => window.clearInterval(timer);
  }, []);

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
      void queryClient.invalidateQueries({ queryKey: ["stats", "telegram"] });
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

  const visibleMessages = messages.filter((message) => {
    const matchesChannel =
      selectedChannel === "all" || message.source === selectedChannel;
    const needle = search.trim().toLowerCase();
    const matchesSearch =
      !needle ||
      message.raw_text.toLowerCase().includes(needle) ||
      message.source.toLowerCase().includes(needle);
    return matchesChannel && matchesSearch && (!iocOnly || messageIocs(message).length > 0);
  });

  return (
    <div className="min-h-screen bg-[#e9ecea] p-2 text-[#17221c] sm:p-4">
      <div className="mx-auto flex min-h-[calc(100vh-16px)] max-w-[1560px] overflow-hidden rounded-[28px] border border-white/80 bg-[#f5f6f5] shadow-[0_24px_70px_rgba(41,55,47,0.10)] sm:min-h-[calc(100vh-32px)]">
        <aside className="hidden w-[224px] shrink-0 flex-col border-r border-[#e8ece9] bg-[#fafbfa] px-4 py-6 lg:flex">
          <div className="flex items-center gap-2.5 px-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#167449] text-white shadow-[0_8px_18px_rgba(22,116,73,0.22)]">
              <CircleDot size={18} />
            </span>
            <div>
              <p className="text-[15px] font-semibold tracking-[-0.02em]">RedTraces</p>
              <p className="text-[8px] uppercase tracking-[0.18em] text-[#8b9991]">
                CTI workspace
              </p>
            </div>
          </div>

          <p className="mb-2 mt-10 px-2 text-[9px] font-medium uppercase tracking-[0.16em] text-[#a3ada7]">
            Workspace
          </p>
          <nav className="space-y-1">
            <NavItem icon={LayoutDashboard} label="Dashboard" active />
            <NavItem icon={Radio} label="Live signals" count={messages.length} />
            <NavItem icon={ShieldCheck} label="IOC explorer" count={allIocs.length} />
            <NavItem icon={Database} label="Sources" />
          </nav>

          <p className="mb-2 mt-8 px-2 text-[9px] font-medium uppercase tracking-[0.16em] text-[#a3ada7]">
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
            <div className="mb-4 rounded-[18px] bg-[#102f23] p-4 text-white">
              <div className="flex items-center gap-2 text-[10px] text-white/65">
                <Wifi size={12} />
                Collector status
              </div>
              <p className="mt-2 text-[13px] font-semibold">
                {DEMO_MODE ? "Demo workspace" : streamOnline ? "Stream online" : "Reconnecting"}
              </p>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                <div className="h-full w-[78%] rounded-full bg-[#5ed69b]" />
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
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#809087]"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search signals, sources or IOCs"
                aria-label="Search signals"
                className="h-10 w-full rounded-xl bg-[#f6f8f7] pl-9 pr-3 text-[11px] outline-none placeholder:text-[#a5afa9] focus:ring-2 focus:ring-[#167449]/15"
              />
            </div>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                aria-label="Notifications"
                className="grid h-10 w-10 place-items-center rounded-xl border border-[#edf0ee] text-[#506057]"
              >
                <Bell size={15} />
              </button>
              <div className="hidden items-center gap-2.5 border-l border-[#edf0ee] pl-3 sm:flex">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-[#dcefe5] text-[12px] font-semibold text-[#167449]">
                  RT
                </span>
                <div>
                  <p className="text-[11px] font-semibold">Threat Analyst</p>
                  <p className="text-[9px] text-[#96a29b]">
                    {DEMO_MODE ? "Demo environment" : "Live environment"}
                  </p>
                </div>
              </div>
            </div>
          </header>

          <main className="px-1 pb-3 pt-6 sm:px-2">
            <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#167449]">
                  Intelligence overview
                </p>
                <h1 className="mt-1 text-[30px] font-semibold tracking-[-0.045em]">
                  Security dashboard
                </h1>
                <p className="mt-1 text-[11px] text-[#85938b]">
                  Monitor incoming signals and extracted indicators in one place.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIocOnly((value) => !value)}
                aria-pressed={iocOnly}
                className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-[11px] font-semibold transition ${
                  iocOnly
                    ? "bg-[#167449] text-white shadow-[0_8px_18px_rgba(22,116,73,0.18)]"
                    : "border border-[#cfd8d3] bg-white text-[#45564c]"
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

            <div className="mt-3 grid gap-3 xl:grid-cols-12">
              <section className="rounded-[22px] border border-[#edf0ee] bg-white p-5 xl:col-span-8">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-[14px] font-semibold">Live signal feed</h2>
                    <p className="mt-1 text-[10px] text-[#91a098]">
                      {selectedChannel === "all"
                        ? "All monitored Telegram channels"
                        : `Filtered to @${selectedChannel}`}
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#edf7f1] px-2.5 py-1.5 text-[9px] font-semibold text-[#167449]">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#1e9b62]" />
                    {visibleMessages.length} visible
                  </span>
                </div>

                {!DEMO_MODE && history.isError ? (
                  <div className="grid min-h-60 place-items-center text-center">
                    <div>
                      <ServerCrash className="mx-auto text-[#b5beba]" size={24} />
                      <p className="mt-3 text-[12px] font-semibold">Feed unavailable</p>
                      <button
                        type="button"
                        onClick={() => void history.refetch()}
                        className="mt-2 text-[10px] font-semibold text-[#167449]"
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
                            className="h-28 animate-pulse rounded-xl bg-[#f5f7f6]"
                          />
                        ))}
                      </div>
                    )}
                    {(!history.isLoading || DEMO_MODE) &&
                      visibleMessages.length === 0 && (
                        <div className="grid min-h-52 place-items-center text-center">
                          <div>
                            <Radio className="mx-auto text-[#c1c9c4]" size={22} />
                            <p className="mt-3 text-[11px] text-[#7f8e85]">
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
                        className="mt-4 w-full rounded-xl border border-[#e5eae7] py-2.5 text-[10px] font-semibold text-[#64746b]"
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
                <section className="rounded-[22px] border border-[#edf0ee] bg-white p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-[14px] font-semibold">IOC overview</h2>
                      <p className="mt-1 text-[10px] text-[#91a098]">
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
                        background: `conic-gradient(#167449 0 68%, #dce8e1 68% 82%, #eff2f0 82% 100%)`,
                      }}
                    >
                      <div className="grid h-[76px] w-[76px] place-items-center rounded-full bg-white text-center">
                        <div>
                          <p className="text-[24px] font-semibold leading-none tracking-[-0.05em]">
                            {allIocs.length}
                          </p>
                          <p className="mt-1 text-[8px] text-[#8b9991]">Extracted</p>
                        </div>
                      </div>
                    </div>
                    <div className="min-w-0 flex-1 space-y-3">
                      {iocDistribution.slice(0, 4).map(([type, count]) => (
                        <div key={type}>
                          <div className="mb-1 flex justify-between text-[9px]">
                            <span className="text-[#68776e]">
                              {IOC_LABELS[type] || type}
                            </span>
                            <span className="font-semibold">{count}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-[#edf1ef]">
                            <div
                              className="h-full rounded-full bg-[#238b5c]"
                              style={{ width: `${(count / maxIocCount) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                      {iocDistribution.length === 0 && (
                        <p className="text-[10px] text-[#91a098]">
                          No IOCs in this view yet.
                        </p>
                      )}
                    </div>
                  </div>
                </section>

                <section className="rounded-[22px] border border-[#edf0ee] bg-white p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-[14px] font-semibold">Source health</h2>
                      <p className="mt-1 text-[10px] text-[#91a098]">
                        Collector connectivity
                      </p>
                    </div>
                    <span className="rounded-lg bg-[#edf7f1] px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.1em] text-[#167449]">
                      {DEMO_MODE ? "Demo" : "Live"}
                    </span>
                  </div>
                  <div className="mt-5 space-y-4">
                    {[
                      ["Telegram", "Streaming", true],
                      ["Reddit", DEMO_MODE ? "Sample mode" : "Polling", true],
                      ["Dark web", DEMO_MODE ? "Sample mode" : "Tor routed", DEMO_MODE],
                    ].map(([name, detail, online]) => (
                      <div key={String(name)} className="flex items-center gap-3">
                        <span
                          className={`grid h-8 w-8 place-items-center rounded-lg ${
                            online
                              ? "bg-[#e9f5ef] text-[#167449]"
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
                            online ? "bg-[#26a86b]" : "bg-[#bdc5c0]"
                          }`}
                        />
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
