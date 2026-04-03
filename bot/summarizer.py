# ─────────────────────────────────────────────
#  summarizer.py  —  Claude generates digest
# ─────────────────────────────────────────────
import json
import re
import time
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def summarize_news(articles: list[dict], active_threads: list[str] | None = None) -> dict:
    """
    Sends articles to Claude and returns a bilingual digest dict with:
    - "es": { editor_note, sentiment, stories, quote }  <- Spanish (primary)
    - "en": { editor_note, sentiment, stories, quote }  <- English translation
    """
    active_threads = active_threads or []
    thread_context = ""
    if active_threads:
        tags_str = ", ".join(f'"{t}"' for t in active_threads)
        thread_context = f"\nLos siguientes temas han aparecido recurrentemente esta semana: {tags_str}. Si una historia continúa alguno de estos temas, usa el mismo tag exacto en el campo thread_tag.\n"

    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(f"{i}. [{a['source']}] {a['title']}\nURL: {a['url']}\n{a['content']}\n\n")
    news_text = "".join(parts)

    prompt = f"""Eres un editor de noticias financieras produciendo un briefing matutino diario para una audiencia hispanohablante sofisticada. Voz: directa, seca, ocasionalmente sardónica — como un editor de mercados veterano que ha visto cada ciclo y encuentra el actual tanto alarmante como vagamente entretenido.
{thread_context}
Analiza los artículos a continuación y devuelve un objeto JSON con EXACTAMENTE esta estructura:

{{
  "es": {{
    "editor_note": "2-3 oraciones abriendo el briefing del día. Siempre abre con 'Estimados humanos,' como las primeras dos palabras. Voz: directa, seca, ocasionalmente sardónica. Referencia la historia dominante. Primera persona. NO incluyas firma — se agrega por separado. Sin relleno.",

    "narrative_thread": "Una oración en español describiendo el tema macro dominante del día — el hilo conductor que conecta las historias más importantes.",

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
        "body": "Exactamente dos oraciones en español. Primera oración: hecho concreto — qué ocurrió, con un número o nombre específico. Segunda oración: qué significa — quién gana, quién pierde, o qué hay que observar a continuación. Sin resúmenes de agencia.",
        "url": "URL original del artículo",
        "tag": "Uno de: Macro | FX | México | Comercio | Tasas | Mercados | Energía | Política",
        "context_note": {{
          "es": "Una oración explicando por qué esta historia importa HOY — conecta con condiciones de mercado actuales, datos recientes, o eventos de la semana.",
          "en": "One sentence explaining why this story matters TODAY — connect to current market conditions, recent data, or this week's events."
        }},
        "thread_tag": "Si esta historia continúa un tema recurrente de la semana, escribe el tag exacto (e.g. 'Banxico: tasa'). Si es independiente, escribe null."
      }}
    ],

    "quote": {{
      "text": "Una cita financiera o económica relevante que conecte temáticamente con las noticias de hoy. Debe ser real y verificable. Puede estar en español o inglés.",
      "attribution": "Nombre completo, fuente, año"
    }}
  }},

  "en": {{
    "editor_note": "Faithful English translation of the editor_note above. Keep the same voice and tone.",

    "narrative_thread": "Faithful English translation of the narrative_thread above.",

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
        "tag": "Same tag",
        "context_note": {{
          "es": "<same as above>",
          "en": "Faithful English translation of context_note"
        }},
        "thread_tag": "<same as above or null>"
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
- Diversidad temática obligatoria: cada historia debe cubrir un tema distinto. Si varios artículos tratan el mismo evento o tema central (e.g. múltiples artículos sobre el conflicto Irán/petróleo, o sobre aranceles Trump), selecciona SOLO el más completo e informativo — descarta los demás sin excepción
- Nunca incluyas dos historias donde la pregunta central sea la misma, aunque provengan de fuentes distintas o tengan ángulos ligeramente diferentes
- stories debe incluir la URL original de la lista de artículos
- Responde ÚNICAMENTE con el objeto JSON, sin preámbulo, sin markdown fences
- sentiment.position debe ser consistente con el label: Aversión al Riesgo = 5-35, Cauteloso = 36-64, Apetito por Riesgo = 65-95
- El bloque "en" es una traducción fiel del bloque "es" — mismas historias, mismas URLs, mismo sentimiento
- context_note debe ser sustantivo: no repitas el cuerpo de la historia, aporta contexto nuevo
- thread_tag debe ser null si la historia es independiente; solo usa tags de la lista de temas recurrentes si aplica

Artículos:
{news_text}
"""

    print("  [summarizer] Sending to Claude (bilingual)...")
    for attempt in range(4):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8000,
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

    def clean_and_parse(text: str) -> dict:
        """Strip markdown fences and parse JSON, raising JSONDecodeError on failure."""
        text = text.strip()
        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0].strip()
        # Trim anything before the first '{' or after the last '}'
        start = text.find("{")
        end   = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
        return json.loads(text)

    # Try to parse; if malformed, re-ask Claude once with a repair prompt
    raw = message.content[0].text.strip()
    for parse_attempt in range(2):
        try:
            digest = clean_and_parse(raw)
            break
        except json.JSONDecodeError as e:
            if parse_attempt == 0:
                print(f"  [summarizer] JSON parse failed ({e}), asking Claude to repair...")
                repair_message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8000,
                    messages=[
                        {"role": "user",    "content": prompt},
                        {"role": "assistant", "content": raw},
                        {"role": "user",    "content": "Tu respuesta anterior contiene JSON malformado. Devuelve exactamente el mismo contenido pero como JSON válido y bien escapado. Sin preámbulo, sin markdown fences."},
                    ]
                )
                raw = repair_message.content[0].text.strip()
            else:
                raise ValueError(f"[summarizer] JSON malformado tras intento de reparación: {e}")

    # Validate bilingual structure
    if "es" not in digest or "en" not in digest:
        raise ValueError(f"[summarizer] Missing bilingual keys. Got: {list(digest.keys())}")

    print(f"  [summarizer] Got {len(digest['es'].get('stories', []))} stories (ES+EN)")
    return digest
