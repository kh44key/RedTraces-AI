export type Signal = {
  id: string;
  title: string;
  text: string;
  source: string;
  platform: string;
  date: string;
  severity: string;
  score: number | null;
  status: string;
  topic: string;
  indicators: string[];
  technique?: string;
  forwardedFrom?: string;
};
export type Indicator = {
  id: string;
  value: string;
  type: string;
  sightings: number;
  source: string;
  date: string;
  score: number | null;
  confidence: number | null;
};
export type Artifact = {
  name: string;
  type: string;
  status: string;
  size?: number;
};
export type Watch = {
  name: string;
  domain: string;
  keywords: string;
  enabled: boolean;
};
export type Candidate = {
  name: string;
  platform: string;
  score: number;
  posts: number;
  relevant: number;
  reason: string;
  state: string;
};
export type DataSet = {
  signals: Signal[];
  indicators: Indicator[];
  artifacts: Artifact[];
  deployments: Record<string, unknown>[];
  noise: {
    processed: number;
    accepted: number;
    rejected: number;
    reasons: Record<string, number>;
    detectors: Record<string, number>;
    languages: Record<string, number>;
  };
  errors: string[];
  loaded: boolean;
};
export const platformColors: Record<string, string> = {
  Telegram: "#8fe5bd",
  "Dark web": "#ffc978",
  Discovery: "#79cfff",
  X: "#b6a4f4",
  Facebook: "#ff9eb3",
  Instagram: "#d9e89b",
};
export const initialWatches: Watch[] = [
  {
    name: "Aster Bank",
    domain: "aster.example",
    keywords: "aster, credential sale, data exposure",
    enabled: true,
  },
  {
    name: "Orion Health",
    domain: "orion.example",
    keywords: "orion, patient records, access broker",
    enabled: true,
  },
  {
    name: "Northstar Cloud",
    domain: "northstar.example",
    keywords: "northstar, cloud token, exposed service",
    enabled: true,
  },
];
export const initialCandidates: Candidate[] = [
  {
    name: "Signal Exchange / demo",
    platform: "Telegram",
    score: 92,
    posts: 24,
    relevant: 21,
    reason:
      "Repeated access-sale claims with target aliases and supporting context.",
    state: "Pending review",
  },
  {
    name: "Breach Research / demo",
    platform: "Dark web",
    score: 87,
    posts: 30,
    relevant: 24,
    reason:
      "Exposure discussions match two monitored organizations. Claims remain unverified.",
    state: "Pending review",
  },
  {
    name: "Threat Notes / demo",
    platform: "Discovery",
    score: 81,
    posts: 18,
    relevant: 13,
    reason:
      "Technical reports contain relevant infrastructure and vulnerability context.",
    state: "Pending review",
  },
  {
    name: "General Tech / demo",
    platform: "Telegram",
    score: 22,
    posts: 25,
    relevant: 3,
    reason: "Mostly product discussions; too little threat-specific context.",
    state: "Rejected",
  },
];
const topics = [
  {
    title: "Access-sale claim mentions Aster Bank",
    text: "Synthetic research scenario: a public post claims access to an Aster Bank portal. No database has been obtained; the claim requires independent verification.",
    topic: "Access sale",
    severity: "High",
    score: 86,
    technique: "T1078",
  },
  {
    title: "Phishing infrastructure in a research report",
    text: "Synthetic threat report describes a credential-harvesting page at signin.aster.example. The domain is reserved for this demonstration, not malicious infrastructure.",
    topic: "Phishing",
    severity: "High",
    score: 78,
    technique: "T1566",
  },
  {
    title: "Orion Health exposure claim reposted",
    text: "Synthetic exposure claim references Orion Health. Forwarding metadata links a source post; it does not verify the claim or identify an attacker.",
    topic: "Data exposure",
    severity: "High",
    score: 83,
    technique: "T exfiltration",
  },
  {
    title: "Malware analysis includes sample fingerprints",
    text: "Synthetic technical analysis contains a test fingerprint. Analysts should validate context before promoting an observable into an actionable indicator.",
    topic: "Malware",
    severity: "Medium",
    score: 61,
    technique: "T1059",
  },
  {
    title: "Northstar Cloud service configuration discussed",
    text: "Synthetic discussion of a potentially exposed service on 203.0.113.42. This documentation-only address is not a real exposed host.",
    topic: "Exposure",
    severity: "Medium",
    score: 56,
    technique: "T1190",
  },
  {
    title: "Threat advisory adds investigation context",
    text: "Synthetic analyst advisory summarizes a credential-access technique and defensive checks. No confirmed compromise is established.",
    topic: "Advisory",
    severity: "Low",
    score: 31,
    technique: "T1003",
  },
];
export function emptyData(): DataSet {
  return {
    signals: [],
    indicators: [],
    artifacts: [],
    deployments: [],
    noise: {
      processed: 0,
      accepted: 0,
      rejected: 0,
      reasons: {},
      detectors: {},
      languages: {},
    },
    errors: [],
    loaded: false,
  };
}
export function makeDemo(now = new Date()): DataSet {
  const platforms = Object.keys(platformColors);
  const sources = [
    "Signal Exchange",
    "Breach Research",
    "Threat Notes",
    "Research Wire",
    "Security Roundup",
    "Analyst Journal",
  ];
  const signals: Signal[] = Array.from({ length: 96 }, (_, i) => {
    const t = topics[i % topics.length];
    const p = i % 10 < 5 ? 0 : i % 10 < 7 ? 1 : 2 + (i % 4);
    const daily = [18, 22, 11, 17, 9, 12, 7];
    let day = 0,
      offset = i;
    while (offset >= daily[day]) {
      offset -= daily[day];
      day++;
    }
    const minutesAgo = day * 1440 + 12 + (offset * 1400) / daily[day];
    return {
      ...t,
      id: `DEMO-${String(i + 1).padStart(3, "0")}`,
      source: `${sources[p]} / demo`,
      platform: platforms[p],
      date: new Date(now.getTime() - minutesAgo * 60000).toISOString(),
      status: i % 4 === 0 ? "Needs review" : "Unverified",
      indicators:
        i % 3 === 0 ? [] : [i % 2 ? "signin.aster.example" : "203.0.113.42"],
      forwardedFrom: i % 8 === 0 ? "Research Archive / demo" : undefined,
    };
  });
  const indicators: Indicator[] = Array.from({ length: 32 }, (_, i) => ({
    id: `OBS-${String(i + 1).padStart(3, "0")}`,
    value:
      i % 4 === 0
        ? `203.0.113.${i + 1}`
        : i % 4 === 1
          ? `node${i}.aster.example`
          : i % 4 === 2
            ? `https://lab${i}.orion.example/sample`
            : `${i.toString(16).padStart(64, "0")}`,
    type: ["IPv4", "Domain", "URL", "SHA-256"][i % 4],
    sightings: 2 + (i % 7),
    source: sources[i % 6] + " / demo",
    date: signals[i].date,
    score: 35 + (i % 5) * 12,
    confidence: 52 + (i % 6) * 8,
  }));
  return {
    signals,
    indicators,
    artifacts: [
      {
        name: "research-observables.json",
        type: "stix",
        status: "Example export",
      },
      {
        name: "demo_network_watch.yml",
        type: "sigma",
        status: "Draft · not deployed",
      },
      {
        name: "demo_string_match.yar",
        type: "yara",
        status: "Draft · not deployed",
      },
    ],
    deployments: [
      {
        artifact_id: "demo_network_watch.yml",
        siem_type: "Lab SIEM",
        status: "Simulation only",
        attempted_at: now.toISOString(),
        response_code: "—",
      },
    ],
    noise: {
      processed: 144,
      accepted: 96,
      rejected: 48,
      reasons: { Duplicates: 25, "Off-topic": 16, Spam: 7 },
      detectors: {
        "Language identification": 144,
        "Context relevance": 119,
        "Duplicate comparison": 144,
      },
      languages: { English: 106, Urdu: 24, Other: 14 },
    },
    errors: [],
    loaded: true,
  };
}
export function filterPeriod<T extends { date: string }>(
  rows: T[],
  days: number,
  now = Date.now(),
): T[] {
  return rows.filter((r) => {
    const t = Date.parse(r.date);
    return Number.isFinite(t) && t >= now - days * 86400000 && t <= now;
  });
}
export function countsBy<T>(
  rows: T[],
  key: (row: T) => string,
): [string, number][] {
  return Object.entries(
    rows.reduce<Record<string, number>>((a, r) => {
      const k = key(r);
      a[k] = (a[k] || 0) + 1;
      return a;
    }, {}),
  ).sort((a, b) => b[1] - a[1]);
}
export function downloadFile(
  name: string,
  content: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
// Export observables rather than asserting that all extracted values are malicious STIX Indicators.
export function observableBundle(rows: Indicator[], demo: boolean) {
  const objects = rows.flatMap((r) => {
    const id = crypto.randomUUID();
    if (r.type === "IPv4" || r.type === "ipv4")
      return [
        {
          type: "ipv4-addr",
          spec_version: "2.1",
          id: `ipv4-addr--${id}`,
          value: r.value,
        },
      ];
    if (r.type.toLowerCase() === "domain")
      return [
        {
          type: "domain-name",
          spec_version: "2.1",
          id: `domain-name--${id}`,
          value: r.value,
        },
      ];
    if (r.type.toLowerCase() === "url")
      return [
        { type: "url", spec_version: "2.1", id: `url--${id}`, value: r.value },
      ];
    return [];
  });
  return {
    type: "bundle",
    id: `bundle--${crypto.randomUUID()}`,
    objects,
    x_redtraces_demo: demo,
  };
}
