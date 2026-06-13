containers_workload_extra_environment = {
  arch_diagram_agent_svc = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
  }
  collaboration_svc = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
  }
  document_storage_svc = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
  }
  frontend = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
    ARCH_DIAGRAM_AGENT_SERVICE_GRPC_HOST = "arch-diagram-agent.ray-test.svc.cluster.local"
    ARCH_DIAGRAM_AGENT_SERVICE_GRPC_PORT = "8810"
    AUTH_TRUST_HOST = "true"
    COLLABORATION_SERVICE_HOST = "collaboration.ray-test.svc.cluster.local"
    COLLABORATION_SERVICE_PORT = "8808"
    DOCUMENT_STORAGE_SERVICE_HOST = "document-storage.ray-test.svc.cluster.local"
    DOCUMENT_STORAGE_SERVICE_PORT = "8809"
    FRONTEND_K8S_NAMESPACE = "ray-test"
    GENERAL_AI_AGENT_GRPC_HOST = "general-ai-agent.ray-test.svc.cluster.local"
    GENERAL_AI_AGENT_GRPC_PORT = "8806"
    HOSTNAME = "0.0.0.0"
    IAM_SERVICE_HOST = "iam.ray-test.svc.cluster.local"
    IAM_SERVICE_PORT = "8803"
    NOTIFICATION_SERVICE_GRPC_HOST = "notification.ray-test.svc.cluster.local"
    NOTIFICATION_SERVICE_GRPC_PORT = "8807"
    PORT = "8802"
    SOLUTIONS_SERVICE_HOST = "solutions.ray-test.svc.cluster.local"
    SOLUTIONS_SERVICE_PORT = "8804"
    STORAGE_SERVICE_GRPC_HOST = "storage.ray-test.svc.cluster.local"
    STORAGE_SERVICE_GRPC_PORT = "8805"
  }
  general_ai_agent = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
  }
  iam_svc = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
  }
  notification_svc = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
  }
  solutions_svc = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
  }
  storage_svc = {
    APP_ENV = "prod"
    APP_TARGET = "aws"
    STORAGE_DATABASE_PATH = "/tmp/storage.db"
  }
}
