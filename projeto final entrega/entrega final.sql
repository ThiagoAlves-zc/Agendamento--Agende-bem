/*CREATE DATABASE apresentacao;

USE apresentacao; 



CREATE TABLE tbl_usuario (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    nome_usuario VARCHAR(100),
    cpf_usuario VARCHAR(11) UNIQUE,
    email_usuario VARCHAR(100) UNIQUE,
    senha_usuario VARCHAR(100),
    data_nascimento DATE
);

CREATE TABLE tbl_agendamento1 (
    id_agen INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT,
    data_hora DATE,
    horas_agen TIME,
    descricao_agen TEXT,
    FOREIGN KEY (id_usuario) REFERENCES tbl_usuario(id_usuario)
);
CREATE TABLE tbl_medico(
    id_medico INT AUTO_INCREMENT PRIMARY KEY NOT NULL,
    nome_medico VARCHAR(250),
    cargo_medico VARCHAR(250),
    crm_medico VARCHAR(20),
    email_medico VARCHAR(100) UNIQUE,
    senha_medico VARCHAR(100));
    
CREATE TABLE tbl_agendamento_medico (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_medico INT,
    id_agendamento INT,
    FOREIGN KEY (id_medico) REFERENCES tbl_medico(id_medico),
    FOREIGN KEY (id_agendamento) REFERENCES tbl_agendamento1(id_agen)
);*/
use apresentacao;
SELECT * FROM tbl_medico;
SELECT * FROM tbl_agendamento1;
SELECT * FROM tbl_usuario;
SELECT * FROM tbl_agendamento_medico;
describe tbl_agendamento1;
