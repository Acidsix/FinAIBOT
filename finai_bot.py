from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import sqlite3
import random
import os

app = Flask(__name__)

# Conectar ao banco de dados
def conectar_banco():
    return sqlite3.connect('finai_bot.db', check_same_thread=False)

# Criar as tabelas necessárias
def criar_tabelas():
    with conectar_banco() as conn:
        cursor = conn.cursor()
        
        # Tabela de gastos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                valor REAL NOT NULL,
                descricao TEXT,
                data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de limites
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS limites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                tipo TEXT NOT NULL,  -- Diário, Semanal, Mensal
                valor REAL NOT NULL
            )
        ''')
        conn.commit()

criar_tabelas()

# Função para adicionar gastos ao banco de dados
def adicionar_gasto(usuario, valor, descricao):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO gastos (usuario, valor, descricao)
            VALUES (?, ?, ?)
        ''', (usuario, valor, descricao))
        conn.commit()

# Função para obter gastos do banco de dados
def obter_gastos(usuario):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT valor, descricao, strftime('%d/%m/%Y %H:%M', data_hora) FROM gastos
            WHERE usuario = ?
            ORDER BY data_hora DESC
        ''', (usuario,))
        return cursor.fetchall()

# Função para definir limites de gastos
def definir_limite(usuario, tipo, valor):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO limites (usuario, tipo, valor)
            VALUES (?, ?, ?)
            ON CONFLICT(usuario, tipo) DO UPDATE SET valor = excluded.valor
        ''', (usuario, tipo, valor))
        conn.commit()

# Função para verificar limites de gastos
def verificar_limite(usuario, tipo):
    with conectar_banco() as conn:
        cursor = conn.cursor()

        # Obtém o limite
        cursor.execute('''
            SELECT valor FROM limites WHERE usuario = ? AND tipo = ?
        ''', (usuario, tipo))
        limite = cursor.fetchone()

        # Obtém o total de gastos no período
        consulta = {
            "Diário": "date(data_hora) = date('now')",
            "Semanal": "date(data_hora) >= date('now', '-6 days')",
            "Mensal": "strftime('%Y-%m', data_hora) = strftime('%Y-%m', 'now')"
        }

        cursor.execute(f'''
            SELECT SUM(valor) FROM gastos WHERE usuario = ? AND {consulta[tipo]}
        ''', (usuario,))
        
        total_gastos = cursor.fetchone()[0] or 0

    return (limite[0] if limite else None), total_gastos

# Função para extrair valor e descrição da mensagem
def extrair_valor_descricao(mensagem):
    palavras = mensagem.split()
    valor = None
    descricao = ""
    
    for i, palavra in enumerate(palavras):
        try:
            valor = float(palavra)
            descricao = " ".join(palavras[i + 1:]) if i + 1 < len(palavras) else "Sem descrição"
            break
        except ValueError:
            continue

    return valor, descricao

@app.route("/webhook", methods=["POST"])
def webhook():
    user_message = request.form.get("Body")
    user_number = request.form.get("From")
    resposta = MessagingResponse()

    try:
        if any(p in user_message.lower() for p in ["oi", "olá", "ola", "eae", "opa", "hello"]):
            resposta.message("Olá! Como posso ajudar? 😊")

        elif any(p in user_message.lower() for p in ["gastei", "comprei", "adicione", "gasto", "gastar"]):
            valor, descricao = extrair_valor_descricao(user_message)
            if valor:
                adicionar_gasto(user_number, valor, descricao)
                resposta.message(f"✅ Gasto de R${valor:.2f} ({descricao}) registrado!")

                for tipo in ["Diário", "Semanal", "Mensal"]:
                    limite, total_gastos = verificar_limite(user_number, tipo)
                    if limite and total_gastos > limite:
                        resposta.message(f"⚠️ Você ultrapassou seu limite {tipo}: R${limite:.2f}. Total gasto: R${total_gastos:.2f}.")
            else:
                resposta.message("❌ Não consegui entender o valor. Tente: 'gastei 30 no mercado'.")

        elif "ver gastos" in user_message.lower():
            gastos = obter_gastos(user_number)
            if gastos:
                msg = "\n".join([f"{g[2]} - R${g[0]:.2f} ({g[1]})" for g in gastos])
                resposta.message(f"📊 Seus gastos:\n{msg}")
            else:
                resposta.message("ℹ️ Nenhum gasto registrado.")

        elif "definir limite" in user_message.lower():
            partes = user_message.split()
            if len(partes) >= 4 and partes[2].capitalize() in ["Diário", "Semanal", "Mensal"]:
                tipo, valor = partes[2].capitalize(), float(partes[3])
                definir_limite(user_number, tipo, valor)
                resposta.message(f"✅ Limite {tipo} definido para R${valor:.2f}.")
            else:
                resposta.message("❌ Formato inválido. Use: 'definir limite diário 100'.")

        elif "ver limite" in user_message.lower():
            partes = user_message.split()
            if len(partes) >= 3 and partes[2].capitalize() in ["Diário", "Semanal", "Mensal"]:
                tipo = partes[2].capitalize()
                limite, total_gastos = verificar_limite(user_number, tipo)
                resposta.message(f"📊 Limite {tipo}: R${limite:.2f} | Gasto: R${total_gastos:.2f}." if limite else f"ℹ️ Nenhum limite {tipo} definido.")

        else:
            resposta.message("🤖 Não entendi. Tente 'ajuda' para ver os comandos.")

    except Exception as e:
        resposta.message(f"❌ Erro: {str(e)}")

    return str(resposta)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
