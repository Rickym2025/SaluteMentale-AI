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
import streamlit.components.v1 as components # Lo teniamo se serve per altro, ma non per il form
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
# (Codice configurazione Gemini invariato, usa st.secrets)
try:
    GEMINI_API_KEY = st.secrets["api_key"]
    YOUTUBE_API_KEY = st.secrets["youtube_api_key"]
    configure(api_key=GEMINI_API_KEY)
except KeyError as e:
    st.error(f"Errore: Chiave API mancante nei segreti di Streamlit: {e}.")
    st.stop()
except Exception as e:
    st.error(f"Errore nella configurazione iniziale: {e}")
    st.stop()

MODEL_NAME = 'gemini-1.5-flash'
# (Prompt di sistema invariati)
SYSTEM_PROMPT_MENTAL_HEALTH = """..."""
SYSTEM_PROMPT_REPORT = """..."""
SYSTEM_PROMPT_DRUG = """..."""

try:
    SAFETY_SETTINGS = [ ... ] # Come prima
    GENERATION_CONFIG = { ... } # Come prima
    model = GenerativeModel(MODEL_NAME, safety_settings=SAFETY_SETTINGS, generation_config=GENERATION_CONFIG)
except Exception as e:
    st.error(f"Errore nella creazione del modello GenerativeModel: {e}")
    st.stop()

# ==================================================
# FUNZIONI HELPER
# (Incolla qui le definizioni complete delle tue funzioni helper:
# download_generated_report, load_lottie_url, extract_text_from_pdf,
# extract_topic, fetch_youtube_videos, analizza_immagini_radiografiche, ecc.)
# ==================================================
# Esempio (assicurati siano le tue funzioni complete):
def download_generated_report(content, filename, format='txt'):
    # ... (codice come prima) ...
    try:
        output_bytes = content.encode('utf-8')
        b64 = base64.b64encode(output_bytes).decode()
        href = f'<a href="data:file/txt;base64,{b64}" download="{filename}.txt">Scarica Report (TXT)</a>'
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Errore creazione link download: {e}")

def load_lottie_url(url: str):
    # ... (codice come prima) ...
     try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
     except requests.exceptions.RequestException: return None
     except Exception: return None

def extract_text_from_pdf(file_bytes):
    # ... (codice come prima) ...
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            text = "".join(page.get_text() for page in doc)
            if not text.strip(): st.warning("Il PDF sembra vuoto o non contiene testo estraibile.")
            return text
    except Exception as e:
        st.error(f"Errore estrazione testo da PDF: {e}")
        return None

def extract_topic(prompt):
    # ... (codice come prima) ...
    start_phrases = ["@codex", "codex", "@SoulCare", "soulcare"]
    lower_prompt = prompt.lower()
    for phrase in start_phrases:
        if lower_prompt.startswith(phrase):
            prompt = prompt[len(phrase):].strip()
            break
    return prompt.strip()

def fetch_youtube_videos(query):
    # ... (codice come prima, usa YOUTUBE_API_KEY) ...
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
    except Exception as e:
        st.error(f"Errore ricerca YouTube: {e}")
    return video_details

def analizza_immagini_radiografiche(lista_immagini): # O la tua funzione di analisi
    # ... (codice come prima, assicurati che usi il modello corretto e restituisca testo + disclaimer app) ...
    if not lista_immagini: return "Errore: Nessuna immagine valida fornita."
    content_to_send = ["Analizza le seguenti immagini..."] + lista_immagini
    try:
        # Imposta il system prompt appropriato se necessario per questa chiamata
        # Questo dipende da come hai istanziato 'model' globalmente
        # Potrebbe essere meglio istanziare modelli specifici per task diversi
        # Ad esempio: model_analisi_rx = GenerativeModel(..., system_instruction=PROMPT_ANALISI_RX)
        response = model.generate_content(content_to_send) # Usa il modello globale per ora

        if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason
            return f"Errore: Analisi bloccata ({reason})."
        if hasattr(response, 'text') and response.text:
            disclaimer_app = "\n\n---\n**⚠️⚠️ DISCLAIMER FINALE (DA APP) ⚠️⚠️**\n*..." # Il tuo disclaimer
            return response.text.strip() + disclaimer_app
        else:
            return "Errore: Risposta vuota dall'IA."
    except Exception as e:
        st.error(f"Errore imprevisto durante l'analisi AI: {str(e)}")
        return f"Errore: Analisi fallita ({type(e).__name__})."

# ==================================================
# FUNZIONE PRINCIPALE DELL'APP STREAMLIT
# ==================================================
def main():
    st.set_page_config(page_title="SoulCare AI - Salute Mentale", page_icon="❤️", layout="wide", initial_sidebar_state="expanded")

    # --- Sidebar ---
    with st.sidebar:
        try: st.image("soul.png", use_column_width=True)
        except Exception: st.warning("Immagine 'soul.png' non trovata.")
        page = st.selectbox("**MENU**", ["🏠 Home", "🧠 Coach del Benessere", "📝 Analisi Referto Medico", "💊 Info Farmaci", "🧑‍⚕️ Chiedi a un Esperto", "⚖️ Informativa Privacy", "🫂 Sostienici"])
        st.markdown(" Seguimi su:")
        # (HTML social links come prima)
        st.markdown("""<style>...</style><div class="follow-me">...</div>""", unsafe_allow_html=True)

        # --- MODIFICA: Pulsanti donazione nella sidebar ---
        if page == "🫂 Sostienici": # Mostra solo qui
            st.markdown("### Sostieni SoulCare AI")
            st.markdown("Se trovi utile questa applicazione, considera di supportare il suo sviluppo con una donazione:")

            # --- BUY ME A COFFEE ---
            # SOSTITUISCI CON IL TUO LINK DI BUY ME A COFFEE
            buy_me_a_coffee_url = "https://www.buymeacoffee.com/tuonomeutente"
            st.link_button("Offrimi un caffè ☕", buy_me_a_coffee_url, use_container_width=True)
            st.markdown("*(Piattaforma semplice per piccole donazioni)*")
            st.markdown("---")

            # --- STRIPE PAYMENT LINK ---
            # SOSTITUISCI CON IL TUO STRIPE PAYMENT LINK
            stripe_payment_link = "https://buy.stripe.com/tuo_link_id"
            st.link_button("Dona con Carta (via Stripe) 💳", stripe_payment_link, use_container_width=True)
            st.markdown("*(Per donazioni tramite carta di credito/debito)*")

            # Rimosso il vecchio componente Razorpay HTML
            # components.html("""<form>...</form>""", ...)

    # --- Contenuto Pagina Principale ---

    # --- IMMAGINE DI INTESTAZIONE ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try:
        st.image(header_image_url)
    except Exception as img_err:
        st.warning(f"Avviso: Impossibile caricare l'immagine di intestazione. ({img_err})", icon="🖼️")

    # --- Contenuto delle diverse pagine ---

    if page == "🏠 Home":
        st.title("Benvenuto/a in SoulCare AI 🧑‍⚕️❤️")
        # ... (Testo e Lottie Home come prima) ...

    elif page == "🧠 Coach del Benessere":
        st.header("🧠 Coach Virtuale del Benessere")
        # ... (Lottie e avviso come prima) ...
        # ... (Logica Chat come prima, usa SYSTEM_PROMPT_MENTAL_HEALTH) ...

    elif page == "📝 Analisi Referto Medico":
        st.header("📝 Analisi Preliminare Referto Medico")
        # ... (Logica caricamento PDF e analisi come prima, usa SYSTEM_PROMPT_REPORT) ...

    elif page == "💊 Info Farmaci":
        st.header("💊 Informazioni Generali sui Farmaci")
        # ... (Logica input testo/PDF e analisi come prima, usa SYSTEM_PROMPT_DRUG) ...

    elif page == "🧑‍⚕️ Chiedi a un Esperto":
        st.header("🧑‍⚕️ Contatta un Esperto") # Titolo aggiornato
        st.markdown("""
            Hai bisogno di un parere più specifico o vuoi metterti in contatto?
            Compila il modulo Google qui sotto. La tua richiesta verrà inoltrata in modo confidenziale.

            *Ricorda: questo modulo è per richieste **non urgenti**. Per emergenze, contatta i servizi sanitari.*
        """)

        # --- MODIFICA: Link al Modulo Google ---
        # SOSTITUISCI QUESTO URL CON IL LINK AL TUO MODULO GOOGLE REALE
        google_form_url = "https://docs.google.com/forms/d/e/TUO_CODICE_FORM/viewform?usp=sf_link"

        st.link_button("📝 Apri il Modulo di Contatto Sicuro", google_form_url, use_container_width=True, type="primary")

        st.markdown("---")
        st.markdown("""
             **Esperti Disponibili (Esempio):**
             - Dott.ssa Anjali Sharma (Psicologa)
             - Dott. Sandeep (Psichiatra)
             - Dott.ssa Emily White (Consulente Salute Mentale)
         """)
        # Rimosso il vecchio componente HTML Formspree
        # components.html(contact_form_html, ...)

    elif page == "⚖️ Informativa Privacy":
        st.header("⚖️ Informativa sulla Privacy")
        # ... (Testo policy come prima, assicurati di inserire la tua email di contatto) ...

    elif page == "🫂 Sostienici":
        # Il contenuto principale di questa pagina è ora nella sidebar
        st.header("🫂 Sostienici")
        st.info("Grazie per considerare di supportare SoulCare AI! Trovi le opzioni per la donazione nella barra laterale a sinistra.")
        # Puoi aggiungere altro testo o immagini qui se vuoi
        st.write("Per richieste di supporto tecnico o feedback, contattaci a skavtech.in@gmail.com")


# --- Chiamata finale ---
if __name__ == "__main__":
    main()
