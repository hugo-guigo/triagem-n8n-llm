-- Banco da clínica fictícia. Roda uma vez, na criação do volume, dentro do banco "clinica".
-- Só dados fictícios.

-- Toda mensagem que chega tem um id_mensagem. Ele é a chave de idempotência:
-- se o mesmo id chegar duas vezes (retry do cliente, clique duplo), as tabelas
-- abaixo recusam a segunda gravação em vez de duplicar o registro.

-- "CRM": pedidos de agendamento e cancelamento
CREATE TABLE solicitacoes (
    id           BIGSERIAL PRIMARY KEY,
    id_mensagem  TEXT NOT NULL UNIQUE,
    nome         TEXT NOT NULL,
    canal        TEXT NOT NULL,
    tipo         TEXT NOT NULL CHECK (tipo IN ('agendamento', 'cancelamento')),
    resumo       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pendente',
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Alertas para um humano: reclamações e urgência alta
CREATE TABLE alertas (
    id           BIGSERIAL PRIMARY KEY,
    id_mensagem  TEXT NOT NULL UNIQUE,
    motivo       TEXT NOT NULL CHECK (motivo IN ('reclamacao', 'urgencia_alta')),
    categoria    TEXT NOT NULL,
    urgencia     TEXT NOT NULL,
    resumo       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'aberto',
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fila de revisão humana (handoff): o fluxo não teve certeza, então não responde sozinho
CREATE TABLE fila_revisao (
    id            BIGSERIAL PRIMARY KEY,
    id_mensagem   TEXT NOT NULL UNIQUE,
    motivo        TEXT NOT NULL CHECK (motivo IN ('confianca_baixa', 'json_invalido', 'erro_llm')),
    texto         TEXT NOT NULL,
    saida_llm     JSONB,
    status        TEXT NOT NULL DEFAULT 'pendente',
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Log de cada execução do fluxo (observabilidade)
CREATE TABLE execucoes (
    id              BIGSERIAL PRIMARY KEY,
    id_execucao     TEXT,              -- id da execução no n8n, para achar na interface
    id_mensagem     TEXT,
    recebido_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    destino         TEXT NOT NULL CHECK (destino IN ('crm', 'alerta', 'revisao', 'resposta', 'invalido', 'duplicada', 'erro')),
    categoria       TEXT,
    urgencia        TEXT,
    confianca       NUMERIC(4, 3),
    handoff         BOOLEAN NOT NULL DEFAULT false,
    erro            TEXT,
    modelo          TEXT,
    tentativas_llm  SMALLINT,
    latencia_llm_ms INTEGER,
    latencia_ms     INTEGER,           -- do webhook até a resposta
    tokens_entrada  INTEGER,           -- NULL quando a API não informa
    tokens_saida    INTEGER
);
CREATE INDEX execucoes_recebido_em ON execucoes (recebido_em);

-- Falhas capturadas pelo workflow de erro (Error Trigger)
CREATE TABLE falhas (
    id           BIGSERIAL PRIMARY KEY,
    workflow     TEXT,
    id_execucao  TEXT,
    no           TEXT,                 -- nó do n8n onde a execução quebrou
    mensagem     TEXT,
    url          TEXT,                 -- link para a execução na interface do n8n
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- O usuário "app" (usado pelo n8n para gravar aqui) só lê e grava linhas
GRANT CONNECT ON DATABASE clinica TO app;
GRANT USAGE ON SCHEMA public TO app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app;
