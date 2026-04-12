"""Rule-based architecture diagram generation service.

Parses natural language prompts and produces structured diagram data
without requiring an LLM.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class RawNode:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    label: str = ""
    node_type: str = "generic"
    provider: str = "generic"
    x: float = 0.0
    y: float = 0.0
    group: str = "default"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RawEdge:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_id: uuid.UUID = field(default_factory=uuid.uuid4)
    target_id: uuid.UUID = field(default_factory=uuid.uuid4)
    label: str = ""


@dataclass
class RawComponent:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    component_type: str = "generic"
    provider: str = "generic"
    description: str = ""
    role_summary: str = ""


class GeneratedDiagram(NamedTuple):
    nodes: list[RawNode]
    edges: list[RawEdge]
    components: list[RawComponent]
    notes_markdown: str
    version_number: int = 1


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

_PROVIDER_KEYWORDS: dict[str, list[str]] = {
    "azure": [
        "azure",
        "aks",
        "app gateway",
        "application gateway",
        "azure sql",
        "cosmos",
        "cosmosdb",
        "azure firewall",
        "azure functions",
        "service bus",
        "event hub",
        "blob storage",
        "azure monitor",
        "log analytics",
        "azure ad",
        "entra",
        "vnet",
        "hub and spoke",
        "azure container",
        "acr",
    ],
    "aws": [
        "aws",
        "eks",
        "lambda",
        "api gateway",
        "sqs",
        "sns",
        "dynamodb",
        "rds",
        "s3",
        "cloudwatch",
        "cloudfront",
        "ec2",
        "ecs",
        "fargate",
        "cognito",
        "kinesis",
        "elasticache",
        "aurora",
        "route53",
    ],
    "gcp": [
        "gcp",
        "google cloud",
        "gke",
        "cloud run",
        "bigquery",
        "pubsub",
        "pub/sub",
        "cloud sql",
        "firestore",
        "cloud storage",
        "cloud functions",
        "stackdriver",
        "anthos",
    ],
    "on-prem": [
        "on-prem",
        "on premise",
        "on-premises",
        "datacenter",
        "data center",
        "bare metal",
        "vmware",
        "hyper-v",
    ],
}


def detect_provider(text: str) -> str:
    lower = text.lower()
    for provider, keywords in _PROVIDER_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return provider
    return "generic"


# ---------------------------------------------------------------------------
# Component detection
# ---------------------------------------------------------------------------


@dataclass
class ComponentSpec:
    label: str
    node_type: str
    group: str
    description: str
    role_summary: str
    keywords: list[str]


_COMPONENT_SPECS: list[ComponentSpec] = [
    ComponentSpec(
        label="Firewall",
        node_type="firewall",
        group="Hub Network",
        description="Network firewall for traffic inspection and control",
        role_summary="Filters inbound/outbound traffic between network zones",
        keywords=["firewall", "azure firewall", "palo alto", "fortinet", "nva"],
    ),
    ComponentSpec(
        label="Application Gateway",
        node_type="load_balancer",
        group="Hub Network",
        description="Layer-7 load balancer and WAF",
        role_summary="Routes HTTP/HTTPS traffic to backends with WAF protection",
        keywords=["app gateway", "application gateway", "waf", "agw"],
    ),
    ComponentSpec(
        label="Load Balancer",
        node_type="load_balancer",
        group="Ingress",
        description="Network load balancer distributing traffic",
        role_summary="Distributes incoming requests across backend instances",
        keywords=["load balancer", "nlb", "alb", "elb", "layer 4 lb", "l4 lb"],
    ),
    ComponentSpec(
        label="API Gateway",
        node_type="api_gateway",
        group="Ingress",
        description="Managed API gateway for routing and auth",
        role_summary="Manages API endpoints, auth, rate-limiting, and routing",
        keywords=["api gateway", "apigw", "api management", "apim", "kong"],
    ),
    ComponentSpec(
        label="Kubernetes Cluster",
        node_type="kubernetes",
        group="Compute",
        description="Container orchestration cluster",
        role_summary="Runs containerized workloads at scale",
        keywords=["aks", "eks", "gke", "kubernetes", "k8s", "container"],
    ),
    ComponentSpec(
        label="Serverless Function",
        node_type="serverless",
        group="Compute",
        description="Event-driven serverless compute",
        role_summary="Executes code in response to events without managing servers",
        keywords=[
            "function",
            "lambda",
            "cloud function",
            "serverless",
            "azure functions",
        ],
    ),
    ComponentSpec(
        label="Virtual Machine",
        node_type="vm",
        group="Compute",
        description="Virtual machine instance",
        role_summary="Hosts application workloads on managed virtual machines",
        keywords=["vm", "virtual machine", "ec2", "compute engine", "vms"],
    ),
    ComponentSpec(
        label="Container Registry",
        node_type="registry",
        group="Compute",
        description="Container image registry",
        role_summary="Stores and distributes container images",
        keywords=["container registry", "acr", "ecr", "gcr", "docker registry"],
    ),
    ComponentSpec(
        label="SQL Database",
        node_type="database",
        group="Data Layer",
        description="Relational SQL database",
        role_summary="Stores relational, transactional application data",
        keywords=[
            "sql",
            "postgres",
            "mysql",
            "mariadb",
            "azure sql",
            "aurora",
            "rds",
            "cloud sql",
        ],
    ),
    ComponentSpec(
        label="NoSQL Database",
        node_type="nosql",
        group="Data Layer",
        description="NoSQL/document database",
        role_summary="Stores flexible schema document or key-value data",
        keywords=[
            "nosql",
            "cosmosdb",
            "cosmos",
            "dynamodb",
            "firestore",
            "mongodb",
            "cassandra",
        ],
    ),
    ComponentSpec(
        label="Cache",
        node_type="cache",
        group="Data Layer",
        description="In-memory caching layer",
        role_summary="Reduces database load by caching frequently accessed data",
        keywords=["redis", "cache", "memcached", "elasticache", "azure cache"],
    ),
    ComponentSpec(
        label="Object Storage",
        node_type="storage",
        group="Data Layer",
        description="Blob / object storage",
        role_summary="Stores unstructured data such as files, images, and backups",
        keywords=[
            "storage",
            "blob",
            "s3",
            "cloud storage",
            "object storage",
            "datalake",
        ],
    ),
    ComponentSpec(
        label="Message Queue",
        node_type="queue",
        group="Messaging",
        description="Message queue for decoupled async communication",
        role_summary="Decouples producers and consumers via asynchronous messaging",
        keywords=["sqs", "queue", "rabbitmq", "activemq", "azure storage queue"],
    ),
    ComponentSpec(
        label="Service Bus / Event Hub",
        node_type="service_bus",
        group="Messaging",
        description="Enterprise messaging and event streaming",
        role_summary="Provides reliable message delivery and event streaming",
        keywords=[
            "service bus",
            "event hub",
            "eventhub",
            "kafka",
            "sns",
            "pubsub",
            "pub/sub",
            "kinesis",
        ],
    ),
    ComponentSpec(
        label="CDN",
        node_type="cdn",
        group="Ingress",
        description="Content delivery network",
        role_summary="Caches and serves static content close to end users",
        keywords=["cdn", "cloudfront", "akamai", "fastly", "azure cdn"],
    ),
    ComponentSpec(
        label="DNS",
        node_type="dns",
        group="Ingress",
        description="DNS service for name resolution",
        role_summary="Resolves domain names and routes traffic globally",
        keywords=["dns", "route53", "azure dns", "cloud dns"],
    ),
    ComponentSpec(
        label="Monitoring & Logging",
        node_type="monitoring",
        group="Observability",
        description="Centralized monitoring, logging, and alerting",
        role_summary="Collects metrics, logs, and traces for observability",
        keywords=[
            "monitoring",
            "log analytics",
            "cloudwatch",
            "stackdriver",
            "prometheus",
            "grafana",
            "datadog",
            "splunk",
            "elk",
            "observability",
            "logging",
            "azure monitor",
        ],
    ),
    ComponentSpec(
        label="Identity Provider",
        node_type="identity",
        group="Security",
        description="Authentication and identity service",
        role_summary="Manages user identities and issues access tokens",
        keywords=["ad", "azure ad", "entra", "cognito", "okta", "iam", "identity"],
    ),
    ComponentSpec(
        label="Private Endpoint",
        node_type="private_endpoint",
        group="Network",
        description="Private connectivity to PaaS services",
        role_summary="Connects to PaaS services via private IP without public exposure",
        keywords=["private endpoint", "private link", "privatelink"],
    ),
    ComponentSpec(
        label="VPN Gateway",
        node_type="vpn",
        group="Hub Network",
        description="VPN gateway for on-premises connectivity",
        role_summary="Provides encrypted site-to-site or point-to-site VPN connectivity",
        keywords=["vpn", "vpn gateway", "site-to-site", "p2s"],
    ),
    ComponentSpec(
        label="App Server",
        node_type="app_server",
        group="Compute",
        description="Application server tier",
        role_summary="Hosts business logic and application services",
        keywords=["app server", "application server", "web server", "backend server"],
    ),
]


def detect_components(text: str) -> list[ComponentSpec]:
    """Return component specs whose keywords appear in text (de-duplicated)."""
    lower = text.lower()
    found: list[ComponentSpec] = []
    seen_labels: set[str] = set()
    for spec in _COMPONENT_SPECS:
        if spec.label in seen_labels:
            continue
        for kw in spec.keywords:
            if kw in lower:
                found.append(spec)
                seen_labels.add(spec.label)
                break
    return found


# ---------------------------------------------------------------------------
# Pattern matchers for well-known architecture styles
# ---------------------------------------------------------------------------


def _is_hub_spoke(text: str) -> bool:
    lower = text.lower()
    return "hub" in lower and (
        "spoke" in lower or "hub and spoke" in lower or "hub-and-spoke" in lower
    )


def _is_serverless(text: str) -> bool:
    lower = text.lower()
    return "serverless" in lower or (
        ("lambda" in lower or "function" in lower)
        and ("event" in lower or "trigger" in lower or "queue" in lower)
    )


def _is_three_tier(text: str) -> bool:
    lower = text.lower()
    return (
        "3-tier" in lower
        or "3 tier" in lower
        or "three-tier" in lower
        or "three tier" in lower
    )


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

_GROUP_Y_SLOTS: dict[str, float] = {
    "Ingress": 0,
    "Hub Network": 100,
    "Network": 200,
    "Compute": 300,
    "Messaging": 400,
    "Data Layer": 500,
    "Security": 600,
    "Observability": 700,
    "default": 800,
}

_X_GAP = 220
_Y_BASE = 50


def assign_positions(nodes: list[RawNode]) -> None:
    """Assign x/y grid positions based on group."""
    group_counters: dict[str, int] = {}
    for node in nodes:
        group = node.group
        idx = group_counters.get(group, 0)
        group_counters[group] = idx + 1
        y_offset = _GROUP_Y_SLOTS.get(group, 800)
        node.x = float(idx * _X_GAP + 50)
        node.y = float(_Y_BASE + y_offset)


# ---------------------------------------------------------------------------
# Edge generation heuristics
# ---------------------------------------------------------------------------


def _find_by_type(nodes: list[RawNode], *types: str) -> RawNode | None:
    for n in nodes:
        if n.node_type in types:
            return n
    return None


def _find_all_by_type(nodes: list[RawNode], *types: str) -> list[RawNode]:
    return [n for n in nodes if n.node_type in types]


def _find_by_group(nodes: list[RawNode], group: str) -> list[RawNode]:
    return [n for n in nodes if n.group == group]


def generate_edges(nodes: list[RawNode]) -> list[RawEdge]:
    """Generate reasonable edges between detected nodes."""
    edges: list[RawEdge] = []

    def edge(src: RawNode, dst: RawNode, label: str = "") -> None:
        edges.append(RawEdge(source_id=src.id, target_id=dst.id, label=label))

    _find_by_type(nodes, "cdn", "load_balancer", "api_gateway")
    gateways = _find_all_by_type(nodes, "api_gateway", "load_balancer")
    firewall = _find_by_type(nodes, "firewall")
    computes = _find_all_by_type(nodes, "kubernetes", "serverless", "vm", "app_server")
    databases = _find_all_by_type(nodes, "database", "nosql")
    caches = _find_all_by_type(nodes, "cache")
    queues = _find_all_by_type(nodes, "queue", "service_bus")
    storages = _find_all_by_type(nodes, "storage")
    monitoring = _find_by_type(nodes, "monitoring")
    identity = _find_by_type(nodes, "identity")
    private_eps = _find_all_by_type(nodes, "private_endpoint")
    cdn = _find_by_type(nodes, "cdn")
    dns = _find_by_type(nodes, "dns")

    # DNS -> CDN or first ingress
    if dns:
        target = cdn or (
            gateways[0] if gateways else (firewall or computes[0] if computes else None)
        )
        if target:
            edge(dns, target, "resolve")

    # CDN -> first gateway or firewall
    if cdn:
        target = gateways[0] if gateways else firewall
        if target:
            edge(cdn, target, "forward")

    # Firewall -> gateways or computes
    if firewall:
        for gw in gateways:
            edge(firewall, gw, "allow")
        if not gateways:
            for c in computes:
                edge(firewall, c, "allow")

    # Gateways -> computes
    for gw in gateways:
        for c in computes:
            edge(gw, c, "route")

    # Computes -> databases
    for c in computes:
        for db in databases:
            edge(c, db, "read/write")

    # Computes -> caches
    for c in computes:
        for ca in caches:
            edge(c, ca, "cache")

    # Computes -> queues
    for c in computes:
        for q in queues:
            edge(c, q, "publish")

    # Queues -> computes (fan-out triggers)
    for q in queues:
        for c in computes:
            edge(q, c, "trigger")

    # Computes -> storage
    for c in computes:
        for s in storages:
            edge(c, s, "store")

    # Private endpoints -> databases/storage
    for pe in private_eps:
        for db in databases:
            edge(pe, db, "private")
        for s in storages:
            edge(pe, s, "private")

    # Identity -> computes
    if identity:
        for c in computes:
            edge(identity, c, "auth")

    # Monitoring collects from everything
    if monitoring:
        for n in nodes:
            if n.id != monitoring.id and n.node_type not in ("monitoring",):
                edge(n, monitoring, "telemetry")

    # De-duplicate edges (same src/dst)
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    unique: list[RawEdge] = []
    for e in edges:
        key = (e.source_id, e.target_id)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique


# ---------------------------------------------------------------------------
# Notes generation
# ---------------------------------------------------------------------------


def generate_notes(provider: str, components: list[ComponentSpec], text: str) -> str:
    lines = [
        "# Architecture Notes",
        "",
        f"**Cloud Provider:** {provider.upper()}",
        "",
        "## Overview",
        "",
        "This architecture was generated from the following prompt:",
        "",
        f"> {text}",
        "",
        "## Components",
        "",
    ]
    for spec in components:
        lines.append(f"### {spec.label}")
        lines.append("")
        lines.append(f"- **Type:** {spec.node_type}")
        lines.append(f"- **Group:** {spec.group}")
        lines.append(f"- **Description:** {spec.description}")
        lines.append(f"- **Role:** {spec.role_summary}")
        lines.append("")

    if _is_hub_spoke(text):
        lines += [
            "## Topology: Hub and Spoke",
            "",
            "The hub VNet hosts shared services (firewall, gateway, DNS) and peers "
            "to spoke VNets that host workloads. All inter-spoke traffic transits "
            "through the hub for centralised security inspection.",
            "",
        ]
    elif _is_serverless(text):
        lines += [
            "## Topology: Serverless / Event-Driven",
            "",
            "Functions or Lambda handlers are triggered by events from queues or "
            "event streams. The architecture scales to zero when idle and processes "
            "events concurrently.",
            "",
        ]
    elif _is_three_tier(text):
        lines += [
            "## Topology: 3-Tier",
            "",
            "Classic web tier → application tier → data tier pattern. The load "
            "balancer distributes incoming requests to the application servers, "
            "which in turn query the database.",
            "",
        ]

    lines += [
        "## Security Considerations",
        "",
        "- All inter-tier communication should use TLS.",
        "- Apply least-privilege IAM policies to each component.",
        "- Enable diagnostic logs and forward to the observability stack.",
        "",
        "## Scalability",
        "",
        "- Compute tiers can be horizontally scaled.",
        "- Managed database services provide automated failover.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_architecture(
    prompt: str,
    cloud_context: str | None = None,
    diagram_type: str | None = None,
    version_number: int = 1,
) -> GeneratedDiagram:
    """Parse *prompt* and return a fully structured diagram."""
    combined = " ".join(filter(None, [prompt, cloud_context, diagram_type]))
    provider = detect_provider(combined)
    specs = detect_components(combined)

    # Fallback: generic 3-tier if nothing detected
    if not specs:
        specs = [
            ComponentSpec(
                label="Load Balancer",
                node_type="load_balancer",
                group="Ingress",
                description="Network load balancer",
                role_summary="Distributes incoming traffic",
                keywords=[],
            ),
            ComponentSpec(
                label="App Server",
                node_type="app_server",
                group="Compute",
                description="Application server",
                role_summary="Hosts application logic",
                keywords=[],
            ),
            ComponentSpec(
                label="Database",
                node_type="database",
                group="Data Layer",
                description="Relational database",
                role_summary="Stores application data",
                keywords=[],
            ),
        ]

    nodes: list[RawNode] = []
    for spec in specs:
        nodes.append(
            RawNode(
                label=f"{provider.upper()} {spec.label}"
                if provider != "generic"
                else spec.label,
                node_type=spec.node_type,
                provider=provider,
                group=spec.group,
            )
        )

    assign_positions(nodes)
    edges = generate_edges(nodes)
    notes = generate_notes(provider, specs, prompt)

    raw_components = [
        RawComponent(
            name=spec.label,
            component_type=spec.node_type,
            provider=provider,
            description=spec.description,
            role_summary=spec.role_summary,
        )
        for spec in specs
    ]

    return GeneratedDiagram(
        nodes=nodes,
        edges=edges,
        components=raw_components,
        notes_markdown=notes,
        version_number=version_number,
    )


def refine_architecture(
    existing_prompt: str,
    refinement_prompt: str,
    cloud_context: str | None = None,
    diagram_type: str | None = None,
    version_number: int = 2,
) -> GeneratedDiagram:
    """Merge the existing prompt with the refinement and regenerate."""
    merged = f"{existing_prompt}. Refinement: {refinement_prompt}"
    return generate_architecture(
        merged,
        cloud_context=cloud_context,
        diagram_type=diagram_type,
        version_number=version_number,
    )
