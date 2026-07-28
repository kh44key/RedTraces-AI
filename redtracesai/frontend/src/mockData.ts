export type DemoMessage = {
  id: string;
  platform: "telegram";
  source: string;
  raw_text: string;
  author: string | null;
  url: string | null;
  collected_at: string;
  posted_at: string;
  metadata: Record<string, unknown>;
  attachments: Array<Record<string, string>>;
};

const minutesAgo = (minutes: number) =>
  new Date(Date.now() - minutes * 60_000).toISOString();

export const DEMO_MESSAGES: DemoMessage[] = [
  {
    id: "demo-10482",
    platform: "telegram",
    source: "threatwire_intel",
    raw_text:
      "Observed active exploitation attempts targeting CVE-2026-4187. Initial telemetry shows internet-facing appliances receiving a crafted request followed by a PowerShell stager. Block outbound connections to update-gateway[.]example.",
    author: "analyst_delta",
    url: null,
    collected_at: minutesAgo(1),
    posted_at: minutesAgo(2),
    metadata: {
      message_id: 10482,
      views: 3842,
      forwards: 117,
      ioc_count: 1,
      iocs: {
        sha256: [],
        sha1: [],
        md5: [],
        urls: [],
        ipv4: [],
        ipv6: [],
        domains: ["update-gateway.example"],
      },
    },
    attachments: [],
  },
  {
    id: "demo-8841",
    platform: "telegram",
    source: "ransomwatch",
    raw_text:
      "New ransomware victim claim posted by the BlackFrost group. The actor alleges access to a regional logistics provider and published a 2 GB proof archive. Claim remains unverified; infrastructure and sample hashes are under review.",
    author: "rw_bot",
    url: null,
    collected_at: minutesAgo(4),
    posted_at: minutesAgo(5),
    metadata: { message_id: 8841, views: 2218, forwards: 64 },
    attachments: [],
  },
  {
    id: "demo-7710",
    platform: "telegram",
    source: "malware_research_lab",
    raw_text:
      "Stealer campaign update: a new loader variant is using poisoned search ads and signed MSI packages. Persistence is established through a scheduled task named RuntimeBrokerUpdate. SHA-256: 63c7e3984f3b9a4e3d87734d15f9852ef71dfe388152507c81e4251638332b9a",
    author: "reverse_ops",
    url: null,
    collected_at: minutesAgo(9),
    posted_at: minutesAgo(11),
    metadata: {
      message_id: 7710,
      views: 5921,
      forwards: 203,
      ioc_count: 1,
      iocs: {
        sha256: [
          "63c7e3984f3b9a4e3d87734d15f9852ef71dfe388152507c81e4251638332b9a",
        ],
        sha1: [],
        md5: [],
        urls: [],
        ipv4: [],
        ipv6: [],
        domains: [],
      },
    },
    attachments: [],
  },
  {
    id: "demo-3066",
    platform: "telegram",
    source: "breach_signal",
    raw_text:
      "Possible data leak listing detected for a healthcare vendor. The seller claims customer records and internal documents. No sample validation yet; monitoring for escrow activity and additional evidence.",
    author: "signal_node_3",
    url: null,
    collected_at: minutesAgo(17),
    posted_at: minutesAgo(19),
    metadata: { message_id: 3066, views: 987, forwards: 31 },
    attachments: [],
  },
  {
    id: "demo-99124",
    platform: "telegram",
    source: "threatwire_intel",
    raw_text:
      "Phishing kit infrastructure pivot: cloud-auth[.]example at 198.51.100.42 imitates a cloud document-sharing login and submits credentials to a Telegram bot. Observed path: hxxps://cloud-auth[.]example/session.",
    author: "analyst_echo",
    url: null,
    collected_at: minutesAgo(26),
    posted_at: minutesAgo(28),
    metadata: {
      message_id: 99124,
      views: 4170,
      forwards: 88,
      ioc_count: 3,
      iocs: {
        sha256: [],
        sha1: [],
        md5: [],
        urls: ["https://cloud-auth.example/session"],
        ipv4: ["198.51.100.42"],
        ipv6: [],
        domains: ["cloud-auth.example"],
      },
    },
    attachments: [],
  },
  {
    id: "demo-4502",
    platform: "telegram",
    source: "initial_access_feed",
    raw_text:
      "Initial-access broker advertising VPN access to an unnamed European manufacturer. Claimed privileges: domain user with access to two production subnets. Asking price is 3 BTC. Scope remains unconfirmed.",
    author: "iab_watch",
    url: null,
    collected_at: minutesAgo(38),
    posted_at: minutesAgo(42),
    metadata: { message_id: 4502, views: 1642, forwards: 49 },
    attachments: [],
  },
  {
    id: "demo-66091",
    platform: "telegram",
    source: "malware_research_lab",
    raw_text:
      "Botnet controller update observed at 14:20 UTC. The latest configuration adds a fallback domain-generation routine and switches C2 traffic to protobuf over HTTPS. Detection signatures are being tested.",
    author: "packet_sage",
    url: null,
    collected_at: minutesAgo(51),
    posted_at: minutesAgo(54),
    metadata: { message_id: 66091, views: 3098, forwards: 72 },
    attachments: [],
  },
  {
    id: "demo-1228",
    platform: "telegram",
    source: "exploit_observer",
    raw_text:
      "Proof-of-concept exploit published for a pre-authentication path traversal issue affecting a popular backup appliance. No confirmed mass exploitation. Exposed versions should be isolated pending vendor guidance.",
    author: "cve_tracker",
    url: null,
    collected_at: minutesAgo(74),
    posted_at: minutesAgo(77),
    metadata: { message_id: 1228, views: 7234, forwards: 314 },
    attachments: [],
  },
];

export const DEMO_STATS = {
  total: 2847,
  last_hour: 7,
  unique_channels: 6,
};
