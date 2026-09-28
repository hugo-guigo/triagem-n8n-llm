#!/bin/sh
# Cria dois usuários com o mínimo de permissão:
#   n8n -> dono do banco "n8n" (dados internos do n8n: workflows, execuções, credenciais)
#   app -> só lê e grava as tabelas da clínica; não cria nem apaga tabelas
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname clinica \
  -v n8n_pw="$N8N_DB_PASSWORD" -v app_pw="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE n8n LOGIN PASSWORD :'n8n_pw';
CREATE DATABASE n8n OWNER n8n;
CREATE ROLE app LOGIN PASSWORD :'app_pw';
SQL
