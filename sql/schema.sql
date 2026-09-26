-- Schema do banco de dados "Gestão de Desempenho da Equipe"
-- Rode este script uma vez, num banco novo, antes de usar o recurso
-- "Banco de Dados" do app (ou o script migrar_para_sql.py).
--
-- Modelo: uma "uma" (personagem base) pode ter várias "builds" (versões/
-- otimizações). Cada build acumula seus próprios resultados de área,
-- corridas e registros de ânimo.

CREATE TABLE umas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE builds (
    id SERIAL PRIMARY KEY,
    uma_id INTEGER NOT NULL REFERENCES umas(id),
    nome_build VARCHAR(150) NOT NULL,  -- nome completo da build (o "nome" mostrado no app)
    tag VARCHAR(50),                    -- rótulo curto da build, ex: 'V1', 'Ago/2026'
    ativo BOOLEAN DEFAULT TRUE
);

CREATE TABLE resultados_area (
    id SERIAL PRIMARY KEY,
    build_id INTEGER NOT NULL REFERENCES builds(id),
    area VARCHAR(50) NOT NULL,
    valor NUMERIC NOT NULL,
    animo VARCHAR(20)                   -- Muito Ruim, Ruim, Normal, Bom, Ótimo (ou NULL)
);

CREATE TABLE corridas (
    id SERIAL PRIMARY KEY,
    build_id INTEGER NOT NULL REFERENCES builds(id),
    corrida VARCHAR(100) NOT NULL,
    posicao INTEGER NOT NULL
);

CREATE TABLE animo_registros (
    id SERIAL PRIMARY KEY,
    build_id INTEGER NOT NULL REFERENCES builds(id),
    nivel VARCHAR(20) NOT NULL,
    observacao TEXT
);
