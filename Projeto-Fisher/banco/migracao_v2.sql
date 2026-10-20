-- =====================================================================
-- MIGRAÇÃO v2 - Fisher completo (painel, estoque com histórico, etc.)
-- Rode UMA vez, no banco que já existe, com o usuário administrador:
--     mysql -u fisher_admin -p fisher < banco/migracao_v2.sql
-- Nenhum dado é apagado.
-- (Se o usuário do .env tiver permissão de ALTER/CREATE, o próprio
--  sistema faz as colunas/tabela sozinho; o DROP TRIGGER é sempre manual.)
-- =====================================================================
USE fisher;

-- Novas colunas ------------------------------------------------------
ALTER TABLE tanque         ADD COLUMN volume_m3 FLOAT NULL;
ALTER TABLE tanque         ADD COLUMN observacoes TEXT NULL;
ALTER TABLE tanque         ADD COLUMN criado_em DATETIME DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE registro_trato ADD COLUMN descontado_kg FLOAT DEFAULT 0;
ALTER TABLE estoque_racao  ADD COLUMN capacidade_kg FLOAT DEFAULT 500;

UPDATE registro_trato SET descontado_kg = quantidade_kg WHERE descontado_kg IS NULL;
UPDATE estoque_racao  SET capacidade_kg = 500            WHERE capacidade_kg IS NULL;

-- Nova tabela de histórico ------------------------------------------
CREATE TABLE IF NOT EXISTS atividade (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    autor VARCHAR(100),
    tipo VARCHAR(30) NOT NULL,
    descricao VARCHAR(300) NOT NULL,
    tanque_id INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- O desconto de ração agora é feito pela aplicação. Sem remover o
-- trigger antigo, cada trato descontaria o estoque duas vezes.
DROP TRIGGER IF EXISTS trg_trato_desconta_estoque;
