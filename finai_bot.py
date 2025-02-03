from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import random  # Para respostas variadas

app = Flask(__name__)

# Dicionário para armazenar gastos dos usuários
usuarios = {}

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
        elif any(palavra in user_message.lower() for palavra in ["adicionar gasto", "gastei", "adicione", "gasto", "gastar"]):
            palavras = user_message.split()
            valor = None
            for i, palavra in enumerate(palavras):
                # Tenta converter a palavra para float (ignorando pontos como separadores decimais)
                if palavra.replace(".", "").isdigit():
                    valor = float(palavra)
                    # Extrai a descrição (tudo após o valor)
                    descricao = " ".join(palavras[i + 1:]) if i + 1 < len(palavras) else "Sem descrição"
                    break

            if valor:
                # Adiciona o gasto ao usuário com data e hora
                if user_number not in usuarios:
                    usuarios[user_number] = []
                usuarios[user_number].append({
                    "valor": valor,
                    "descricao": descricao,
                    "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M")
                })

                # Responde ao usuário
                resposta.message(f"✅ Gasto de R${valor} ({descricao}) adicionado em {datetime.now().strftime('%d/%m/%Y %H:%M')}!")
            else:
                resposta.message("❌ Valor do gasto não encontrado. Use: 'adicionar gasto 50 lanche'")

        # Ver gastos
        elif any(palavra in user_message.lower() for palavra in ["ver gastos", "meus gastos", "gastos", "extrato"]):
            if user_number in usuarios and usuarios[user_number]:
                # Formata os gastos para exibição
                gastos_formatados = "\n".join(
                    f"📅 {gasto['data_hora']}: R${gasto['valor']} ({gasto['descricao']})"
                    for gasto in usuarios[user_number]
                )
                total = sum(gasto["valor"] for gasto in usuarios[user_number])
                resposta.message(f"📊 Seus gastos:\n{gastos_formatados}\n\n💸 Total: R${total}")
            else:
                resposta.message("ℹ️ Você ainda não adicionou gastos.")

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
    app.run(debug=True)