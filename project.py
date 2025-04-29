# -*- coding: utf-8 -*-

# ==================================================
# IMPORT NECESSARI
# ==================================================
import streamlit as st
from PIL import Image
import base64
import os
import requests
from streamlit_lottie import st_lottie
import streamlit.components.v1 as components
from google.generativeai import configure, GenerativeModel
import fitz  # PyMuPDF
import re
import pandas as pd
from io import BytesIO
import time
from google.api_core import exceptions

# ==================================================
# CONFIGURAZIONE MODELLO E API KEYS (DA STREAMLIT SECRETS)
# ==================================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    # Assicurati che la chiave YouTube sia nei segreti se usi fetch_youtube_videos
    YOUTUBE_API_KEY = st.secrets.get("youtube_api_key") # Usiamo .get per non dare errore se manca
    configure(api_key=GEMINI_API_KEY)
except KeyError as e:
    missing_key = e.args[0]
    st.error(f"Errore: Chiave API '{missing_key}' mancante nei segreti.")
    st.stop()
except Exception as e:
    st.error(f"Errore nella configurazione iniziale: {e}")
    st.stop()

# --- Definizioni Modello e Prompt ---
MODEL_NAME = 'gemini-1.5-flash'
SYSTEM_PROMPT_MENTAL_HEALTH = """Sei "Salute Mentale AI", un assistente virtuale focalizzato sul benessere mentale. **Rispondi sempre e solo in ITALIANO.** Il tuo obiettivo è fornire supporto informativo, psicoeducazione generale e suggerimenti per il benessere, basandoti sulle domande dell'utente. **NON SEI UN TERAPEUTA E NON PUOI FORNIRE DIAGNOSI O CONSULENZE MEDICHE.** Quando rispondi: - Usa un tono empatico, calmo e di supporto. - Fornisci informazioni generali e basate su concetti noti di psicologia e benessere mentale. - Suggerisci strategie di coping generali (es. tecniche di rilassamento, mindfulness, importanza del sonno e dell'attività fisica). - Incoraggia l'utente a cercare supporto professionale qualificato (psicologo, psicoterapeuta, medico) per problemi specifici o persistenti. - **Includi sempre alla fine un disclaimer chiaro**: "Ricorda, questa è un'interazione con un'IA e non sostituisce il parere di un professionista della salute mentale. Se stai attraversando un momento difficile, considera di parlarne con un medico, uno psicologo o uno psicoterapeuta." """
SYSTEM_PROMPT_REPORT = """Analizza il seguente testo estratto da un referto medico. **Rispondi sempre e solo in ITALIANO.** Fornisci un riassunto conciso dei punti principali o dei risultati menzionati. **NON FARE INTERPRETAZIONI MEDICHE O DIAGNOSI.** Limita l'analisi a quanto scritto nel testo. Alla fine, ricorda all'utente: "Questa è un'analisi automatica del testo fornito e non sostituisce l'interpretazione di un medico. Discuti sempre il referto completo con il tuo medico curante." """
SYSTEM_PROMPT_DRUG = """Fornisci informazioni generali sul farmaco menzionato o descritto nel testo. **Rispondi sempre e solo in ITALIANO.** Includi (se trovi informazioni): indicazioni d'uso generali, meccanismo d'azione di base, effetti collaterali comuni e principali avvertenze. **NON FORNIRE CONSIGLI SUL DOSAGGIO O SULL'USO SPECIFICO.** Enfatizza che queste sono informazioni generali e **NON sostituiscono il foglietto illustrativo o il parere del medico/farmacista.** Concludi con: "Consulta sempre il tuo medico o farmacista prima di assumere qualsiasi farmaco e leggi attentamente il foglietto illustrativo." """

try:
    SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    GENERATION_CONFIG = { "temperature": 0.6, "top_p": 0.95, "top_k": 40, "max_output_tokens": 4096 }
    model_base = GenerativeModel(MODEL_NAME, safety_settings=SAFETY_SETTINGS, generation_config=GENERATION_CONFIG)
except Exception as e:
    st.error(f"Errore creazione modello: {e}"); st.stop()

# ==================================================
# FUNZIONI HELPER
# ==================================================
def download_generated_report(content, filename, format='txt'):
    try:
        cleaned_content = content.split("\n\n---\n**⚠️⚠️ DISCLAIMER FINALE (DA APP) ⚠️⚠️**")[0]
        output_bytes = cleaned_content.encode('utf-8')
        b64 = base64.b64encode(output_bytes).decode()
        href = f'<a href="data:file/txt;base64,{b64}" download="{filename}.txt">Scarica Report (TXT)</a>'
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e: st.error(f"Errore download: {e}")

def load_lottie_url(url: str):
     try: response = requests.get(url, timeout=10); response.raise_for_status(); return response.json()
     except: return None

def extract_text_from_pdf(file_bytes):
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            text = "".join(page.get_text() for page in doc)
            if not text.strip(): st.warning("PDF vuoto o senza testo.")
            return text
    except Exception as e: st.error(f"Errore PDF: {e}"); return None

def extract_topic(prompt):
    start_phrases = ["@codex", "codex", "@SoulCare", "soulcare", "@Salute Mentale AI", "salute mentale ai"]
    lower_prompt = prompt.lower()
    for phrase in start_phrases:
        if lower_prompt.startswith(phrase): prompt = prompt[len(phrase):].strip(); break
    prompt = re.sub(r'^(cosa è|come posso|parlami di|spiegami)\s+', '', prompt, flags=re.IGNORECASE).strip()
    return prompt if prompt else "benessere mentale generale"

def fetch_youtube_videos(query):
    if not YOUTUBE_API_KEY:
        # st.info("Ricerca video YouTube disabilitata (manca API key).") # Rendi silenzioso
        return []
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = { "part": "snippet", "q": f"{query} benessere mentale OR psicologia", "type": "video", "maxResults": 3, "relevanceLanguage": "it", "key": YOUTUBE_API_KEY }
    video_details = []
    try:
        response = requests.get(search_url, params=params, timeout=10); response.raise_for_status()
        results = response.json().get("items", [])
        for item in results:
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {}); video_title = snippet.get("title")
            if video_id and video_title:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                video_details.append({"title": video_title, "url": video_url, "video_id": video_id})
    except Exception as e: st.error(f"Errore ricerca YT: {e}") # Logga errore se avviene
    return video_details

def generate_gemini_response(system_prompt, user_content):
    """ Chiama l'API Gemini e gestisce errori/tentativi. """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            temp_model = GenerativeModel(MODEL_NAME, safety_settings=SAFETY_SETTINGS, generation_config=GENERATION_CONFIG, system_instruction=system_prompt)
            response = temp_model.generate_content(user_content)
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason
                st.error(f"Risposta bloccata ({reason})."); return f"Errore: Bloccato ({reason})."
            if hasattr(response, 'text') and response.text:
                disclaimer_app = "\n\n---\n**⚠️⚠️ DISCLAIMER FINALE (DA APP) ⚠️⚠️**\n*Ricorda: questa analisi è AUTOMATICA e NON SOSTITUISCE IL MEDICO/PROFESSIONISTA. Consulta SEMPRE un esperto qualificato.*"
                return response.text.strip() + disclaimer_app
            else:
                st.warning(f"Risposta vuota (Tentativo {attempt + 1}).")
                if attempt == max_retries - 1: return "Errore: Risposta vuota dall'IA."
                time.sleep(2)
        except exceptions.GoogleAPIError as e:
            st.warning(f"Errore API Google (Tentativo {attempt + 1}): {e}")
            if "quota" in str(e).lower(): return "Errore: Quota API superata."
            if attempt < max_retries - 1: time.sleep(2)
            else: return "Errore: API non raggiungibile."
        except Exception as e:
            st.error(f"Errore imprevisto analisi: {e}")
            return f"Errore: Analisi fallita ({type(e).__name__})."
    return "Errore: Analisi fallita."


# ==================================================
# FUNZIONE PRINCIPALE DELL'APP STREAMLIT
# ==================================================
def main():
    # Riscritto per chiarezza
    st.set_page_config(
        page_title="Salute Mentale AI",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # URL per donazioni (SOSTITUISCI CON I TUOI LINK REALI)
    buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
    stripe_payment_link = "https://buy.stripe.com/tuo_link_id"
    google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
    contact_email = "[LA TUA EMAIL DI CONTATTO]" # Sostituisci

    # --- Sidebar ---
    with st.sidebar:
        # Opzionale: Ripristinata immagine se 'soul.png' esiste
        if os.path.exists("soul.png"):
             try: st.image("soul.png") # Rimosso use_column_width
             except Exception: pass # Ignora se non carica
        else:
             st.info("Immagine 'soul.png' non presente.")

        st.markdown("### Menu Principale")
        page_options = ["🏠 Home", "🧠 Coach del Benessere", "📝 Analisi Referto Medico", "💊 Info Farmaci",
                         "🧑‍⚕️ Chiedi a un Esperto", "--- Strumenti Correlati ---", "☢️ App Analisi Radiografie",
                         "🩸 App Analisi Sangue", "--- Info e Supporto ---", "⚖️ Informativa Privacy", "🫂 Sostienici"]
        separator_values = ["--- Strumenti Correlati ---", "--- Info e Supporto ---"]
        def format_func(option): return "---" if option in separator_values else option
        page = st.sidebar.selectbox("**MENU**", page_options, label_visibility="collapsed", format_func=format_func)

        if page == "🫂 Sostienici":
            st.markdown("### Sostieni Salute Mentale AI")
            st.markdown("Se trovi utile l'app:")
            st.link_button("Offrimi un caffè ☕", buy_me_a_coffee_url, use_container_width=True)
            st.markdown("*(Semplice e veloce)*"); st.markdown("---")
            st.link_button("Dona con Carta (Stripe) 💳", stripe_payment_link, use_container_width=True)
            st.markdown("*(Tramite piattaforma sicura)*")

        st.markdown("---")
        st.markdown(" Seguimi su:")
        # INCOLLA QUI IL TUO HTML PER I LINK SOCIAL
        # Esempio semplice:
        st.markdown("- [GitHub](https://github.com/tuoutente)")
        st.markdown("- [Twitter/X](https://twitter.com/tuoutente)")
        # Oppure usa il tuo HTML complesso con immagini:
        # st.markdown("""<style>...</style><div class="follow-me">...</div>""", unsafe_allow_html=True)

    # --- Contenuto Pagina Principale ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try: st.image(header_image_url)
    except Exception as img_err: st.warning(f"Avviso intestazione: {img_err}", icon="🖼️")

    # --- CONTENUTO SPECIFICO PER PAGINA ---
    if page not in separator_values:
        if page == "🏠 Home":
            st.title("Benvenuto/a in Salute Mentale AI 🧠❤️")
            st.markdown("""**Salute Mentale AI** è un assistente virtuale...""")
            lottie_url_home = "https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json"
            lottie_animation_home = load_lottie_url(lottie_url_home)
            if lottie_animation_home: st_lottie(lottie_animation_home, speed=1, width=400, height=300, key="lottie_home")
            st.markdown("---")
            st.subheader("Linee Guida per l'Utilizzo:")
            st.markdown("""*   **Scopo Informativo**: ...\n*   **Condotta Rispettosa**: ...\n*   **Privacy e Dati**: ...\n*   **Emergenze**: ...\n*   **Uso Responsabile**: ...\n*   **Feedback**: ...""")

        elif page == "🧠 Coach del Benessere":
            st.header("🧠 Coach Virtuale del Benessere")
            lottie_url_coach = "https://lottie.host/0c079fc2-f4df-452a-966b-3a852ffb9801/WjOxpGVduu.json"
            lottie_animation_coach = load_lottie_url(lottie_url_coach)
            if lottie_animation_coach: st_lottie(lottie_animation_coach, speed=1, width=220, height=300, key="lottie_coach")
            st.warning("**Promemoria:** Sono un'IA di supporto...")

            if "chat_history_wellness" not in st.session_state: st.session_state.chat_history_wellness = []
            # Mostra solo l'ultima risposta se presente
            if st.session_state.chat_history_wellness:
                 last_resp = st.session_state.chat_history_wellness[-1]
                 if last_resp["role"] == "assistant":
                      with st.chat_message("assistant", avatar="❤️"): st.markdown(last_resp["content"])
                 st.markdown("---")

            # Input utente con Text Area
            user_prompt_wellness = st.text_area("Scrivi qui la tua domanda o riflessione...", height=150, key="wellness_input", label_visibility="collapsed")
            submit_wellness = st.button("Invia al Coach AI ➡️", key="wellness_submit", type="primary")

            if submit_wellness and user_prompt_wellness:
                # Mostra input utente visivamente
                with st.chat_message("user"): st.markdown(user_prompt_wellness)
                with st.spinner("Salute Mentale AI sta elaborando... 🤔"):
                    response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, user_prompt_wellness)
                    # Mostra la nuova risposta
                    with st.chat_message("assistant", avatar="❤️"): st.markdown(response_text)
                    # Sovrascrivi la history solo con l'ultima risposta valida dell'assistente
                    if not response_text.startswith("Errore:"):
                        st.session_state.chat_history_wellness = [{"role": "assistant", "content": response_text}]
                    # Suggerimenti Video
                    topic_for_youtube = extract_topic(user_prompt_wellness)
                    video_suggestions = fetch_youtube_videos(topic_for_youtube)
                    if video_suggestions:
                        st.markdown("---"); st.markdown("### Risorse Video:")
                        for video in video_suggestions: st.markdown(f"- [{video['title']}]({video['url']})")
            elif submit_wellness and not user_prompt_wellness: st.warning("Inserisci una domanda.")

        elif page == "📝 Analisi Referto Medico":
            st.header("📝 Analisi Referto Medico")
            # ... (codice analisi referto come prima) ...

        elif page == "💊 Info Farmaci":
            st.header("💊 Info Farmaci")
            # ... (codice info farmaci come prima) ...

        elif page == "🧑‍⚕️ Chiedi a un Esperto":
            st.header("🧑‍⚕️ Contatta un Esperto")
            # ... (codice modulo google come prima) ...

        elif page == "☢️ App Analisi Radiografie":
            st.header("App Analisi Radiografie ☢️")
            # ... (codice link app radiografie come prima) ...

        elif page == "🩸 App Analisi Sangue":
            st.header("App Analisi Sangue 🩸")
            # ... (codice link app sangue come prima) ...

        elif page == "⚖️ Informativa Privacy":
            st.header("⚖️ Informativa sulla Privacy")
            st.markdown(f"""**Informativa sulla Privacy di Salute Mentale AI** ... (Testo completo qui, usa {contact_email})""")

        elif page == "🫂 Sostienici":
            st.header("🫂 Sostienici")
            st.success("🙏 Grazie per aver visitato questa pagina! 🙏")
            st.info("Trovi le opzioni per la donazione nella barra laterale...")
            st.write("Per supporto: ...")

        # --- SEZIONE DONAZIONE FOOTER (VISIBILE IN FONDO A TUTTE LE PAGINE VALIDE) ---
        st.markdown("---")
        st.markdown("#### Ti piace questa app? ❤️")
        st.markdown("Mantenere e migliorare **Salute Mentale AI** richiede impegno...")
        # --- CORREZIONE QUI: Rimosso l'argomento Ellipsis (...) ---
        st.link_button(
            "☕ Offrimi un caffè (Buy Me a Coffee)",
            buy_me_a_coffee_url,
            use_container_width=True, # Aggiunto argomento keyword valido
            type="primary"             # Aggiunto argomento keyword valido
        )
        st.caption("Anche un piccolo contributo aiuta!")

    # --- Footer Finale (Caption) ---
    st.markdown("---")
    st.caption("Applicazione sviluppata con Streamlit e Google Gemini...")

# --- Chiamata finale ---
if __name__ == "__main__":
    main()
