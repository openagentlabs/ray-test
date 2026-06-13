{{- define "routing-tier.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "routing-tier.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "routing-tier.labels" -}}
helm.sh/chart: {{ include "routing-tier.chart" . }}
{{ include "routing-tier.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "routing-tier.chart" -}}
{{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}

{{- define "routing-tier.selectorLabels" -}}
app.kubernetes.io/name: {{ include "routing-tier.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: envoy-router
{{- end }}

{{- define "routing-tier.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default "pod-manager" .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "routing-tier.albListenPorts" -}}
{{- $ports := list -}}
{{- if .Values.ingress.listeners.http.enabled -}}
{{- $ports = append $ports (dict "HTTP" (.Values.ingress.listeners.http.port | int)) -}}
{{- end -}}
{{- if .Values.ingress.listeners.https.enabled -}}
{{- if not .Values.ingress.listeners.https.certificateArn -}}
{{- fail "ingress.listeners.https.enabled requires ingress.listeners.https.certificateArn" -}}
{{- end -}}
{{- $ports = append $ports (dict "HTTPS" (.Values.ingress.listeners.https.port | int)) -}}
{{- end -}}
{{- if eq (len $ports) 0 -}}
{{- fail "At least one ingress listener (http or https) must be enabled" -}}
{{- end -}}
{{- $ports | toJson -}}
{{- end }}

{{- define "routing-tier.albAnnotations" -}}
{{- $ann := dict -}}
{{- $_ := set $ann "alb.ingress.kubernetes.io/scheme" .Values.ingress.scheme -}}
{{- $_ := set $ann "alb.ingress.kubernetes.io/target-type" "ip" -}}
{{- $_ := set $ann "alb.ingress.kubernetes.io/listen-ports" (include "routing-tier.albListenPorts" .) -}}
{{- $_ := set $ann "alb.ingress.kubernetes.io/healthcheck-port" (.Values.service.healthPort | toString) -}}
{{- $_ := set $ann "alb.ingress.kubernetes.io/healthcheck-path" "/health" -}}
{{- if .Values.ingress.listeners.https.enabled -}}
{{- $_ := set $ann "alb.ingress.kubernetes.io/certificate-arn" .Values.ingress.listeners.https.certificateArn -}}
{{- end -}}
{{- if and .Values.ingress.listeners.http.enabled .Values.ingress.listeners.https.enabled .Values.ingress.listeners.https.sslRedirect -}}
{{- $_ := set $ann "alb.ingress.kubernetes.io/ssl-redirect" (.Values.ingress.listeners.https.port | toString) -}}
{{- end -}}
{{- range $key, $value := .Values.ingress.annotations -}}
{{- $_ := set $ann $key $value -}}
{{- end -}}
{{- $ann | toYaml -}}
{{- end }}
