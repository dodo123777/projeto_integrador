from email.mime import message

from flask import Blueprint, jsonify, request
import requests  # biblioteca HTTP para chamar a API do Gemini

from auth import auth_required  # decorator que valida o JWT antes de entrar na rota
from config import Config       # lê GEMINI_API_KEY e GEMINI_MODEL do .env / Render


# Blueprint registrado em app.py como chat_bp
chat_bp = Blueprint("chat", __name__)

# URL base da API — {model} é substituído pelo valor de GEMINI_MODEL em runtime
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def extract_reply(response_data):
        """Navega no JSON da Gemini e devolve o texto da resposta, limpando pensamentos do Gemma."""
        candidates = response_data.get("candidates") or []

        for candidate in candidates:
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
        
            full_text_parts = []
            for part in parts:
                text = part.get("text", "")
            
                # 1. Se a part vier explicitamente marcada como pensamento (em algumas versões da API)
                if part.get("thought") == True:
                    continue
                
                # 2. Se o pensamento vier misturado no texto (comum no Gemma 4)
                # O Gemma usa <|channel|>thought ou <channel|> para delimitar o pensamento
                if "<channel|>" in text:
                    # Pegamos apenas o que vem DEPOIS do fechamento do canal de pensamento
                    text = text.split("<channel|>")[-1]
                elif "<|channel|>thought" in text:
                    text = text.split("<|channel|>thought")[-1]
                
                if text.strip():
                    full_text_parts.append(text.strip())

            if full_text_parts:
                return "\n".join(full_text_parts)

        return None


def extract_error_message(response_data):
    """Tenta extrair uma mensagem de erro legível do JSON da Gemini."""
    error = response_data.get("error") or {}
    if error.get("message"):
        return error["message"]

    # promptFeedback aparece quando a API bloqueia a mensagem por segurança
    prompt_feedback = response_data.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason")
    if block_reason:
        return f"A solicitação foi bloqueada pela API ({block_reason})."

    return None


# POST /chat — protegida por JWT (auth_required rejeita sem token válido → 401)
@chat_bp.route("/chat", methods=["POST"])
@auth_required
def chat():
    # Segurança: garante que as variáveis de ambiente estão presentes antes de prosseguir
    if not Config.GEMINI_API_KEY:
        return jsonify({"erro": "GEMINI_API_KEY não configurada no servidor."}), 500

    if not Config.GEMINI_MODEL:
        return jsonify({"erro": "GEMINI_MODEL não configurado no servidor."}), 500

    # Lê o JSON do body; silent=True evita crash se o body não for JSON válido
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"erro": "Envie uma mensagem para o chat."}), 400

    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Você é um assistente virtual especializado em organização e produtividade, "
                        "projetado exclusivamente para apoiar pessoas com TDAH e Autismo.\n\n"
                        "Seu objetivo é ser um facilitador de rotina: tirar dúvidas sobre métodos de foco e "
                        "quebrar tarefas complexas em passos menores.\n\n"
                        "Siga estas REGRAS INQUEBRÁVEIS:\n\n"
                        "1. A BARREIRA CLÍNICA: Você NÃO é médico ou psicólogo. É proibido dar diagnósticos, "
                        "sugerir tratamentos ou remédios. Se o usuário relatar crises, responda com empatia: "
                        "'Como sou uma IA de organização, não posso dar orientações de saúde. Por favor, procure "
                        "um profissional qualificado.'\n\n"
                        "2. LIMITE DE DADOS: Você não tem acesso à agenda ou banco de dados real. Se solicitado, "
                        "diga: 'Ainda não tenho os cabos conectados à sua agenda real! Essa função chegará em breve.'\n\n"
                        "3. FORMATO: Use frases curtas, tópicos (bullet points) e negrito. Evite blocos de texto.\n\n"
                        "4. SILÊNCIO INTERNO (CRÍTICO): É ESTRITAMENTE PROIBIDO gerar monólogos internos, rascunhos, "
                        "análise de regras ou pensamentos em voz alta (ex: 'User says', 'Rule 1', 'Draft'). "
                        "Responda APENAS o texto final que o usuário deve ler. Vá direto ao ponto."
                        "REDAÇÃO FINAL APENAS: É terminantemente proibido incluir rascunhos, análises de regras, 'User says', 'Drafts' ou qualquer texto que não seja a resposta direta ao usuário."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": message}],
            }
        ],
        "generationConfig": {
            # Baixamos para 0.2 para ele ser mais obediente e menos 'criativo' na divagação.
            "temperature": 0.2,
            "maxOutputTokens": 1024,
            "response_mime_type": "text/plain",
            "stopSequences": ["<|channel|>thought", "<|think|>"],
            "thinking_config": { "include_thoughts": False }
        },
    }

    try:
        # A chave da API vai como query param (?key=...), não no header
        response = requests.post(
            GEMINI_API_URL.format(model=Config.GEMINI_MODEL),
            params={"key": Config.GEMINI_API_KEY},
            json=payload,
            timeout=30,  # segundos — evita o request ficar pendurado para sempre
        )
        response_data = response.json()
    except requests.Timeout:
        return jsonify({"erro": "A IA demorou demais para responder. Tente novamente."}), 504
    except requests.RequestException:
        return jsonify({"erro": "Não foi possível se conectar à API da IA."}), 502
    except ValueError:
        # response.json() lança ValueError se o body não for JSON válido
        return jsonify({"erro": "A API da IA retornou uma resposta inválida."}), 502

    error_message = extract_error_message(response_data)
    if not response.ok:
        return jsonify({"erro": error_message or "Falha ao obter resposta da IA."}), 502

    reply = extract_reply(response_data)
    if not reply:
        return jsonify({"erro": error_message or "A IA não retornou uma resposta em texto."}), 502

    # Devolve só o texto final para o front-end
    return jsonify({"reply": reply}), 200
