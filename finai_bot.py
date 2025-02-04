from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import sqlite3
import random
import os  # Adicionado para usar a variável de ambiente PORT

app = Flask(__name__)

# Conectar ao banco de dados (ou criar se não existir)
def conectar_banco():
    conn = sqlite3.connect('finai_bot.db')
    return conn

# Criar as tabelas necessárias
def criar_tabelas():
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Tabela de gastos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            valor REAL NOT NULL,
            descricao TEXT,
            data_hora TEXT NOT NULL
        )
    ''')
    
    # Tabela de limites
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS limites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            tipo TEXT NOT NULL,  # Diário, Semanal, Mensal
            valor REAL NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# Chamar a função para criar as tabelas ao iniciar o Bot
criar_tabelas()

# Função para adicionar gastos ao banco de dados
def adicionar_gasto(usuario, valor, descricao):
    conn = conectar_banco()
    cursor = conn.cursor()
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
    cursor.execute('''
        INSERT INTO gastos (usuario, valor, descricao, data_hora)
        VALUES (?, ?, ?, ?)
    ''', (usuario, valor, descricao, data_hora))
    conn.commit()
    conn.close()

# Função para obter gastos do banco de dados
def obter_gastos(usuario):
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT valor, descricao, data_hora FROM gastos
        WHERE usuario = ?
        ORDER BY data_hora DESC
    ''', (usuario,))
    gastos = cursor.fetchall()
    conn.close()
    return gastos

# Função para definir limites de gastos
def definir_limite(usuario, tipo, valor):
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Verifica se já existe um limite para o tipo especificado
    cursor.execute('''
        SELECT id FROM limites
        WHERE usuario = ? AND tipo = ?
    ''', (usuario, tipo))
    limite_existente = cursor.fetchone()
    
    if limite_existente:
        # Atualiza o limite existente
        cursor.execute('''
            UPDATE limites
            SET valor = ?
            WHERE id = ?
        ''', (valor, limite_existente[0]))
    else:
        # Insere um novo limite
        cursor.execute('''
            INSERT INTO limites (usuario, tipo, valor)
            VALUES (?, ?, ?)
        ''', (usuario, tipo, valor))
    
    conn.commit()
    conn.close()

# Função para verificar limites de gastos
def verificar_limite(usuario, tipo):
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Obtém o limite definido
    cursor.execute('''
        SELECT valor FROM limites
        WHERE usuario = ? AND tipo = ?
    ''', (usuario, tipo))
    limite = cursor.fetchone()
    
    # Obtém o total de gastos no período
    if tipo == "Diário":
        cursor.execute('''
            SELECT SUM(valor) FROM gastos
            WHERE usuario = ? AND date(data_hora) = date('now')
        ''', (usuario,))
    elif tipo == "Semanal":
        cursor.execute('''
            SELECT SUM(valor) FROM gastos
            WHERE usuario = ? AND date(data_hora) >= date('now', 'weekday 0', '-7 days')
        ''', (usuario,))
    elif tipo == "Mensal":
        cursor.execute('''
            SELECT SUM(valor) FROM gastos
            WHERE usuario = ? AND strftime('%Y-%m', data_hora) = strftime('%Y-%m', 'now')
        ''', (usuario,))
    
    total_gastos = cursor.fetchone()[0] or 0
    conn.close()
    
    if limite:
        return limite[0], total_gastos
    else:
        return None, total_gastos

# Função para gerar respostas variadas
def gerar_resposta_saudacao():
    respostas = [
        "Olá! Eu sou o FinAI, seu assistente financeiro. Como posso ajudar? 😊",
        "Oi! Estou aqui para ajudar você a organizar suas finanças. O que precisa? 💰",
        "E aí! Pronto para cuidar das suas finanças? Me diga como posso ajudar! 🚀"
    ]
    return random.choice(respostas)  # Retorna uma resposta aleatória

def gerar_resposta_agradecimento():
    respostas = [
        "De nada! Estou aqui para ajudar. 😊",
        "Por nada! Conte comigo sempre que precisar. 💪",
        "Não há de quê! Qualquer coisa, é só chamar. 😄"
    ]
    return random.choice(respostas)  # Retorna uma resposta aleatória

def gerar_resposta_erro():
    respostas = [
        "Ops! Algo deu errado. Tente novamente. 😅",
        "Hmm, não entendi. Pode repetir, por favor? 🤔",
        "Desculpe, não consegui processar isso. Tente de outra forma. 😕"
    ]
    return random.choice(respostas)  # Retorna uma resposta aleatória

# Função para extrair valor e descrição da mensagem
def extrair_valor_descricao(mensagem):
    palavras = mensagem.split()
    valor = None
    descricao = ""
    
    for i, palavra in enumerate(palavras):
        if palavra.replace(".", "").isdigit():
            valor = float(palavra)
            # Captura a descrição após o valor, ignorando preposições como "no", "em", etc.
            descricao = " ".join(palavras[i + 2:]) if i + 2 < len(palavras) else "Sem descrição"
            break
    
    return valor, descricao

@app.route("/webhook", methods=["POST"])
def webhook():
    # Recebe a mensagem do usuário
    user_message = request.form.get("Body")
    user_number = request.form.get("From")

    # Inicializa a resposta
    resposta = MessagingResponse()

    # Lógica do Bot
    try:
        # Saudação
        if any(palavra in user_message.lower() for palavra in ["oi", "olá", "ola", "eae", "opa", "hello"]):
            resposta.message(gerar_resposta_saudacao())

        # Adicionar gasto
        elif any(palavra in user_message.lower() for palavra in ["gastei", "comprei", "adicione", "gasto", "gastar"]):
            valor, descricao = extrair_valor_descricao(user_message)
            if valor:
                adicionar_gasto(user_number, valor, descricao)
                resposta.message(f"✅ Gasto de R${valor} ({descricao}) adicionado em {datetime.now().strftime('%d/%m/%Y %H:%M')}!")
                
                # Verifica limites após adicionar o gasto
                for tipo in ["Diário", "Semanal", "Mensal"]:
                    limite, total_gastos = verificar_limite(user_number, tipo)
                    if limite and total_gastos > limite:
                        resposta.message(f"⚠️ Atenção! Você ultrapassou seu limite {tipo} de R${limite}. Total gasto: R${total_gastos}.")
            else:
                resposta.message("❌ Valor do gasto não encontrado. Use: 'gastei 30 no mercado' ou 'comprei 20 em lanche'.")

        # Ver gastos
        elif any(palavra in user_message.lower() for palavra in ["ver gastos", "meus gastos", "gastos", "extrato"]):
            gastos = obter_gastos(user_number)
            if gastos:
                gastos_formatados = "\n".join(
                    f"📅 {gasto[2]}: R${gasto[0]} ({gasto[1]})"
                    for gasto in gastos
                )
                total = sum(gasto[0] for gasto in gastos)
                resposta.message(f"📊 Seus gastos:\n{gastos_formatados}\n\n💸 Total: R${total}")
            else:
                resposta.message("ℹ️ Você ainda não adicionou gastos.")

        # Definir limite
        elif "definir limite" in user_message.lower():
            palavras = user_message.split()
            if len(palavras) >= 4 and palavras[2].lower() in ["diário", "semanal", "mensal"]:
                tipo = palavras[2].capitalize()
                valor = float(palavras[3])
                definir_limite(user_number, tipo, valor)
                resposta.message(f"✅ Limite {tipo} definido para R${valor}.")
            else:
                resposta.message("❌ Formato inválido. Use: 'definir limite diário 100'.")

        # Verificar limite
        elif "ver limite" in user_message.lower():
            palavras = user_message.split()
            if len(palavras) >= 3 and palavras[2].lower() in ["diário", "semanal", "mensal"]:
                tipo = palavras[2].capitalize()
                limite, total_gastos = verificar_limite(user_number, tipo)
                if limite:
                    resposta.message(f"📊 Seu limite {tipo} é R${limite}. Total gasto: R${total_gastos}.")
                else:
                    resposta.message(f"ℹ️ Você ainda não definiu um limite {tipo}.")
            else:
                resposta.message("❌ Formato inválido. Use: 'ver limite diário'.")

        # Comando de ajuda
        elif any(palavra in user_message.lower() for palavra in ["ajuda", "comandos", "help"]):
            resposta.message('''
📝 **Comandos disponíveis:**
- *Adicionar gasto*: "gastei 30 no mercado", "comprei 20 em lanche".
- *Ver gastos*: "ver gastos", "meus gastos".
- *Definir limite*: "definir limite diário 100", "definir limite semanal 500".
- *Ver limite*: "ver limite diário", "ver limite semanal".
- *Ajuda*: "ajuda", "comandos".
''')

        # Agradecimento
        elif any(palavra in user_message.lower() for palavra in ["obrigado", "obrigada", "valeu", "thanks"]):
            resposta.message(gerar_resposta_agradecimento())

        # Comando não reconhecido
        else:
            resposta.message(gerar_resposta_erro())

    except Exception as e:
        resposta.message(f"❌ Ocorreu um erro: {str(e)}")

    return str(resposta)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Usa a porta do Render ou 5000 como padrão
    app.run(host="0.0.0.0", port=port, debug=False)  # Defina debug=False para produção