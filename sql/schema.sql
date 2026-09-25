-- Schema do banco de dados "Gestão de Desempenho da Equipe"
-- Rode este script uma vez, num banco novo, antes de usar o recurso
-- "Banco de Dados" do app (ou o script migrar_para_sql.py).

CREATE TABLE pessoas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    nome_base VARCHAR(100) NOT NULL,   -- agrupa builds diferentes da mesma Uma
    tag VARCHAR(50),                    -- ex: 'V2', 'Ago/2026'
    ativo BOOLEAN DEFAULT TRUE
);

CREATE TABLE resultados_area (
    id SERIAL PRIMARY KEY,
    pessoa_id INTEGER NOT NULL REFERENCES pessoas(id),
    area VARCHAR(50) NOT NULL,
    valor NUMERIC NOT NULL,
    animo VARCHAR(20)                   -- Muito Ruim, Ruim, Normal, Bom, Ótimo (ou NULL)
);

CREATE TABLE corridas (
    id SERIAL PRIMARY KEY,
    pessoa_id INTEGER NOT NULL REFERENCES pessoas(id),
    corrida VARCHAR(100) NOT NULL,
    posicao INTEGER NOT NULL
);

CREATE TABLE animo_registros (
    id SERIAL PRIMARY KEY,
    pessoa_id INTEGER NOT NULL REFERENCES pessoas(id),
    nivel VARCHAR(20) NOT NULL,
    observacao TEXT
);
