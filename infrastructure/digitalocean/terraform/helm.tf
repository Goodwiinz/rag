# =============================================================================
# Helm Releases for DigitalOcean RAG System
# =============================================================================

# -----------------------------------------------------------------------------
# NGINX Ingress Controller
# -----------------------------------------------------------------------------

resource "helm_release" "nginx_ingress" {
  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.9.0"
  namespace        = "ingress-nginx"
  create_namespace = true

  values = [<<-EOF
    controller:
      service:
        type: LoadBalancer
        annotations:
          service.beta.kubernetes.io/do-loadbalancer-name: "${var.project_name}-lb"
          service.beta.kubernetes.io/do-loadbalancer-protocol: "http"
          service.beta.kubernetes.io/do-loadbalancer-http-ports: "80"
          service.beta.kubernetes.io/do-loadbalancer-tls-passthrough: "true"
          service.beta.kubernetes.io/do-loadbalancer-enable-proxy-protocol: "false"
          service.beta.kubernetes.io/do-loadbalancer-healthcheck-path: "/healthz"
          service.beta.kubernetes.io/do-loadbalancer-healthcheck-protocol: "http"
        externalTrafficPolicy: Cluster
      config:
        proxy-body-size: "100m"
        proxy-read-timeout: "300"
        proxy-send-timeout: "300"
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 500m
          memory: 512Mi
      metrics:
        enabled: false
    EOF
  ]

  depends_on = [digitalocean_kubernetes_cluster.rag_cluster]
}

# -----------------------------------------------------------------------------
# Cert-Manager for SSL/TLS
# -----------------------------------------------------------------------------

resource "helm_release" "cert_manager" {
  count = var.enable_ssl ? 1 : 0

  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  version          = "1.14.2"
  namespace        = "cert-manager"
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }

  set {
    name  = "prometheus.enabled"
    value = var.enable_monitoring
  }

  depends_on = [digitalocean_kubernetes_cluster.rag_cluster]
}

# Let's Encrypt ClusterIssuer - Created via local-exec after cluster is ready
resource "null_resource" "letsencrypt_issuer" {
  count = var.enable_ssl ? 1 : 0

  provisioner "local-exec" {
    command = <<-EOF
      # Configure kubectl with the new cluster
      doctl kubernetes cluster kubeconfig save ${digitalocean_kubernetes_cluster.rag_cluster.name} --set-current-context

      # Wait for cert-manager to be ready
      sleep 30

      # Apply the ClusterIssuer
      kubectl apply --validate=false -f - <<YAML
      apiVersion: cert-manager.io/v1
      kind: ClusterIssuer
      metadata:
        name: letsencrypt-prod
      spec:
        acme:
          server: https://acme-v02.api.letsencrypt.org/directory
          email: ${var.letsencrypt_email}
          privateKeySecretRef:
            name: letsencrypt-prod-key
          solvers:
          - http01:
              ingress:
                class: nginx
      YAML
    EOF
  }

  depends_on = [
    helm_release.cert_manager,
    helm_release.nginx_ingress,
    digitalocean_kubernetes_cluster.rag_cluster
  ]
}

# -----------------------------------------------------------------------------
# Prometheus & Grafana Monitoring Stack
# -----------------------------------------------------------------------------

resource "helm_release" "prometheus_stack" {
  count = var.enable_monitoring ? 1 : 0

  name             = "prometheus"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = "56.6.2"
  namespace        = "monitoring"
  create_namespace = true

  values = [<<-EOF
    prometheus:
      prometheusSpec:
        retention: 15d
        storageSpec:
          volumeClaimTemplate:
            spec:
              storageClassName: do-block-storage
              accessModes: ["ReadWriteOnce"]
              resources:
                requests:
                  storage: 50Gi
        resources:
          requests:
            cpu: 200m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 2Gi

    alertmanager:
      alertmanagerSpec:
        storage:
          volumeClaimTemplate:
            spec:
              storageClassName: do-block-storage
              accessModes: ["ReadWriteOnce"]
              resources:
                requests:
                  storage: 10Gi

    grafana:
      enabled: true
      adminPassword: "${var.grafana_password}"
      persistence:
        enabled: true
        storageClassName: do-block-storage
        size: 10Gi
      ingress:
        enabled: true
        ingressClassName: nginx
        annotations:
          cert-manager.io/cluster-issuer: letsencrypt-prod
        hosts:
          - grafana.${var.domain_name}
        tls:
          - secretName: grafana-tls
            hosts:
              - grafana.${var.domain_name}
      dashboardProviders:
        dashboardproviders.yaml:
          apiVersion: 1
          providers:
            - name: 'default'
              orgId: 1
              folder: 'RAG System'
              type: file
              disableDeletion: false
              editable: true
              options:
                path: /var/lib/grafana/dashboards/default

    nodeExporter:
      enabled: true

    kubeStateMetrics:
      enabled: true
    EOF
  ]

  depends_on = [
    digitalocean_kubernetes_cluster.rag_cluster,
    helm_release.nginx_ingress
  ]
}

# -----------------------------------------------------------------------------
# Metrics Server (for HPA)
# -----------------------------------------------------------------------------

resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = "3.12.0"
  namespace  = "kube-system"

  set {
    name  = "args"
    value = "{--kubelet-preferred-address-types=InternalIP}"
  }

  depends_on = [digitalocean_kubernetes_cluster.rag_cluster]
}

# -----------------------------------------------------------------------------
# External Secrets Operator (optional - for external secret management)
# -----------------------------------------------------------------------------

# Uncomment if using external secrets management
# resource "helm_release" "external_secrets" {
#   name             = "external-secrets"
#   repository       = "https://charts.external-secrets.io"
#   chart            = "external-secrets"
#   version          = "0.9.11"
#   namespace        = "external-secrets"
#   create_namespace = true
#
#   depends_on = [digitalocean_kubernetes_cluster.rag_cluster]
# }
