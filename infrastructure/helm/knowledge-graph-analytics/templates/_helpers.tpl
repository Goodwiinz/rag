{{/*
Expand the name of the chart.
*/}}
{{- define "knowledge-graph-analytics.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "knowledge-graph-analytics.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
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
{{- define "knowledge-graph-analytics.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "knowledge-graph-analytics.labels" -}}
helm.sh/chart: {{ include "knowledge-graph-analytics.chart" . }}
{{ include "knowledge-graph-analytics.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Values.commonLabels }}
{{ toYaml .Values.commonLabels }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "knowledge-graph-analytics.selectorLabels" -}}
app.kubernetes.io/name: {{ include "knowledge-graph-analytics.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "knowledge-graph-analytics.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "knowledge-graph-analytics.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the image name
*/}}
{{- define "knowledge-graph-analytics.image" -}}
{{- $registry := .Values.global.imageRegistry -}}
{{- if .Values.image.repository -}}
{{- $registry = .Values.image.repository -}}
{{- end -}}
{{- if .Values.global.imageRegistry -}}
{{- $registry = .Values.global.imageRegistry -}}
{{- end -}}
{{- $tag := .Chart.AppVersion -}}
{{- if .Values.image.tag -}}
{{- $tag = .Values.image.tag -}}
{{- end -}}
{{- printf "%s/%s:%s" $registry (default .Chart.Name .Values.nameOverride) $tag -}}
{{- end }}

{{/*
Create the database URL
*/}}
{{- define "knowledge-graph-analytics.databaseUrl" -}}
{{- $postgres := .Values.postgresql -}}
{{- if $postgres.enabled -}}
{{- printf "postgresql://%s:%s@%s:%d/%s" $postgres.auth.username $postgres.auth.password $postgres.fullname $postgres.primary.service.port $postgres.auth.database -}}
{{- else -}}
{{- printf "%s" .Values.backend.env.DATABASE_URL -}}
{{- end -}}
{{- end }}

{{/*
Create the Redis URL
*/}}
{{- define "knowledge-graph-analytics.redisUrl" -}}
{{- $redis := .Values.redis -}}
{{- if $redis.enabled -}}
{{- $password := "" -}}
{{- if $redis.auth.enabled -}}
{{- $password = printf ":%s@" $redis.auth.password -}}
{{- end -}}
{{- printf "redis://%s%s:%d/0" $password $redis.fullname $redis.master.service.port -}}
{{- else -}}
{{- printf "%s" .Values.backend.env.REDIS_URL -}}
{{- end -}}
{{- end }}

{{/*
Create the Neo4j URI
*/}}
{{- define "knowledge-graph-analytics.neo4jUri" -}}
{{- $neo4j := .Values.neo4j -}}
{{- if $neo4j.enabled -}}
{{- printf "bolt://%s:7687" $neo4j.fullname -}}
{{- else -}}
{{- printf "%s" .Values.backend.env.NEO4J_URI -}}
{{- end -}}
{{- end }}

{{/*
Create the Qdrant URL
*/}}
{{- define "knowledge-graph-analytics.qdrantUrl" -}}
{{- $qdrant := .Values.qdrant -}}
{{- if $qdrant.enabled -}}
{{- printf "http://%s:6333" $qdrant.fullname -}}
{{- else -}}
{{- printf "%s" .Values.backend.env.QDRANT_URL -}}
{{- end -}}
{{- end }}

{{/*
Return the storage class name
*/}}
{{- define "knowledge-graph-analytics.storageClass" -}}
{{- if .Values.global.storageClass -}}
{{- .Values.global.storageClass -}}
{{- else -}}
{{- "gp2" -}}
{{- end -}}
{{- end }}

{{/*
Return the DNS zone
*/}}
{{- define "knowledge-graph-analytics.dnsZone" -}}
{{- if .Values.global.dnsZone -}}
{{- .Values.global.dnsZone -}}
{{- else -}}
{{- "yourdomain.com" -}}
{{- end -}}
{{- end }}

{{/*
Create the frontend host
*/}}
{{- define "knowledge-graph-analytics.frontendHost" -}}
{{- printf "analytics.%s" (include "knowledge-graph-analytics.dnsZone" .) -}}
{{- end }}

{{/*
Create the backend host
*/}}
{{- define "knowledge-graph-analytics.backendHost" -}}
{{- printf "api.%s" (include "knowledge-graph-analytics.dnsZone" .) -}}
{{- end }}

{{/*
Return the environment name
*/}}
{{- define "knowledge-graph-analytics.environment" -}}
{{- if .Values.global.environment -}}
{{- .Values.global.environment -}}
{{- else -}}
{{- "production" -}}
{{- end -}}
{{- end }}

{{/*
Return the resource limits for a given component
*/}}
{{- define "knowledge-graph-analytics.resources" -}}
{{- $component := index .Values .component -}}
{{- if $component.resources -}}
resources:
  {{- toYaml $component.resources | nindent 2 }}
{{- end -}}
{{- end }}

{{/*
Return the security context for a given component
*/}}
{{- define "knowledge-graph-analytics.securityContext" -}}
{{- $component := index .Values .component -}}
{{- if $component.securityContext -}}
securityContext:
  {{- toYaml $component.securityContext | nindent 2 }}
{{- end -}}
{{- end }}

{{/*
Return the affinity rules for a given component
*/}}
{{- define "knowledge-graph-analytics.affinity" -}}
{{- $component := index .Values .component -}}
{{- if $component.affinity -}}
affinity:
  {{- toYaml $component.affinity | nindent 2 }}
{{- else if .Values.affinity -}}
affinity:
  {{- toYaml .Values.affinity | nindent 2 }}
{{- end -}}
{{- end }}

{{/*
Return the tolerations for a given component
*/}}
{{- define "knowledge-graph-analytics.tolerations" -}}
{{- $component := index .Values .component -}}
{{- if $component.tolerations -}}
tolerations:
  {{- toYaml $component.tolerations | nindent 2 }}
{{- else if .Values.tolerations -}}
tolerations:
  {{- toYaml .Values.tolerations | nindent 2 }}
{{- end -}}
{{- end }}

{{/*
Return the node selector for a given component
*/}}
{{- define "knowledge-graph-analytics.nodeSelector" -}}
{{- $component := index .Values .component -}}
{{- if $component.nodeSelector -}}
nodeSelector:
  {{- toYaml $component.nodeSelector | nindent 2 }}
{{- else if .Values.nodeSelector -}}
nodeSelector:
  {{- toYaml .Values.nodeSelector | nindent 2 }}
{{- end -}}
{{- end }}

{{/*
Return the pod annotations for a given component
*/}}
{{- define "knowledge-graph-analytics.podAnnotations" -}}
{{- $component := index .Values .component -}}
{{- if $component.podAnnotations -}}
{{- toYaml $component.podAnnotations -}}
{{- else if .Values.podAnnotations -}}
{{- toYaml .Values.podAnnotations -}}
{{- end -}}
{{- end }}

{{/*
Create a default pod security policy
*/}}
{{- define "knowledge-graph-analytics.podSecurityPolicy" -}}
{{- if .Values.podSecurityPolicy.enabled }}
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: {{ include "knowledge-graph-analytics.fullname" . }}
  labels:
    {{- include "knowledge-graph-analytics.labels" . | nindent 4 }}
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
{{- end }}
{{- end }}

{{/*
Create a default network policy
*/}}
{{- define "knowledge-graph-analytics.networkPolicy" -}}
{{- if .Values.networkPolicy.enabled }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "knowledge-graph-analytics.fullname" . }}
  labels:
    {{- include "knowledge-graph-analytics.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      {{- include "knowledge-graph-analytics.selectorLabels" . | nindent 6 }}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
        - podSelector:
            matchLabels:
              {{- include "knowledge-graph-analytics.selectorLabels" . | nindent 14 }}
      ports:
        - protocol: TCP
          port: {{ .Values.frontend.service.port }}
        - protocol: TCP
          port: {{ .Values.backend.service.port }}
  egress:
    - to: []
      ports:
        - protocol: TCP
          port: 53
        - protocol: UDP
          port: 53
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: postgresql
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: redis
      ports:
        - protocol: TCP
          port: 6379
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: neo4j
      ports:
        - protocol: TCP
          port: 7687
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: qdrant
      ports:
        - protocol: TCP
          port: 6333
{{- end }}
{{- end }}