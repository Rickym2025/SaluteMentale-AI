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
# (Codice configurazione Gemini invariato)
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    YOUTUBE_API_KEY = st.secrets["youtube_api_key"]
    configure(api_key=GEMINI_API_KEY)
except KeyError as e:
    missing_key = e.args[0]
    st.error(f"Errore: Chiave API '{missing_key}' mancante nei segreti.")
    st.stop() # Stoppa l'app se mancano chiavi essenziali
except Exception as e:
    st.error(f"Errore nella configurazione iniziale: {e}")
    st.stop()

MODEL_NAME = 'gemini-1.5-flash'
# (Prompt di sistema invariati)
SYSTEM_PROMPT_MENTAL_HEALTH = """Sei "Salute Mentale AI"..."""
SYSTEM_PROMPT_REPORT = """Analizza il seguente testo estratto..."""
SYSTEM_PROMPT_DRUG = """Fornisci informazioni generali sul farmaco..."""

try:
    SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    GENERATION_CONFIG = { "temperature": 0.6, "top_p": 0.95, "top_k": 40, "max_output_tokens": 4096 }
    model = GenerativeModel(MODEL_NAME, safety_settings=SAFETY_SETTINGS, generation_config=GENERATION_CONFIG)
except Exception as e:
    st.error(f"Errore nella creazione del modello GenerativeModel: {e}")
    st.stop()

# ==================================================
# FUNZIONI HELPER
# (Incolla qui le definizioni complete: download_generated_report, load_lottie_url,
#  extract_text_from_pdf, extract_topic, fetch_youtube_videos, generate_gemini_response)
# ==================================================
def download_generated_report(content, filename, format='txt'):
    try:
        output_bytes = content.encode('utf-8')
        b64 = base64.b64encode(output_bytes).decode()
        href = f'<a href="data:file/txt;base64,{b64}" download="{filename}.txt">Scarica Report (TXT)</a>'
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e: st.error(f"Errore download: {e}")

def load_lottie_url(url: str):
     try:
        response = requests.get(url, timeout=10)
        response.raise_for_status(); return response.json()
     except: return None

def extract_text_from_pdf(file_bytes):
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            text = "".join(page.get_text() for page in doc)
            if not text.strip(): st.warning("PDF vuoto o senza testo.")
            return text
    except Exception as e: st.error(f"Errore estrazione PDF: {e}"); return None

def extract_topic(prompt):
    start_phrases = ["@codex", "codex", "@SoulCare", "soulcare", "@Salute Mentale AI", "salute mentale ai"]
    lower_prompt = prompt.lower()
    for phrase in start_phrases:
        if lower_prompt.startswith(phrase): prompt = prompt[len(phrase):].strip(); break
    return prompt.strip()

def fetch_youtube_videos(query):
    if not YOUTUBE_API_KEY: return []
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = { "part": "snippet", "q": f"{query} benessere mentale OR psicologia", "type": "video", "maxResults": 3, "relevanceLanguage": "it", "key": YOUTUBE_API_KEY }
    video_details = []
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("items", [])
        for item in results:
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            video_title = snippet.get("title")
            if video_id and video_title:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                video_details.append({"title": video_title, "url": video_url, "video_id": video_id})
    except Exception as e: st.error(f"Errore ricerca YouTube: {e}")
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
                st.error(f"Analisi bloccata ({reason})."); return f"Errore: Bloccato ({reason})."
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
    st.set_page_config(page_title="Salute Mentale AI", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

    # URL per donazioni (assicurati siano corretti)
    buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
    stripe_payment_link = "https://buy.stripe.com/tuo_link_id" # Sostituisci

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Menu Principale")
        page_options = [
            "🏠 Home", "🧠 Coach del Benessere", "📝 Analisi Referto Medico", "💊 Info Farmaci",
            "🧑‍⚕️ Chiedi a un Esperto", "--- Strumenti Correlati ---", "☢️ App Analisi Radiografie",
            "🩸 App Analisi Sangue", "--- Info e Supporto ---", "⚖️ Informativa Privacy", "🫂 Sostienici"
        ]
        separator_values = ["--- Strumenti Correlati ---", "--- Info e Supporto ---"]
        def format_func(option): return "---" if option in separator_values else option
        page = st.sidebar.selectbox("**MENU**", page_options, label_visibility="collapsed", format_func=format_func)

        # Mostra pulsanti donazione nella sidebar SOLO se nella pagina Sostienici
        if page == "🫂 Sostienici":
            st.markdown("### Sostieni Salute Mentale AI")
            st.markdown("...") # Testo sidebar come prima
            st.link_button("Offrimi un caffè ☕", buy_me_a_coffee_url, use_container_width=True)
            st.markdown("...") # Testo sidebar come prima
            st.link_button("Dona con Carta (via Stripe) 💳", stripe_payment_link, use_container_width=True)
            st.markdown("...") # Testo sidebar come prima

        st.markdown("---") # Separatore prima dei link social
        st.markdown(" Seguimi su:")
        # Incolla qui il tuo HTML per i link social
        st.markdown("""<style>...</style><div class="follow-me">...</div>""", unsafe_allow_html=True)


    # --- Contenuto Pagina Principale ---

    # --- Immagine di Intestazione ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try: st.image(header_image_url)
    except Exception as img_err: st.warning(f"Avviso intestazione: {img_err}", icon="🖼️")

    # --- CONTENUTO SPECIFICO PER PAGINA (Renderizza solo se non è un separatore) ---
    if page not in separator_values:
        if page == "🏠 Home":
            st.title("Benvenuto/a in Salute Mentale AI 🧠❤️")
            st.markdown("""**Salute Mentale AI** è un assistente virtuale...""")
            lottie_url_home = "https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json"
            lottie_animation_home = load_lottie_url(lottie_url_home)
            if lottie_animation_home: st_lottie(lottie_animation_home, speed=1, width=400, height=300, key="lottie_home")
            st.markdown("""**Linee Guida per l'Utilizzo:**\n*   **Scopo Informativo**: ...\n*   **Condotta Rispettosa**: ...\n*   **Privacy e Dati**: ...\n*   **Emergenze**: ...\n*   **Uso Responsabile**: ...\n*   **Feedback**: ...""")

        elif page == "🧠 Coach del Benessere":
            st.header("🧠 Coach Virtuale del Benessere")
            # ... (Lottie, avviso, logica Chat come prima) ...

        elif page == "📝 Analisi Referto Medico":
            st.header("📝 Analisi Preliminare Referto Medico")
            # ... (Logica caricamento PDF e analisi come prima) ...

        elif page == "💊 Info Farmaci":
            st.header("💊 Informazioni Generali sui Farmaci")
            # ... (Logica input testo/PDF e analisi come prima) ...

        elif page == "🧑‍⚕️ Chiedi a un Esperto":
            st.header("🧑‍⚕️ Contatta un Esperto")
            # ... (Testo e link Modulo Google come prima) ...

        elif page == "☢️ App Analisi Radiografie":
            st.header("Rimando all'App Analisi Radiografie")
            # ... (Testo e link App Radiografie come prima) ...

        elif page == "🩸 App Analisi Sangue":
            st.header("Rimando all'App Analisi Sangue")
            # ... (Testo e link App Sangue come prima) ...

        elif page == "⚖️ Informativa Privacy":
            st.header("⚖️ Informativa sulla Privacy")
            # --- INSERISCI QUI IL TESTO COMPLETO ---
            st.markdown("""**Informativa sulla Privacy di Salute Mentale AI**: \n\n ... (Il tuo testo completo qui) ...""")

        elif page == "🫂 Sostienici":
            st.header("🫂 Sostienici")
            st.success("🙏 Grazie per essere arrivato fin qui! 🙏") # Messaggio di ringraziamento
            st.info("Trovi le opzioni per la donazione nella barra laterale a sinistra. Ogni contributo, anche piccolo, fa la differenza!")
            st.write("Per richieste di supporto tecnico o feedback, contattaci a skavtech.in@gmail.com")

        # --- SEZIONE DONAZIONE "BUY ME A COFFEE" VISIBILE IN FONDO A TUTTE LE PAGINE VALIDE ---
        st.markdown("---") # Separatore
        st.markdown("#### Ti piace questa app? ❤️")
        st.markdown("Mantenere e migliorare strumenti come **Salute Mentale AI** richiede tempo e risorse. Se trovi valore in questa applicazione, considera di offrirmi un caffè virtuale!")
        st.link_button("☕ Offrimi un caffè (Buy Me a Coffee)", buy_me_a_coffee_url, use_container_width=True, type="primary")
        st.caption("Anche un piccolo contributo aiuta a sostenere il progetto!")

    # --- Footer Finale (Caption) ---
    st.markdown("---")
    st.caption("Applicazione sviluppata con Streamlit e Google Gemini. Ricorda: consulta sempre un medico o professionista qualificato.")

# --- Chiamata finale ---
if __name__ == "__main__":
    main()
