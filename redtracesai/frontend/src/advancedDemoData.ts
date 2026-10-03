const minutesAgo = (minutes: number) =>
  new Date(Date.now() - minutes * 60_000).toISOString();

export type ScoredIOC = {
  id: string;
  value: string;
  type: "ipv4" | "domain" | "url" | "sha256";
  confidence: number;
  severity: "critical" | "high" | "medium";
  sources: string[];
  sightings: number;
  campaign: string;
  last_seen: string;
};

export type AttackTechnique = {
  id: string;
  name: string;
  tactic: string;
  score: number;
  evidence: number;
};

export type CampaignNode = {
  id: string;
  label: string;
  kind: "campaign" | "actor" | "ioc" | "source";
  x: number;
  y: number;
};

export type CampaignEdge = { from: string; to: string };

export type PendingRule = {
  id: string;
  title: string;
  format: "Sigma" | "YARA";
  severity: "critical" | "high" | "medium";
  ioc_count: number;
  campaign: string;
  target: string;
  created_at: string;
  status: "awaiting analyst" | "changes requested";
};

export const DEMO_SCORED_IOCS: ScoredIOC[] = [
  { id: "ioc-001", value: "203.0.113.77", type: "ipv4", confidence: 96, severity: "critical", sources: ["Telegram", "Reddit", "Dark web"], sightings: 8, campaign: "NightJackal", last_seen: minutesAgo(2) },
  { id: "ioc-002", value: "secure-docs.example", type: "domain", confidence: 92, severity: "critical", sources: ["Telegram", "Discord", "Auto-discovery"], sightings: 6, campaign: "NightJackal", last_seen: minutesAgo(4) },
  { id: "ioc-003", value: "https://payload.example/dropper", type: "url", confidence: 88, severity: "high", sources: ["Reddit", "Dark web"], sightings: 4, campaign: "NightJackal", last_seen: minutesAgo(11) },
  { id: "ioc-004", value: "8f27d01a1d3b9c6e787462295a51bd86e5afc560d7cc8c871d6ab3f0129e45ab", type: "sha256", confidence: 94, severity: "critical", sources: ["Telegram", "Discord"], sightings: 5, campaign: "NightJackal", last_seen: minutesAgo(8) },
  { id: "ioc-005", value: "198.51.100.64", type: "ipv4", confidence: 78, severity: "high", sources: ["Auto-discovery", "Reddit"], sightings: 3, campaign: "SilentLedger", last_seen: minutesAgo(14) },
  { id: "ioc-006", value: "login-update.example", type: "domain", confidence: 71, severity: "medium", sources: ["Discord"], sightings: 2, campaign: "Unclustered", last_seen: minutesAgo(19) },
  { id: "ioc-007", value: "https://cdn-patch.example/update.exe", type: "url", confidence: 84, severity: "high", sources: ["Telegram", "Auto-discovery"], sightings: 4, campaign: "SilentLedger", last_seen: minutesAgo(27) },
  { id: "ioc-008", value: "4d186321c1a7f0f354b297e8914ab240", type: "sha256", confidence: 67, severity: "medium", sources: ["Dark web"], sightings: 1, campaign: "Unclustered", last_seen: minutesAgo(39) },
];

export const DEMO_ATTACK_TECHNIQUES: AttackTechnique[] = [
  { id: "T1566.002", name: "Spearphishing Link", tactic: "Initial Access", score: 92, evidence: 14 },
  { id: "T1204.002", name: "Malicious File", tactic: "Execution", score: 84, evidence: 9 },
  { id: "T1059.001", name: "PowerShell", tactic: "Execution", score: 78, evidence: 7 },
  { id: "T1105", name: "Ingress Tool Transfer", tactic: "Command & Control", score: 88, evidence: 11 },
  { id: "T1071.001", name: "Web Protocols", tactic: "Command & Control", score: 81, evidence: 8 },
  { id: "T1027", name: "Obfuscated Files", tactic: "Defense Evasion", score: 69, evidence: 5 },
  { id: "T1041", name: "Exfiltration Over C2", tactic: "Exfiltration", score: 61, evidence: 3 },
  { id: "T1583.001", name: "Domains", tactic: "Resource Development", score: 74, evidence: 6 },
];

export const DEMO_CAMPAIGN_NODES: CampaignNode[] = [
  { id: "campaign", label: "NightJackal", kind: "campaign", x: 50, y: 48 },
  { id: "actor", label: "UNC-4827", kind: "actor", x: 19, y: 20 },
  { id: "ip", label: "203.0.113.77", kind: "ioc", x: 79, y: 18 },
  { id: "domain", label: "secure-docs.example", kind: "ioc", x: 83, y: 70 },
  { id: "hash", label: "8f27…e45ab", kind: "ioc", x: 48, y: 86 },
  { id: "telegram", label: "@falconfeedsio", kind: "source", x: 13, y: 75 },
  { id: "darkweb", label: "Dark web forum", kind: "source", x: 47, y: 12 },
];

export const DEMO_CAMPAIGN_EDGES: CampaignEdge[] = [
  { from: "campaign", to: "actor" }, { from: "campaign", to: "ip" },
  { from: "campaign", to: "domain" }, { from: "campaign", to: "hash" },
  { from: "campaign", to: "telegram" }, { from: "campaign", to: "darkweb" },
  { from: "actor", to: "darkweb" }, { from: "ip", to: "domain" },
];

export const DEMO_PENDING_RULES: PendingRule[] = [
  { id: "SIG-2041", title: "NightJackal outbound infrastructure", format: "Sigma", severity: "critical", ioc_count: 3, campaign: "NightJackal", target: "Proxy / Firewall", created_at: minutesAgo(12), status: "awaiting analyst" },
  { id: "YAR-0882", title: "NightJackal dropper hashes", format: "YARA", severity: "high", ioc_count: 2, campaign: "NightJackal", target: "EDR / Malware scanner", created_at: minutesAgo(19), status: "awaiting analyst" },
  { id: "SIG-2039", title: "SilentLedger DNS callbacks", format: "Sigma", severity: "high", ioc_count: 2, campaign: "SilentLedger", target: "DNS telemetry", created_at: minutesAgo(31), status: "changes requested" },
  { id: "SIG-2037", title: "Suspicious payload download", format: "Sigma", severity: "medium", ioc_count: 1, campaign: "Unclustered", target: "Web proxy", created_at: minutesAgo(46), status: "awaiting analyst" },
];

export const DEMO_WEEKLY_REPORT = {
  title: "Social CTI Weekly Intelligence Brief",
  period: "27 July – 2 August 2026",
  generated_at: minutesAgo(7),
  executive_summary: "NightJackal remained the highest-priority observed campaign, with infrastructure corroborated across Telegram, Reddit and a monitored dark-web forum. Eight high-confidence indicators were normalized into STIX, and three deployable network detections were generated for analyst review.",
  metrics: { signals: 1284, unique_iocs: 86, high_confidence: 31, campaigns: 3, rules_generated: 12, sources: 18 },
  findings: [
    "NightJackal infrastructure appeared on three independent platforms within 42 minutes.",
    "Spearphishing links and ingress tool transfer were the strongest ATT&CK technique matches.",
    "Two file hashes require YARA deployment through an EDR workflow.",
  ],
  recommendations: [
    "Block confirmed NightJackal network indicators after analyst approval.",
    "Hunt for PowerShell downloads followed by outbound connections to newly registered domains.",
    "Prioritize review of the four pending Sigma/YARA rules before the next collection cycle.",
  ],
};
