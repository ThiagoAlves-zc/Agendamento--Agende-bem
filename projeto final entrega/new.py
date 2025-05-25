from datetime import datetime
import mysql.connector

# Conexão com banco
try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="25140377",
        database="apresentacao"
    )
    cursor = conn.cursor()
    print("✅ Conexão com banco de dados OK!")
except Exception as e:
    print(f"❌ Erro ao conectar ao banco de dados: {e}")
    exit()

usuario_logado = {}
medico_logado = {}

# ---------------- LOGIN / CADASTRO ----------------

def login():
    global usuario_logado
    while True:
        print("Login")
        email = input("Digite seu email (ou 0 para voltar): ")
        if email == "0":
            return False
        senha = input("Digite sua senha: ")
        sql = "SELECT id_usuario, nome_usuario, email_usuario, data_nascimento FROM tbl_usuario WHERE email_usuario = %s AND senha_usuario = %s"
        cursor.execute(sql, (email, senha))
        resultado = cursor.fetchone()
        if resultado:
            usuario_logado = {
                "id": resultado[0],
                "nome": resultado[1],
                "email": resultado[2],
                "data_nasc": resultado[3]
            }
            print(f"✅ Bem-vindo, {usuario_logado['nome']}!")
            return True
        else:
            print("❌ Email ou senha incorretos. Tente novamente.")

def cadastro():
    try:
        nome = input("Digite seu nome: ")
        email = input("Digite seu email: ")
        senha = input("Digite uma senha: ")
        cpf = input("Digite seu CPF (Somente números): ")
        data_nasc_str = input("Digite sua data de nascimento (DD/MM/AAAA): ")
        data_nasc = datetime.strptime(data_nasc_str, "%d/%m/%Y")
        sql = "INSERT INTO tbl_usuario (nome_usuario,email_usuario, senha_usuario, data_nascimento,cpf_usuario) VALUES (%s, %s, %s, %s,%s)"
        cursor.execute(sql, (nome, email, senha, data_nasc, cpf))
        conn.commit()
        print("✅ Cadastro realizado com sucesso!")
    except ValueError:
        print("⚠️ Data em formato inválido! Use DD/MM/AAAA.")
    except Exception as e:
        print(f"❌ Erro ao cadastrar usuário: {e}")

def cadastro_medico():
    try:
        nome = input("Digite seu nome: ")
        cargo = input("Digite seu cargo: ")
        crm = input("Digite seu CRM: ")
        email = input("Digite seu email: ")
        senha = input("Digite sua senha: ")

        sql = "INSERT INTO tbl_medico (nome_medico, cargo_medico, crm_medico, email_medico, senha_medico) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (nome, cargo, crm, email, senha))
        conn.commit()
        print("✅ Cadastro de médico realizado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao cadastrar médico: {e}")

def login_medico():
    global medico_logado
    email = input("Digite seu email: ")
    senha = input("Digite sua senha: ")

    sql = "SELECT id_medico, nome_medico FROM tbl_medico WHERE email_medico = %s AND senha_medico = %s"
    cursor.execute(sql, (email, senha))
    resultado = cursor.fetchone()
    if resultado:
        medico_logado = {
            "id": resultado[0],
            "nome": resultado[1]
        }
        print(f"✅ Bem-vindo, Dr(a). {medico_logado['nome']}!")
        return True
    else:
        print("❌ Email ou senha inválidos.")
        return False

# ---------------- PACIENTE ----------------

def agendar():
    try:
        data_str = input("Digite a data do agendamento (DD/MM/AAAA): ")
        hora = input("Digite o horário do agendamento (HH:MM): ")
        descricao = input("Digite uma breve descrição do que você tem: ")

        data_agendamento = datetime.strptime(data_str, "%d/%m/%Y")
        hora_obj = datetime.strptime(hora, "%H:%M").time()

        sql = "INSERT INTO tbl_agendamento1 (id_usuario, data_hora, horas_agen, descricao_agen) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (usuario_logado['id'], data_agendamento, hora_obj, descricao))
        conn.commit()
        print("✅ Agendamento realizado com sucesso!")
    except ValueError:
        print("⚠️ Data ou hora em formato inválido!")
    except Exception as e:
        print(f"❌ Erro ao agendar: {e}")

def cancelar():
    try:
        id_agendamento = int(input("Digite o ID do agendamento que deseja excluir: "))
        sql_dependente = "DELETE FROM tbl_agendamento_medico WHERE id_agendamento = %s"
        cursor.execute(sql_dependente, (id_agendamento,))
        conn.commit()
        sql = "DELETE FROM tbl_agendamento1 WHERE id_agen = %s"
        cursor.execute(sql, (id_agendamento,))
        conn.commit()
        print("✅ Agendamento excluído com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao cancelar agendamento: {e}")

def mudar():
    try:
        id_agendamento = input("Digite o ID do agendamento que deseja mudar: ")
        data_input = input("Digite a nova data do agendamento (DD/MM/AAAA): ")
        hora_input = input("Digite a nova hora do agendamento (HH:MM): ")
        data_agendamento = datetime.strptime(data_input, "%d/%m/%Y").date()
        hora_obj = datetime.strptime(hora_input, "%H:%M").time()
        sql = "UPDATE tbl_agendamento1 SET data_hora = %s, horas_agen = %s WHERE id_agen = %s"
        values = (data_agendamento, hora_obj, id_agendamento)
        cursor.execute(sql, values)
        conn.commit()
        print("✅ Agendamento atualizado com sucesso!")
    except ValueError:
        print("⚠️ Data ou hora em formato inválido!")
    except Exception as e:
        print(f"❌ Erro ao atualizar agendamento: {e}")


def lista():
    try:
        sql = """
            SELECT a.id_agen, u.nome_usuario, u.cpf_usuario, u.data_nascimento, 
                   a.data_hora, a.horas_agen, a.descricao_agen
            FROM tbl_agendamento1 a
            JOIN tbl_usuario u ON a.id_usuario = u.id_usuario
            WHERE a.id_usuario = %s
        """
        cursor.execute(sql, (usuario_logado['id'],))
        resultados = cursor.fetchall()

        if not resultados:
            print("⚠️ Nenhum agendamento encontrado.")
            return

        for linha in resultados:
            print(f"""
📝 ID: {linha[0]}
👤 Nome: {linha[1]}
🆔 CPF: {linha[2]}
🎂 Nascimento: {linha[3].strftime('%d/%m/%Y')}
📅 Data: {linha[4].strftime('%d/%m/%Y')}
🕒 Hora: {linha[5]}
📄 Descrição: {linha[6]}
----------------------------------
            """)
    except Exception as e:
        print(f"❌ Erro ao listar agendamentos: {e}")

# ---------------- MÉDICO ----------------

def listar_agendamentos_disponiveis():
    try:
        sql = """
            SELECT a.id_agen, u.nome_usuario, a.data_hora, a.horas_agen, a.descricao_agen
            FROM tbl_agendamento1 a
            JOIN tbl_usuario u ON a.id_usuario = u.id_usuario
            WHERE NOT EXISTS (
                SELECT 1 FROM tbl_agendamento_medico am WHERE am.id_agendamento = a.id_agen
            )
        """
        cursor.execute(sql)
        resultados = cursor.fetchall()
        if not resultados:
            print("⚠️ Nenhum agendamento disponível.")
            return

        for r in resultados:
            print(f"ID: {r[0]} | Paciente: {r[1]} | Data: {r[2].strftime('%d/%m/%Y')} | Hora: {r[3]} | Desc: {r[4]}")

        agendamento_id = int(input("Digite o ID do agendamento que deseja pegar (ou 0 para cancelar): "))
        if agendamento_id == 0:
            return

        sql = "INSERT INTO tbl_agendamento_medico (id_agendamento, id_medico) VALUES (%s, %s)"
        cursor.execute(sql, (agendamento_id, medico_logado['id']))
        conn.commit()
        print("✅ Agendamento atribuído com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao atribuir agendamento: {e}")

def listar_agendamentos_do_medico():
    try:
        sql = """
            SELECT a.id_agen, u.nome_usuario, a.data_hora, a.horas_agen, a.descricao_agen
            FROM tbl_agendamento1 a
            JOIN tbl_agendamento_medico am ON a.id_agen = am.id_agendamento
            JOIN tbl_usuario u ON a.id_usuario = u.id_usuario
            WHERE am.id_medico = %s
        """
        cursor.execute(sql, (medico_logado['id'],))
        resultados = cursor.fetchall()

        if not resultados:
            print("⚠️ Nenhum agendamento atribuído a você.")
            return

        for r in resultados:
            print(f"ID: {r[0]} | Paciente: {r[1]} | Data: {r[2].strftime('%d/%m/%Y')} | Hora: {r[3]} | Desc: {r[4]}")
    except Exception as e:
        print(f"❌ Erro ao listar agendamentos: {e}")

# ---------------- MENUS ----------------

def menu_usuario():
    while True:
        print("\n---- Menu do Usuário ----")
        print("1 - Agendar")
        print("2 - Listar Agendamentos")
        print("3 - Alterar Agendamento")
        print("4 - Cancelar Agendamento")
        print("0 - Voltar")
        opcao = input("Escolha uma opção: ")
        if opcao == "1":
            agendar()
        elif opcao == "2":
            lista()
        elif opcao == "3":
            mudar()
        elif opcao == "4":
            cancelar()
        elif opcao == "0":
            break
        else:
            print("⚠️ Opção inválida!")

def menu_med():
    while True:
        print("\n---- Menu do Médico ----")
        print("1 - Ver agendamentos disponíveis")
        print("2 - Ver meus agendamentos")
        print("0 - Sair")
        opcao = input("Escolha uma opção: ")
        if opcao == "1":
            listar_agendamentos_disponiveis()
        elif opcao == "2":
            listar_agendamentos_do_medico()
        elif opcao == "0":
            break
        else:
            print("⚠️ Opção inválida!")

def fluxo_medico():
    while True:
        print("\n---- Acesso Médico ----")
        print("1 - Login")
        print("2 - Cadastrar novo médico")
        print("0 - Voltar")
        escolha = input("Escolha: ")

        if escolha == "1":
            if login_medico():
                menu_med()
        elif escolha == "2":
            cadastro_medico()
        elif escolha == "0":
            break
        else:
            print("⚠️ Opção inválida!")

def fluxo_paciente():
    while True:
        print("\n---- Acesso Paciente ----")
        print("1 - Login")
        print("2 - Cadastrar novo paciente")
        print("0 - Voltar")
        escolha = input("Escolha: ")

        if escolha == "1":
            if login():
                menu_usuario()
        elif escolha == "2":
            cadastro()
            if login():
                menu_usuario()
        elif escolha == "0":
            break
        else:
            print("⚠️ Opção inválida!")

def usuario():
    while True:
        print("\nVocê é médico ou paciente?")
        print("1 - Médico")
        print("2 - Paciente")
        print("0 - Sair")
        escolha = input("Escolha: ")

        if escolha == "1":
            fluxo_medico()
        elif escolha == "2":
            fluxo_paciente()
        elif escolha == "0":
            print("👋 Encerrando o programa.")
            break
        else:
            print("⚠️ Opção inválida!")

# Início
usuario()
cursor.close()
conn.close()