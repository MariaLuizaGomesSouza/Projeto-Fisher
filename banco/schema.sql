-- 1. Criação da Base de Dados
CREATE DATABASE IF NOT EXISTS fisher;
USE fisher;

-- 2. DDL - Tabelas da Aplicação
CREATE TABLE IF NOT EXISTS user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha VARCHAR(200) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS tanque (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    especie VARCHAR(100) NOT NULL,
    quantidade INT NOT NULL,
    user_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS biometria (
    id INT AUTO_INCREMENT PRIMARY KEY,
    peso_medio_gramas FLOAT NOT NULL,
    temperatura_agua FLOAT NOT NULL,
    data DATETIME DEFAULT CURRENT_TIMESTAMP,
    tanque_id INT NOT NULL,
    FOREIGN KEY (tanque_id) REFERENCES tanque(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS estoque_racao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quantidade_kg FLOAT NOT NULL DEFAULT 0,
    user_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS registro_trato (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quantidade_kg FLOAT NOT NULL,
    data DATETIME DEFAULT CURRENT_TIMESTAMP,
    tanque_id INT NOT NULL,
    user_id INT NOT NULL,
    FOREIGN KEY (tanque_id) REFERENCES tanque(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 3. Criação dos Utilizadores (Princípio do Menor Privilégio)
CREATE USER IF NOT EXISTS 'fisher_admin'@'localhost' IDENTIFIED BY 'SenhaAdminSegura123!';
GRANT ALL PRIVILEGES ON fisher.* TO 'fisher_admin'@'localhost';

CREATE USER IF NOT EXISTS 'fisher_app'@'localhost' IDENTIFIED BY 'SenhaAppSegura123!';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON fisher.* TO 'fisher_app'@'localhost';

FLUSH PRIVILEGES;

-- 4. Trigger para Desconto de Ração
DELIMITER $$
CREATE TRIGGER trg_trato_desconta_estoque
AFTER INSERT ON registro_trato
FOR EACH ROW
BEGIN
  UPDATE estoque_racao
     SET quantidade_kg = GREATEST(quantidade_kg - NEW.quantidade_kg, 0)
   WHERE user_id = NEW.user_id;
END$$
DELIMITER ;

-- 5. Stored Procedure para Cálculo da Biomassa
DELIMITER $$
CREATE PROCEDURE sp_biomassa_tanque(IN p_tanque INT)
BEGIN
  SELECT t.nome,
         (t.quantidade * b.peso_medio_gramas / 1000) AS biomassa_kg
    FROM tanque t
    JOIN biometria b ON b.tanque_id = t.id
   WHERE t.id = p_tanque
   ORDER BY b.data DESC
   LIMIT 1;
END$$
DELIMITER ;