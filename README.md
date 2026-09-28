# Triagem de mensagens com n8n + LLM

Em construção. Fluxo em n8n que classifica mensagens de clientes de uma clínica fictícia com um LLM, grava no PostgreSQL e manda para um humano o que não tiver certeza.

## Rodar (etapa 1: infraestrutura)

Requer Docker com Docker Compose.

```bash
python scripts/gerar_env.py   # cria o .env com senhas aleatórias
docker compose up -d
docker compose ps             # os dois serviços devem aparecer como running (postgres: healthy)
```

Abra http://localhost:5678 e crie a conta de dono do n8n (fica só na sua máquina).

Conferir o banco da clínica:

```bash
docker compose exec postgres psql -U admin -d clinica -c "\dt"
```
