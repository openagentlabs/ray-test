/** Checklist item for architecture diagram reviews (id + requirement text). */

export interface ArchDiagramRequirementItem {
  readonly id: string;
  readonly requirement: string;
}

const REQUIREMENTS: readonly ArchDiagramRequirementItem[] = [
  {
    id: "REQ-001",
    requirement:
      "Architecture shows clear monitoring and logging components (e.g. CloudWatch, observability stack)",
  },
  {
    id: "REQ-002",
    requirement:
      "Automated deployment pipelines (CI/CD) are represented or implied for infrastructure and application delivery",
  },
  {
    id: "REQ-003",
    requirement:
      "Runbooks or operational workflows are defined or referenced for failure scenarios",
  },
  {
    id: "REQ-004",
    requirement:
      "Authentication and identity management (e.g. IAM, Cognito) is explicitly shown",
  },
  {
    id: "REQ-005",
    requirement:
      "Data encryption in transit and at rest is represented in the architecture",
  },
  {
    id: "REQ-006",
    requirement:
      "Network boundaries (VPCs, subnets, security groups, firewalls) are clearly defined",
  },
  {
    id: "REQ-007",
    requirement: "Secrets management solution is shown (e.g. Secrets Manager, Vault)",
  },
  {
    id: "REQ-008",
    requirement:
      "High availability design across multiple availability zones or regions is present",
  },
  {
    id: "REQ-009",
    requirement:
      "Failure handling mechanisms (retries, timeouts, dead-letter queues) are visible in design",
  },
  {
    id: "REQ-010",
    requirement:
      "Backup and disaster recovery strategy is represented (e.g. snapshots, replication)",
  },
  {
    id: "REQ-011",
    requirement:
      "Stateless service design or separation of compute and state is evident",
  },
  {
    id: "REQ-012",
    requirement:
      "Scalable compute components (auto scaling groups, serverless, containers) are used",
  },
  {
    id: "REQ-013",
    requirement:
      "Load balancing and traffic distribution components are included (ALB/NLB/API Gateway)",
  },
  {
    id: "REQ-014",
    requirement:
      "Caching layers (e.g. Redis/ElastiCache/CDN) are present for performance optimisation",
  },
  {
    id: "REQ-015",
    requirement:
      "Asynchronous communication patterns (queues, event buses) are used where appropriate",
  },
  {
    id: "REQ-016",
    requirement:
      "Cost management mechanisms are visible (e.g. tagging, lifecycle policies, serverless usage)",
  },
  {
    id: "REQ-017",
    requirement: "Idle resource avoidance or scale-to-zero patterns are implemented",
  },
  {
    id: "REQ-018",
    requirement: "Data lifecycle management (archival, deletion policies) is defined",
  },
  {
    id: "REQ-019",
    requirement:
      "Sustainability considerations (efficient compute, batching, minimised data movement) are reflected",
  },
  {
    id: "REQ-020",
    requirement:
      "Clear separation of concerns (microservices, layered architecture, modular components) is shown",
  },
];

/** Static access to the architecture diagram requirement checklist. */
export class ArchDiagramRequirements {
  static items(): readonly ArchDiagramRequirementItem[] {
    return REQUIREMENTS;
  }
}
