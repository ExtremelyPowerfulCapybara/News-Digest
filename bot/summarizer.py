# ─────────────────────────────────────────────
#  summarizer.py  —  Claude generates digest
# ─────────────────────────────────────────────

import json
import time
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def summarize_news(articles: list[dict]) -> dict:
    """
    Sends articles to Claude and returns a bilingual digest dict with:
    - "es": { editor_note, sentiment, stories, quote }  <- Spanish (primary)
    - "en": { editor_note, sentiment, stories, quote }  <- English translation
    """
    news_text = ""
    for i, a in enumerate(articles, 1):
        news_text += f"{i}. [{a['source']}] {a['title']}\nURL: {a['url']}\n{a['content']}\n\n"

    prompt = f"""Eres un editor de noticias financieras produciendo un briefing matutino diario para una audiencia hispanohablante sofisticada. Voz: directa, seca, ocasionalmente sardónica — como un editor de mercados veterano que ha visto cada ciclo y encuentra el actual tanto alarmante como vagamente entretenido.

Analiza los artículos a continuación y devuelve un objeto JSON con EXACTAMENTE esta estructura:

{{
  "es": {{
    "editor_note": "2-3 oraciones abriendo el briefing del día. Siempre abre con 'Estimados humanos,' como las primeras dos palabras. Voz: directa, seca, ocasionalmente sardónica. Referencia la historia dominante. Primera persona. NO incluyas firma — se agrega por separado. Sin relleno.",

    "sentiment": {{
      "label_es": "Aversión al Riesgo" | "Cauteloso" | "Apetito por Riesgo",
      "label_en": "Risk-Off" | "Cautious" | "Risk-On",
      "position": <entero 5-95 donde 5=aversión extrema, 50=neutral, 95=apetito extremo>,
      "context_es": "Una oración explicando el sentimiento de hoy en español.",
      "context_en": "One sentence explaining today's sentiment in English."
    }},

    "stories": [
      {{
        "source": "Nombre de la fuente",
        "headline": "Titular conciso y específico en español",
        "body": "2-3 oraciones en español. Incluye cifras específicas, nombres, y por qué importa. Termina naturalmente.",
        "url": "URL original del artículo",
        "tag": "Uno de: Macro | FX | México | Comercio | Tasas | Mercados | Energía | Política"
      }}
    ],

    "quote": {{
      "text": "Una cita financiera o económica relevante que conecte temáticamente con las noticias de hoy. Debe ser real y verificable. Puede estar en español o inglés.",
      "attribution": "Nombre completo, fuente, año"
    }}
  }},

  "en": {{
    "editor_note": "Faithful English translation of the editor_note above. Keep the same voice and tone.",

    "sentiment": {{
      "label_es": "<same as above>",
      "label_en": "<same as above>",
      "position": <same integer as above>,
      "context_es": "<same as above>",
      "context_en": "<same as above>"
    }},

    "stories": [
      {{
        "source": "Same source name",
        "headline": "Faithful English translation of the headline",
        "body": "Faithful English translation of the body",
        "url": "Same original URL",
        "tag": "Same tag"
      }}
    ],

    "quote": {{
      "text": "<same quote as above>",
      "attribution": "<same attribution as above>"
    }}
  }}
}}

Reglas:
- Selecciona 5-7 historias, ordenadas por importancia
- Omite duplicados que cubran el mismo evento
- stories debe incluir la URL original de la lista de artículos
- Responde ÚNICAMENTE con el objeto JSON, sin preámbulo, sin markdown fences
- sentiment.position debe ser consistente con el label: Aversión al Riesgo = 5-35, Cauteloso = 36-64, Apetito por Riesgo = 65-95
- El bloque "en" es una traducción fiel del bloque "es" — mismas historias, mismas URLs, mismo sentimiento

Artículos:
{news_text}
"""

    print("  [summarizer] Sending to Claude (bilingual)...")
    for attempt in range(4):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}]
            )
            break
        except Exception as e:
            if "overloaded" in str(e).lower() and attempt < 3:
                wait = 30 * (attempt + 1)
                print(f"  [summarizer] API overloaded, retrying in {wait}s (attempt {attempt + 1}/4)...")
                time.sleep(wait)
            else:
                raise

    raw = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    digest = json.loads(raw)

    # Validate bilingual structure
    if "es" not in digest or "en" not in digest:
        raise ValueError(f"[summarizer] Missing bilingual keys. Got: {list(digest.keys())}")

    print(f"  [summarizer] Got {len(digest['es'].get('stories', []))} stories (ES+EN)")
    return digest
