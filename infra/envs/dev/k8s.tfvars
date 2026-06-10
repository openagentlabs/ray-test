containers_workload_extra_environment = {
  arch_diagram_agent_svc = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
  }
  collaboration_svc = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
  }
  document_storage_svc = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
  }
  frontend = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
    ARCH_DIAGRAM_AGENT_SERVICE_GRPC_HOST = "arch-diagram-agent.arb-ai-assistant.svc.cluster.local"
    ARCH_DIAGRAM_AGENT_SERVICE_GRPC_PORT = "8810"
    AUTH_TRUST_HOST = "true"
    COLLABORATION_SERVICE_HOST = "collaboration.arb-ai-assistant.svc.cluster.local"
    COLLABORATION_SERVICE_PORT = "8808"
    DOCUMENT_STORAGE_SERVICE_HOST = "document-storage.arb-ai-assistant.svc.cluster.local"
    DOCUMENT_STORAGE_SERVICE_PORT = "8809"
    FRONTEND_K8S_NAMESPACE = "arb-ai-assistant"
    GENERAL_AI_AGENT_GRPC_HOST = "general-ai-agent.arb-ai-assistant.svc.cluster.local"
    GENERAL_AI_AGENT_GRPC_PORT = "8806"
    HOSTNAME = "0.0.0.0"
    IAM_SERVICE_HOST = "iam.arb-ai-assistant.svc.cluster.local"
    IAM_SERVICE_PORT = "8803"
    NOTIFICATION_SERVICE_GRPC_HOST = "notification.arb-ai-assistant.svc.cluster.local"
    NOTIFICATION_SERVICE_GRPC_PORT = "8807"
    PORT = "8802"
    SOLUTIONS_SERVICE_HOST = "solutions.arb-ai-assistant.svc.cluster.local"
    SOLUTIONS_SERVICE_PORT = "8804"
    STORAGE_SERVICE_GRPC_HOST = "storage.arb-ai-assistant.svc.cluster.local"
    STORAGE_SERVICE_GRPC_PORT = "8805"
  }
  general_ai_agent = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
  }
  iam_svc = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
  }
  notification_svc = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
  }
  solutions_svc = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
  }
  storage_svc = {
    APP_ENV = "dev"
    APP_TARGET = "aws"
    STORAGE_DATABASE_PATH = "/tmp/storage.db"
  }
}
