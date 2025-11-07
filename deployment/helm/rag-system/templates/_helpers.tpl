{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "rag-system.name" -}}
{{- default .Chart.Name .Values.global.name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "rag-system.fullname" -}}
{{- if .Values.global.fullnameOverride }}
{{- .Values.global.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.global.name }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "rag-system.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rag-system.labels" -}}
helm.sh/chart: {{ include "rag-system.chart" . }}
{{ include "rag-system.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rag-system.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-system.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "rag-system.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "rag-system.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create a default fully qualified namespace name.
*/}}
{{- define "rag-system.namespace" -}}
{{- default .Release.Namespace .Values.global.namespace | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Get the appropriate image registry
*/}}
{{- define "rag-system.imageRegistry" -}}
{{- if .Values.global.imageRegistry }}
{{- .Values.global.imageRegistry }}
{{- else }}
{{- .Values.image.registry }}
{{- end }}
{{- end }}

{{/*
Get the appropriate image repository
*/}}
{{- define "rag-system.imageRepository" -}}
{{- if .Values.global.imageRegistry }}
{{- .Values.global.imageRegistry }}/{{ .Values.image.repository }}
{{- else }}
{{- .Values.image.repository }}
{{- end }}
{{- end }}

{{/*
Get the appropriate image tag
*/}}
{{- define "rag-system.imageTag" -}}
{{- if .Values.image.tag }}
{{- .Values.image.tag }}
{{- else }}
{{- default .Chart.AppVersion .Values.image.tag }}
{{- end }}
{{- end }}

{{/*
Get the appropriate image pull policy
*/}}
{{- define "rag-system.imagePullPolicy" -}}
{{- if .Values.image.pullPolicy }}
{{- .Values.image.pullPolicy }}
{{- else }}
{{- default "IfNotPresent" .Values.image.pullPolicy }}
{{- end }}
{{- end }}

{{/*
Get the appropriate resource requests
*/}}
{{- define "rag-system.resources" -}}
resources:
  requests:
    memory: {{ .Values.resources.requests.memory | default "256Mi" }}
    cpu: {{ .Values.resources.requests.cpu | default "125m" }}
  limits:
    memory: {{ .Values.resources.limits.memory | default "512Mi" }}
    cpu: {{ .Values.resources.limits.cpu | default "250m" }}
{{- end }}

{{/*
Get the appropriate liveness probe
*/}}
{{- define "rag-system.livenessProbe" -}}
livenessProbe:
  httpGet:
    path: {{ .Values.livenessProbe.httpGet.path | default "/" }}
    port: {{ .Values.livenessProbe.httpGet.port | default "80" }}
  initialDelaySeconds: {{ .Values.livenessProbe.initialDelaySeconds | default "30" }}
  periodSeconds: {{ .Values.livenessProbe.periodSeconds | default "10" }}
  timeoutSeconds: {{ .Values.livenessProbe.timeoutSeconds | default "5" }}
  failureThreshold: {{ .Values.livenessProbe.failureThreshold | default "3" }}
{{- end }}

{{/*
Get the appropriate readiness probe
*/}}
{{- define "rag-system.readinessProbe" -}}
readinessProbe:
  httpGet:
    path: {{ .Values.readinessProbe.httpGet.path | default "/" }}
    port: {{ .Values.readinessProbe.httpGet.port | default "80" }}
  initialDelaySeconds: {{ .Values.readinessProbe.initialDelaySeconds | default "15" }}
  periodSeconds: {{ .Values.readinessProbe.periodSeconds | default "5" }}
  timeoutSeconds: {{ .Values.readinessProbe.timeoutSeconds | default "3" }}
  failureThreshold: {{ .Values.readinessProbe.failureThreshold | default "2" }}
{{- end }}

{{/*
Get the appropriate service type
*/}}
{{- define "rag-system.serviceType" -}}
{{- if .Values.service.type }}
{{- .Values.service.type }}
{{- else }}
{{- default "ClusterIP" .Values.service.type }}
{{- end }}
{{- end }}

{{/*
Get the appropriate service port
*/}}
{{- define "rag-system.servicePort" -}}
{{- if .Values.service.port }}
{{- .Values.service.port }}
{{- else }}
{{- default "80" .Values.service.port }}
{{- end }}
{{- end }}

{{/*
Get the appropriate service target port
*/}}
{{- define "rag-system.serviceTargetPort" -}}
{{- if .Values.service.targetPort }}
{{- .Values.service.targetPort }}
{{- else }}
{{- default "80" .Values.service.targetPort }}
{{- end }}
{{- end }}

{{/*
Get the appropriate service name
*/}}
{{- define "rag-system.serviceName" -}}
{{- if .Values.service.name }}
{{- .Values.service.name }}
{{- else }}
{{- include "rag-system.fullname" . }}
{{- end }}
{{- end }}

{{/*
Get the appropriate deployment name
*/}}
{{- define "rag-system.deploymentName" -}}
{{- if .Values.deployment.name }}
{{- .Values.deployment.name }}
{{- else }}
{{- include "rag-system.fullname" . }}
{{- end }}
{{- end }}

{{/*
Get the appropriate replica count
*/}}
{{- define "rag-system.replicaCount" -}}
{{- if .Values.replicaCount }}
{{- .Values.replicaCount }}
{{- else }}
{{- default "1" .Values.replicaCount }}
{{- end }}
{{- end }}

{{/*
Get the appropriate pod anti-affinity
*/}}
{{- define "rag-system.podAntiAffinity" -}}
{{- if .Values.podAntiAffinity.enabled }}
podAntiAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 100
    podAffinityTerm:
      labelSelector:
        matchExpressions:
        - key: app
          operator: In
          values: [{{ .Values.podAntiAffinity.label }}]
      topologyKey: "kubernetes.io/hostname"
{{- end }}
{{- end }}

{{/*
Get the appropriate node affinity
*/}}
{{- define "rag-system.nodeAffinity" -}}
{{- if .Values.nodeAffinity.enabled }}
nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
    - matchExpressions:
      - key: {{ .Values.nodeAffinity.key }}
        operator: {{ .Values.nodeAffinity.operator }}
        values: {{ .Values.nodeAffinity.values }}
{{- end }}
{{- end }}

{{/*
Get the appropriate tolerations
*/}}
{{- define "rag-system.tolerations" -}}
{{- if .Values.tolerations }}
tolerations:
{{- toYaml .Values.tolerations | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Get the appropriate security context
*/}}
{{- define "rag-system.securityContext" -}}
securityContext:
  runAsNonRoot: {{ .Values.securityContext.runAsNonRoot | default true }}
  runAsUser: {{ .Values.securityContext.runAsUser | default 1000 }}
  runAsGroup: {{ .Values.securityContext.runAsGroup | default 1000 }}
  capabilities:
    drop: {{ .Values.securityContext.capabilities.drop | default ["ALL"] }}
  allowPrivilegeEscalation: {{ .Values.securityContext.allowPrivilegeEscalation | default false }}
  readOnlyRootFilesystem: {{ .Values.securityContext.readOnlyRootFilesystem | default true }}
{{- end }}

{{/*
Get the appropriate container security context
*/}}
{{- define "rag-system.containerSecurityContext" -}}
securityContext:
  allowPrivilegeEscalation: {{ .Values.securityContext.allowPrivilegeEscalation | default false }}
  readOnlyRootFilesystem: {{ .Values.securityContext.readOnlyRootFilesystem | default true }}
  runAsNonRoot: {{ .Values.securityContext.runAsNonRoot | default true }}
  capabilities:
    drop: {{ .Values.securityContext.capabilities.drop | default ["ALL"] }}
{{- end }}

{{/*
Get the appropriate environment variables
*/}}
{{- define "rag-system.env" -}}
env:
{{- range $key, $value := .Values.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- end }}

{{/*
Get the appropriate volume mounts
*/}}
{{- define "rag-system.volumeMounts" -}}
{{- if .Values.volumeMounts }}
volumeMounts:
{{- toYaml .Values.volumeMounts | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Get the appropriate volumes
*/}}
{{- define "rag-system.volumes" -}}
{{- if .Values.volumes }}
volumes:
{{- toYaml .Values.volumes | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Get the appropriate pod disruption budget
*/}}
{{- define "rag-system.podDisruptionBudget" -}}
{{- if .Values.podDisruptionBudget.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
spec:
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable }}
  maxUnavailable: {{ .Values.podDisruptionBudget.maxUnavailable }}
{{- end }}
{{- end }}

{{/*
Get the appropriate horizontal pod autoscaler
*/}}
{{- define "rag-system.horizontalPodAutoscaler" -}}
{{- if .Values.horizontalPodAutoscaler.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "rag-system.deploymentName" . }}
  minReplicas: {{ .Values.horizontalPodAutoscaler.minReplicas }}
  maxReplicas: {{ .Values.horizontalPodAutoscaler.maxReplicas }}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {{ .Values.horizontalPodAutoscaler.targetCPUUtilization }}
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: {{ .Values.horizontalPodAutoscaler.targetMemoryUtilization }}
  behavior:
    scaleUp:
      stabilizationWindowSeconds: {{ .Values.horizontalPodAutoscaler.scaleUpStabilizationWindowSeconds | default "60" }}
      policies:
      - type: Percent
        value: {{ .Values.horizontalPodAutoscaler.scaleUpPercent | default "50" }}
        periodSeconds: {{ .Values.horizontalPodAutoscaler.scaleUpPeriodSeconds | default "60" }}
      - type: Pods
        value: {{ .Values.horizontalPodAutoscaler.scaleUpPods | default "3" }}
        periodSeconds: {{ .Values.horizontalPodAutoscaler.scaleUpPeriodSeconds | default "60" }}
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: {{ .Values.horizontalPodAutoscaler.scaleDownStabilizationWindowSeconds | default "300" }}
      policies:
      - type: Percent
        value: {{ .Values.horizontalPodAutoscaler.scaleDownPercent | default "10" }}
        periodSeconds: {{ .Values.horizontalPodAutoscaler.scaleDownPeriodSeconds | default "60" }}
      - type: Pods
        value: {{ .Values.horizontalPodAutoscaler.scaleDownPods | default "2" }}
        periodSeconds: {{ .Values.horizontalPodAutoscaler.scaleDownPeriodSeconds | default "60" }}
      selectPolicy: Min
{{- end }}
{{- end }}

{{/*
Get the appropriate ingress configuration
*/}}
{{- define "rag-system.ingress" -}}
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    {{- if .Values.ingress.annotations }}
    {{- toYaml .Values.ingress.annotations | nindent 4 }}
    {{- end }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  tls:
  - hosts:
    - {{ .Values.ingress.host }}
    secretName: {{ .Values.ingress.tls.secretName }}
  rules:
  - host: {{ .Values.ingress.host }}
    http:
      paths:
      - path: {{ .Values.ingress.path }}
        pathType: {{ .Values.ingress.pathType }}
        backend:
          service:
            name: {{ include "rag-system.serviceName" . }}
            port:
              number: {{ include "rag-system.servicePort" . }}
{{- end }}
{{- end }}

{{/*
Get the appropriate service monitor configuration
*/}}
{{- define "rag-system.serviceMonitor" -}}
{{- if .Values.serviceMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
spec:
  selector:
    matchLabels:
      {{- include "rag-system.selectorLabels" . | nindent 6 }}
  endpoints:
  - port: {{ .Values.serviceMonitor.portName }}
    interval: {{ .Values.serviceMonitor.interval }}
    path: {{ .Values.serviceMonitor.path }}
{{- end }}
{{- end }}

{{/*
Get the appropriate persistent volume claim configuration
*/}}
{{- define "rag-system.persistentVolumeClaim" -}}
{{- if .Values.persistence.enabled }}
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
spec:
  accessModes:
  - {{ .Values.persistence.accessMode | default "ReadWriteOnce" }}
  storageClassName: {{ .Values.persistence.storageClass }}
  resources:
    requests:
      storage: {{ .Values.persistence.size }}
{{- end }}
{{- end }}

{{/*
Get the appropriate configuration map configuration
*/}}
{{- define "rag-system.configMap" -}}
{{- if .Values.configMap.enabled }}
kind: ConfigMap
apiVersion: v1
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
data:
  {{- range $key, $value := .Values.configMap.data }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
Get the appropriate secret configuration
*/}}
{{- define "rag-system.secret" -}}
{{- if .Values.secret.enabled }}
kind: Secret
apiVersion: v1
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
type: Opaque
data:
  {{- range $key, $value := .Values.secret.data }}
  {{ $key }}: {{ $value | b64encode }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
Get the appropriate network policy configuration
*/}}
{{- define "rag-system.networkPolicy" -}}
{{- if .Values.networkPolicy.enabled }}
kind: NetworkPolicy
apiVersion: networking.k8s.io/v1
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      {{- include "rag-system.selectorLabels" . | nindent 6 }}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: {{ include "rag-system.namespace" . }}
    ports:
    - protocol: TCP
      port: {{ include "rag-system.servicePort" . }}
{{- end }}
{{- end }}

{{/*
Get the appropriate priority class configuration
*/}}
{{- define "rag-system.priorityClass" -}}
{{- if .Values.priorityClass.enabled }}
kind: PriorityClass
apiVersion: scheduling.k8s.io/v1
metadata:
  name: {{ .Values.priorityClass.name }}
value: {{ .Values.priorityClass.value }}
description: "{{ .Values.priorityClass.description }}"
globalDefault: {{ .Values.priorityClass.globalDefault | default false }}
preemptionPolicy: {{ .Values.priorityClass.preemptionPolicy | default "PreemptLowerPriority" }}
{{- end }}
{{- end }}

{{/*
Get the appropriate resource quota configuration
*/}}
{{- define "rag-system.resourceQuota" -}}
{{- if .Values.resourceQuota.enabled }}
kind: ResourceQuota
apiVersion: v1
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
spec:
  hard:
    cpu: {{ .Values.resourceQuota.cpu }}
    memory: {{ .Values.resourceQuota.memory }}
    pods: {{ .Values.resourceQuota.pods }}
    requests.cpu: {{ .Values.resourceQuota.requests.cpu }}
    requests.memory: {{ .Values.resourceQuota.requests.memory }}
    limits.cpu: {{ .Values.resourceQuota.limits.cpu }}
    limits.memory: {{ .Values.resourceQuota.limits.memory }}
{{- end }}
{{- end }}

{{/*
Get the appropriate limit range configuration
*/}}
{{- define "rag-system.limitRange" -}}
{{- if .Values.limitRange.enabled }}
kind: LimitRange
apiVersion: v1
metadata:
  name: {{ include "rag-system.fullname" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
spec:
  limits:
  - type: Container
    default:
      cpu: {{ .Values.limitRange.default.cpu }}
      memory: {{ .Values.limitRange.default.memory }}
    defaultRequest:
      cpu: {{ .Values.limitRange.defaultRequest.cpu }}
      memory: {{ .Values.limitRange.defaultRequest.memory }}
    min:
      cpu: {{ .Values.limitRange.min.cpu }}
      memory: {{ .Values.limitRange.min.memory }}
    max:
      cpu: {{ .Values.limitRange.max.cpu }}
      memory: {{ .Values.limitRange.max.memory }}
{{- end }}
{{- end }}

{{/*
Get the appropriate service configuration
*/}}
{{- define "rag-system.service" -}}
kind: Service
apiVersion: v1
metadata:
  name: {{ include "rag-system.serviceName" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
  {{- if .Values.service.annotations }}
  annotations:
    {{- toYaml .Values.service.annotations | nindent 4 }}
  {{- end }}
spec:
  type: {{ include "rag-system.serviceType" . }}
  ports:
  - port: {{ include "rag-system.servicePort" . }}
    targetPort: {{ include "rag-system.serviceTargetPort" . }}
    name: http
    protocol: TCP
  selector:
    {{- include "rag-system.selectorLabels" . | nindent 4 }}
{{- end }}

{{/*
Get the appropriate deployment configuration
*/}}
{{- define "rag-system.deployment" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "rag-system.deploymentName" . }}
  namespace: {{ include "rag-system.namespace" . }}
  labels:
    {{- include "rag-system.labels" . | nindent 4 }}
  {{- if .Values.deployment.annotations }}
  annotations:
    {{- toYaml .Values.deployment.annotations | nindent 4 }}
  {{- end }}
spec:
  replicas: {{ include "rag-system.replicaCount" . }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: {{ .Values.deployment.strategy.rollingUpdate.maxUnavailable | default "1" }}
      maxSurge: {{ .Values.deployment.strategy.rollingUpdate.maxSurge | default "1" }}
  selector:
    matchLabels:
      {{- include "rag-system.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "rag-system.selectorLabels" . | nindent 8 }}
      {{- if .Values.template.annotations }}
      annotations:
        {{- toYaml .Values.template.annotations | nindent 8 }}
      {{- end }}
    spec:
      {{- if .Values.template.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml .Values.template.imagePullSecrets | nindent 8 }}
      {{- end }}
      {{- if .Values.template.serviceAccountName }}
      serviceAccountName: {{ .Values.template.serviceAccountName }}
      {{- end }}
      {{- include "rag-system.securityContext" . | nindent 6 }}
      {{- include "rag-system.nodeAffinity" . | nindent 6 }}
      {{- include "rag-system.tolerations" . | nindent 6 }}
      containers:
      - name: {{ .Values.container.name | default "main" }}
        image: {{ include "rag-system.imageRegistry" . }}/{{ .Values.container.repository | default .Values.image.repository }}:{{ include "rag-system.imageTag" . }}
        imagePullPolicy: {{ include "rag-system.imagePullPolicy" . }}
        {{- include "rag-system.containerSecurityContext" . | nindent 8 }}
        ports:
        - containerPort: {{ .Values.container.port | default .Values.service.targetPort }}
          name: http
        {{- if .Values.container.additionalPorts }}
        {{- toYaml .Values.container.additionalPorts | nindent 8 }}
        {{- end }}
        {{- include "rag-system.env" . | nindent 8 }}
        {{- include "rag-system.livenessProbe" . | nindent 8 }}
        {{- include "rag-system.readinessProbe" . | nindent 8 }}
        {{- include "rag-system.resources" . | nindent 8 }}
        {{- include "rag-system.volumeMounts" . | nindent 8 }}
      {{- if .Values.template.initContainers }}
      initContainers:
        {{- toYaml .Values.template.initContainers | nindent 8 }}
      {{- end }}
      {{- include "rag-system.volumes" . | nindent 6 }}
{{- end }}