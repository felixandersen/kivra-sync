{{- define "kivra-sync.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "kivra-sync.fullname" -}}
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

{{- define "kivra-sync.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "kivra-sync.labels" -}}
helm.sh/chart: {{ include "kivra-sync.chart" . }}
{{ include "kivra-sync.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "kivra-sync.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kivra-sync.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "kivra-sync.secretName" -}}
{{- default (include "kivra-sync.fullname" .) .Values.existingSecret }}
{{- end }}

{{/* An unquoted ssn in a values file is parsed as a float */}}
{{- define "kivra-sync.ssn" -}}
{{- if kindIs "float64" .Values.ssn }}
{{- printf "%.0f" .Values.ssn }}
{{- else }}
{{- .Values.ssn | toString }}
{{- end }}
{{- end }}

{{- define "kivra-sync.isWeb" -}}
{{- if eq .Values.interaction.provider "web" }}true{{ end }}
{{- end }}

{{- define "kivra-sync.usesFilesystem" -}}
{{- if eq .Values.storage.provider "filesystem" }}true{{ end }}
{{- end }}

{{- define "kivra-sync.usesNtfyPassword" -}}
{{- if and (eq .Values.interaction.provider "ntfy") .Values.interaction.ntfy.user }}true{{ end }}
{{- end }}

{{- define "kivra-sync.validate" -}}
{{- if not (has .Values.interaction.provider (list "web" "ntfy")) }}
{{- fail "interaction.provider must be one of: web, ntfy" }}
{{- end }}
{{- if not (has .Values.storage.provider (list "filesystem" "paperless")) }}
{{- fail "storage.provider must be one of: filesystem, paperless" }}
{{- end }}
{{- if not .Values.existingSecret }}
{{- if not .Values.ssn }}
{{- fail "ssn (or existingSecret) is required" }}
{{- end }}
{{- if and (eq .Values.storage.provider "paperless") (not .Values.storage.paperless.token) }}
{{- fail "storage.paperless.token (or existingSecret) is required with the paperless storage provider" }}
{{- end }}
{{- end }}
{{- if and (eq .Values.storage.provider "paperless") (not .Values.storage.paperless.url) }}
{{- fail "storage.paperless.url is required with the paperless storage provider" }}
{{- end }}
{{- if and (eq .Values.interaction.provider "ntfy") (not .Values.interaction.ntfy.topic) }}
{{- fail "interaction.ntfy.topic is required with the ntfy interaction provider" }}
{{- end }}
{{- end }}
