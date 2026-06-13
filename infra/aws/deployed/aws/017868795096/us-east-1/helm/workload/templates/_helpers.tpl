{{- define "arb-workload.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "arb-workload.fullname" -}}
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

{{- define "arb-workload.labels" -}}
helm.sh/chart: {{ include "arb-workload.name" . }}
app.kubernetes.io/name: {{ include "arb-workload.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "arb-workload.selectorLabels" -}}
app.kubernetes.io/name: {{ include "arb-workload.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "arb-workload.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "arb-workload.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "arb-workload.sharedMountPaths" -}}
{{- $paths := list -}}
{{- if .Values.lustre.enabled -}}
{{- $paths = append $paths .Values.lustre.mountPath -}}
{{- end -}}
{{- if .Values.s3SharedFiles.enabled -}}
{{- $paths = append $paths .Values.s3SharedFiles.mountPath -}}
{{- end -}}
{{- join "," $paths -}}
{{- end }}

{{- define "arb-workload.workloadWriteDirs" -}}
{{- $dirs := list -}}
{{- if .Values.lustre.enabled -}}
{{- $dirs = append $dirs .Values.sharedMounts.workloadWriteDirLustre -}}
{{- end -}}
{{- if .Values.s3SharedFiles.enabled -}}
{{- $dirs = append $dirs .Values.sharedMounts.workloadWriteDirS3 -}}
{{- end -}}
{{- join " " $dirs -}}
{{- end }}
