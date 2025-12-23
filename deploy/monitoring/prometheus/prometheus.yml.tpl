global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: vllm
    static_configs:
      - targets: ["{{ include "ior.fullname" . }}-vllm:8000"]
    metrics_path: /metrics
  - job_name: gateway
    static_configs:
      - targets: ["{{ include "ior.fullname" . }}-gateway:{{ .Values.gateway.service.port }}"]
    metrics_path: /v1/health
    scheme: http
