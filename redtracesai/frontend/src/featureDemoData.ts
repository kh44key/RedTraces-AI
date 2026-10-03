const minutesAgo = (minutes: number) =>
  new Date(Date.now() - minutes * 60_000).toISOString();

export type StoredIOC = {
  stix_id: string;
  ioc_value: string;
  ioc_type: string;
  source_id: string | null;
  first_seen: string;
  last_seen: string;
  sighting_count: number;
};

export type RuleArtifact = {
  name: string;
  artifact_type: "stix" | "sigma" | "yara";
  size_bytes: number;
  modified_at: string;
  status: string;
};

export type SIEMPush = {
  id: number;
  attempted_at: string;
  siem_type: string;
  artifact_type: string;
  artifact_id: string | null;
  status: "success" | "failure" | "manual_required";
  endpoint: string | null;
  response_code: number | null;
  message: string;
};

export const DEMO_STORED_IOCS: StoredIOC[] = [
  {
    stix_id: "indicator--573381dd-f13c-4f74-91bc-c2e847c7b921",
    ioc_value: "203.0.113.77",
    ioc_type: "ipv4",
    source_id: "identity--0b415b29-6f0f-4ddd-ae62-b985c215d155",
    first_seen: minutesAgo(46),
    last_seen: minutesAgo(2),
    sighting_count: 4,
  },
  {
    stix_id: "indicator--62efae21-1eb8-44f1-9813-274b67ae716a",
    ioc_value: "secure-docs.example",
    ioc_type: "domain",
    source_id: "identity--f4075ccd-2ba4-4eb8-8ca2-e125f581c636",
    first_seen: minutesAgo(37),
    last_seen: minutesAgo(4),
    sighting_count: 3,
  },
  {
    stix_id: "indicator--bbc71715-cc0d-48aa-95e5-ec3bf2c404ea",
    ioc_value: "https://payload.example/dropper",
    ioc_type: "url",
    source_id: "identity--7308fa5d-50df-46f6-884d-f596a225699d",
    first_seen: minutesAgo(31),
    last_seen: minutesAgo(11),
    sighting_count: 2,
  },
  {
    stix_id: "indicator--00c6c7cf-9e89-4c62-9194-781fa6a2b7aa",
    ioc_value: "8f27d01a1d3b9c6e787462295a51bd86e5afc560d7cc8c871d6ab3f0129e45ab",
    ioc_type: "sha256",
    source_id: "identity--0b415b29-6f0f-4ddd-ae62-b985c215d155",
    first_seen: minutesAgo(21),
    last_seen: minutesAgo(8),
    sighting_count: 2,
  },
  {
    stix_id: "indicator--4d9585df-97e5-46c8-9160-698961101d37",
    ioc_value: "198.51.100.64",
    ioc_type: "ipv4",
    source_id: "identity--f4075ccd-2ba4-4eb8-8ca2-e125f581c636",
    first_seen: minutesAgo(14),
    last_seen: minutesAgo(14),
    sighting_count: 1,
  },
];

export const DEMO_ARTIFACTS: RuleArtifact[] = [
  {
    name: "20260802T145830.219440Z.json",
    artifact_type: "stix",
    size_bytes: 18432,
    modified_at: minutesAgo(18),
    status: "validated bundle",
  },
  {
    name: "2026-08-02.yml",
    artifact_type: "sigma",
    size_bytes: 4268,
    modified_at: minutesAgo(12),
    status: "3 rules generated",
  },
  {
    name: "2026-08-02.yar",
    artifact_type: "yara",
    size_bytes: 3120,
    modified_at: minutesAgo(9),
    status: "7 blocks compiled",
  },
  {
    name: "20260802T132117.881020Z.json",
    artifact_type: "stix",
    size_bytes: 12680,
    modified_at: minutesAgo(76),
    status: "validated bundle",
  },
];

export const DEMO_PUSH_LOG: SIEMPush[] = [
  {
    id: 12,
    attempted_at: minutesAgo(3),
    siem_type: "splunk",
    artifact_type: "sigma",
    artifact_id: "470ce7b7-18dc-5fc8-b1a2-8c19491ed3b1",
    status: "success",
    endpoint: "https://splunk.lab:8089/servicesNS/nobody/search/saved/searches",
    response_code: 201,
    message: "Sigma rule converted and pushed successfully",
  },
  {
    id: 11,
    attempted_at: minutesAgo(6),
    siem_type: "elastic",
    artifact_type: "sigma",
    artifact_id: "ea32fa16-b404-573d-902f-f30976bd763c",
    status: "success",
    endpoint: "https://kibana.lab/api/detection_engine/rules",
    response_code: 200,
    message: "Sigma rule converted and pushed successfully",
  },
  {
    id: 10,
    attempted_at: minutesAgo(9),
    siem_type: "wazuh",
    artifact_type: "sigma",
    artifact_id: "4122af16-8e26-5202-a640-6b54a69dde4d",
    status: "success",
    endpoint: "https://wazuh-indexer.lab:9200/_plugins/_alerting/monitors",
    response_code: 201,
    message: "Sigma rule converted and pushed successfully",
  },
  {
    id: 9,
    attempted_at: minutesAgo(13),
    siem_type: "qradar",
    artifact_type: "sigma",
    artifact_id: "4122af16-8e26-5202-a640-6b54a69dde4d",
    status: "manual_required",
    endpoint: null,
    response_code: null,
    message: "Approved QRadar integration endpoint required",
  },
  {
    id: 8,
    attempted_at: minutesAgo(15),
    siem_type: "elastic",
    artifact_type: "yara",
    artifact_id: "2026-08-02.yar",
    status: "manual_required",
    endpoint: null,
    response_code: null,
    message: "No YARA/EDR upload endpoint configured; manual deployment required",
  },
];
