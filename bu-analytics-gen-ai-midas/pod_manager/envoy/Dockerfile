# Routing-tier Envoy data plane. Config template is rendered at start via env vars;
# ext_authz runs as a separate sidecar image in Kubernetes (see router-tier.yaml).
FROM envoyproxy/envoy:v1.34.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY --chmod=644 envoy.yaml.template /etc/envoy/envoy.yaml.template
COPY --chmod=755 docker-entrypoint.sh /docker-entrypoint.sh

# Fail the image build if rendered config is invalid (RT-9).
RUN /docker-entrypoint.sh envoy --mode validate

EXPOSE 10000 8080 9901

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["envoy", "--service-cluster", "envoy-router"]
