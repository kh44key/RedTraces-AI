export type DemoMessage = {
  id: string;
  platform:
    | "telegram"
    | "reddit"
    | "discord"
    | "darkweb"
    | "autodiscovery";
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
    id: "demo-discord-941832",
    platform: "discord",
    source: "soc-operations",
    raw_text:
      "Triage update: repeated beaconing was observed from a lab endpoint to 203.0.113.77 over HTTPS. The downloaded payload matched SHA-256 8f27d01a1d3b9c6e787462295a51bd86e5afc560d7cc8c871d6ab3f0129e45ab. Host isolated; sample queued for reverse engineering.",
    author: "mira.blue",
    url: null,
    collected_at: minutesAgo(1),
    posted_at: minutesAgo(2),
    metadata: {
      message_id: "1287441902837194832",
      channel_id: "1198873451100284928",
      guild_id: "1184472103991201792",
      noise: {
        accepted: true,
        reason: null,
        language: "en",
        normalized_sha256:
          "ed42fa9387ce455f049262724f2eff693a33925dd1cd318a9460de1d907682cc",
      },
      ioc_count: 2,
      iocs: {
        sha256: [
          "8f27d01a1d3b9c6e787462295a51bd86e5afc560d7cc8c871d6ab3f0129e45ab",
        ],
        sha1: [],
        md5: [],
        urls: [],
        ipv4: ["203.0.113.77"],
        ipv6: [],
        domains: [],
      },
    },
    attachments: [
      {
        filename: "memory-triage.txt",
        type: "text/plain",
        sha256:
          "512789a6c9e3da78c22ad3b1d15da9d4567239b68e79bc3b238644c959aa5f41",
      },
    ],
  },
  {
    id: "demo-reddit-t3-1f8cti",
    platform: "reddit",
    source: "netsec",
    raw_text:
      "Incident responders are tracking a credential-phishing chain using hxxps://secure-docs[.]example/auth. The page fingerprints mobile visitors and forwards captured sessions to 198.51.100.64. Indicators are sanitized and reserved for this demo.",
    author: "packet_nomad",
    url: "https://www.reddit.com/r/netsec/comments/1f8cti/demo_incident_thread/",
    collected_at: minutesAgo(3),
    posted_at: minutesAgo(4),
    metadata: {
      reddit_id: "1f8cti",
      score: 184,
      num_comments: 37,
      noise: {
        accepted: true,
        reason: null,
        language: "en",
        normalized_sha256:
          "eeea3a36b131921a3642956369ebd72e85b334b9c12a82d119381fb401b361a1",
      },
      ioc_count: 3,
      iocs: {
        sha256: [],
        sha1: [],
        md5: [],
        urls: ["https://secure-docs.example/auth"],
        ipv4: ["198.51.100.64"],
        ipv6: [],
        domains: ["secure-docs.example"],
      },
    },
    attachments: [],
  },
  {
    id: "demo-telegram-120491",
    platform: "telegram",
    source: "falconfeedsio",
    raw_text:
      "Threat bulletin: a loader campaign is rotating C2 infrastructure through sync-cache[.]example and the TEST-NET host 192.0.2.146. Analysts associate the activity with malicious archive attachments delivered through invoice-themed lures.",
    author: "falconfeeds_bot",
    url: "https://t.me/falconfeedsio/120491",
    collected_at: minutesAgo(5),
    posted_at: minutesAgo(6),
    metadata: {
      message_id: 120491,
      views: 6241,
      forwards: 208,
      noise: {
        accepted: true,
        reason: null,
        language: "en",
        normalized_sha256:
          "2775f2a7a15834fced8223978d95a272ac7c7991c43cd4f38d45c0cac9af3bae",
      },
      ioc_count: 2,
      iocs: {
        sha256: [],
        sha1: [],
        md5: [],
        urls: [],
        ipv4: ["192.0.2.146"],
        ipv6: [],
        domains: ["sync-cache.example"],
      },
    },
    attachments: [],
  },
  {
    id: "demo-discord-941711",
    platform: "discord",
    source: "malware-research",
    raw_text:
      "Sandbox notes for the new infostealer build: persistence through a Run key, browser database discovery, and exfiltration to api-gateway[.]example/v2/upload. MD5 44d88612fea8a8f36de82e1278abb02f retained as a synthetic training indicator.",
    author: "reverse_ops",
    url: null,
    collected_at: minutesAgo(8),
    posted_at: minutesAgo(9),
    metadata: {
      message_id: "1287440184902277111",
      channel_id: "1198873462236160051",
      guild_id: "1184472103991201792",
      noise: {
        accepted: true,
        reason: null,
        language: "en",
        normalized_sha256:
          "5f665d546107722c3e1eaec4a67ace719df3a7817457f568cafcf2d7a54a119c",
      },
      ioc_count: 2,
      iocs: {
        sha256: [],
        sha1: [],
        md5: ["44d88612fea8a8f36de82e1278abb02f"],
        urls: [],
        ipv4: [],
        ipv6: [],
        domains: ["api-gateway.example"],
      },
    },
    attachments: [],
  },
  {
    id: "demo-reddit-comment-j4cti9",
    platform: "reddit",
    source: "cybersecurity",
    raw_text:
      "We found the same fake update page during internal hunting. DNS history points to cdn-browser-update[.]example, while callbacks resolve to 203.0.113.118. No production systems were affected.",
    author: "ir_fieldnotes",
    url: "https://www.reddit.com/r/cybersecurity/comments/1f8cti/comment/j4cti9/",
    collected_at: minutesAgo(12),
    posted_at: minutesAgo(13),
    metadata: {
      reddit_id: "j4cti9",
      score: 69,
      noise: {
        accepted: true,
        reason: null,
        language: "en",
        normalized_sha256:
          "3d86dfe90da98888fd829cff24276937382a4ed52a5ed9ff433464fa40d333d4",
      },
      ioc_count: 2,
      iocs: {
        sha256: [],
        sha1: [],
        md5: [],
        urls: [],
        ipv4: ["203.0.113.118"],
        ipv6: [],
        domains: ["cdn-browser-update.example"],
      },
    },
    attachments: [],
  },
  {
    id: "demo-discord-940882",
    platform: "discord",
    source: "threat-hunting",
    raw_text:
      "Hunt query matched PowerShell spawning from a document reader on three test hosts. The command retrieved hxxps://telemetry-check[.]example/bootstrap.ps1. Blocking and retrospective search are in progress.",
    author: "hunter.07",
    url: null,
    collected_at: minutesAgo(16),
    posted_at: minutesAgo(17),
    metadata: {
      message_id: "1287431004412217392",
      channel_id: "1198873496721621054",
      guild_id: "1184472103991201792",
      noise: {
        accepted: true,
        reason: null,
        language: "en",
        normalized_sha256:
          "2d0b6ec312a08772447246d41441fd48fcbd4f39675bf61cc5eeb3dbbcfe6b34",
      },
      ioc_count: 2,
      iocs: {
        sha256: [],
        sha1: [],
        md5: [],
        urls: ["https://telemetry-check.example/bootstrap.ps1"],
        ipv4: [],
        ipv6: [],
        domains: ["telemetry-check.example"],
      },
    },
    attachments: [],
  },
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
  total: 3184,
  last_hour: 13,
  unique_channels: 12,
};
