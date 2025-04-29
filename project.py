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
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] # Cerca questa chiave nei secrets
    # --- NOTA IMPORTANTE SULLA CHIAVE YOUTUBE ---
    # Il codice cerca "youtube_api_key". Assicurati di aver generato
    # una CHIAVE API (non un ID Cliente OAuth) nella Google Cloud Console
    # per il progetto dove hai abilitato la YouTube Data API v3,
    # e di averla salvata nei segreti di Streamlit con il nome esatto "youtube_api_key".
    YOUTUBE_API_KEY = st.secrets["youtube_api_key"]

    configure(api_key=GEMINI_API_KEY)

except KeyError as e:
    # Errore più specifico
    missing_key = e.args[0]
    if missing_key == "GEMINI_API_KEY":
        st.error(f"Errore: Chiave API 'GEMINI_API_KEY' mancante nei segreti.")
    elif missing_key == "youtube_api_key":
        st.error(f"Errore: Chiave API 'youtube_api_key' mancante nei segreti.")
        st.info("Assicurati di aver generato una 'Chiave API' (non un ID Cliente OAuth) per YouTube Data API v3 nella Google Cloud Console e di averla aggiunta ai segreti.")
    else:
        st.error(f"Errore: Chiave '{missing_key}' mancante nei segreti.")
    st.error("Vai su 'Manage app' -> 'Settings' -> 'Secrets' per aggiungere le chiavi mancanti.")
    st.stop()
except Exception as e:
    st.error(f"Errore nella configurazione iniziale: {e}")
    st.stop()

# (Definizioni Modello, Prompt, Configurazioni - come prima)
MODEL_NAME = 'gemini-1.5-flash'
SYSTEM_PROMPT_MENTAL_HEALTH = """Sei "SoulCare AI"... (come prima)"""
SYSTEM_PROMPT_REPORT = """Analizza il seguente testo estratto... (come prima)"""
SYSTEM_PROMPT_DRUG = """Fornisci informazioni generali sul farmaco... (come prima)"""
try:
    SAFETY_SETTINGS = [ ... ] # Come prima
    GENERATION_CONFIG = { ... } # Come prima
    model = GenerativeModel(MODEL_NAME, safety_settings=SAFETY_SETTINGS, generation_config=GENERATION_CONFIG)
except Exception as e:
    st.error(f"Errore nella creazione del modello GenerativeModel: {e}")
    st.stop()

# ==================================================
# FUNZIONI HELPER
# (Incolla qui le definizioni complete: download_generated_report, load_lottie_url,
#  extract_text_from_pdf, extract_topic, fetch_youtube_videos,
#  generate_gemini_response - assicurati che fetch_youtube_videos usi YOUTUBE_API_KEY)
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
    start_phrases = ["@codex", "codex", "@SoulCare", "soulcare"]
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
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = model.generate_content(f"{system_prompt}\n\n{user_content}")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason
                st.error(f"Analisi bloccata ({reason}).")
                return f"Errore: Bloccato ({reason})."
            if hasattr(response, 'text') and response.text:
                disclaimer_app = "\n\n---\n**⚠️⚠️ DISCLAIMER FINALE (DA APP) ⚠️⚠️**\n*Ricorda: questa analisi è AUTOMATICA e NON SOSTITUISCE IL MEDICO/PROFESSIONISTA. Consulta SEMPRE un esperto qualificato.*" # Disclaimer più corto
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
    st.set_page_config(page_title="SoulCare AI - Salute Mentale", page_icon="❤️", layout="wide", initial_sidebar_state="expanded")

    # --- Sidebar ---
    with st.sidebar:
        try: st.image("soul.png", use_column_width=True)
        except Exception: st.warning("Immagine 'soul.png' non trovata.")
        page = st.selectbox("**MENU**", ["🏠 Home", "🧠 Coach del Benessere", "📝 Analisi Referto Medico", "💊 Info Farmaci", "🧑‍⚕️ Chiedi a un Esperto", "⚖️ Informativa Privacy", "🫂 Sostienici"])
        st.markdown(" Seguimi su:")
        st.markdown("""<style>...</style><div class="follow-me">...</div>""", unsafe_allow_html=True) # Incolla qui il tuo HTML

        if page == "🫂 Sostienici":
            st.markdown("### Sostieni SoulCare AI")
            st.markdown("Se trovi utile questa applicazione, considera di supportare il suo sviluppo:")
            # --- LINK AGGIORNATO ---
            buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
            st.link_button("Offrimi un caffè ☕", buy_me_a_coffee_url, use_container_width=True)
            st.markdown("*(Piattaforma semplice)*")
            st.markdown("---")
            # SOSTITUISCI CON IL TUO LINK STRIPE REALE
            stripe_payment_link = "https://buy.stripe.com/tuo_link_id"
            st.link_button("Dona con Carta (via Stripe) 💳", stripe_payment_link, use_container_width=True)
            st.markdown("*(Per donazioni con carta)*")

    # --- Contenuto Pagina Principale ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try: st.image(header_image_url)
    except Exception as img_err: st.warning(f"Avviso intestazione: {img_err}", icon="🖼️")

    # --- CONTENUTO SPECIFICO PER PAGINA ---

    if page == "🏠 Home":
        st.title("Benvenuto/a in SoulCare AI 🧑‍⚕️❤️")
        st.markdown("""**SoulCare AI** è un'applicazione...""")
        lottie_url_home = "https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json"
        lottie_animation_home = load_lottie_url(lottie_url_home)
        if lottie_animation_home: st_lottie(lottie_animation_home, speed=1, width=400, height=300, key="lottie_home")
        st.markdown("""**Linee Guida per l'Utilizzo:**...""")

    elif page == "🧠 Coach del Benessere":
        st.header("🧠 Coach Virtuale del Benessere")
        lottie_url_coach = "https://lottie.host/0c079fc2-f4df-452a-966b-3a852ffb9801/WjOxpGVduu.json"
        lottie_animation_coach = load_lottie_url(lottie_url_coach)
        if lottie_animation_coach: st_lottie(lottie_animation_coach, speed=1, width=220, height=300, key="lottie_coach")
        st.warning("SoulCare AI può fornire risposte imprecise...")

        if "chat_history_wellness" not in st.session_state: st.session_state.chat_history_wellness = []
        for message in st.session_state.chat_history_wellness:
            with st.chat_message(message["role"], avatar= "❤️" if message["role"]=="assistant" else "user"): st.markdown(message["content"])

        user_prompt = st.chat_input("Scrivi qui la tua domanda o riflessione...")
        if user_prompt:
            st.chat_message("user").markdown(user_prompt)
            st.session_state.chat_history_wellness.append({"role": "user", "content": user_prompt})
            with st.spinner("SoulCare AI sta pensando... 🤔"):
                # Potresti passare la history recente per contesto, ma per semplicità ora passiamo solo l'ultimo prompt
                # context = f"History (last few):\n{st.session_state.chat_history_wellness[-6:-1]}\n\nCurrent Question:\n{user_prompt}"
                context = user_prompt # Più semplice
                response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, context)
                with st.chat_message("assistant", avatar="❤️"): st.markdown(response_text)
                st.session_state.chat_history_wellness.append({"role": "assistant", "content": response_text})
                topic_for_youtube = extract_topic(user_prompt)
                video_suggestions = fetch_youtube_videos(topic_for_youtube)
                if video_suggestions:
                    st.markdown("---"); st.markdown("### Risorse Video Correlate (YouTube):")
                    for video in video_suggestions: st.markdown(f"- [{video['title']}]({video['url']})")

    elif page == "📝 Analisi Referto Medico":
        st.header("📝 Analisi Preliminare Referto Medico")
        st.markdown("**Carica il tuo referto medico in formato PDF:**")
        uploaded_file = st.file_uploader("Scegli PDF", type=["pdf"], label_visibility="collapsed", key="pdf_report_uploader")
        if uploaded_file is not None:
            try:
                pdf_bytes = uploaded_file.getvalue()
                text = extract_text_from_pdf(pdf_bytes)
                if text:
                    st.text_area("Testo Estratto:", text, height=300)
                    st.markdown("---")
                    if st.button("🔬 Analizza Testo", type="primary", key="analyze_report_btn"):
                        with st.spinner("Analisi referto..."):
                            analisi_output = generate_gemini_response(SYSTEM_PROMPT_REPORT, f"--- TESTO ---\n{text}\n--- FINE ---")
                            st.subheader("Risultato Analisi:")
                            st.markdown(analisi_output)
                            if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"analisi_referto_{uploaded_file.name[:20]}")
                else: st.error("Impossibile estrarre testo.")
            except Exception as e: st.error(f"Errore elaborazione PDF: {e}")

    elif page == "💊 Info Farmaci":
        st.header("💊 Informazioni Generali sui Farmaci")
        st.markdown("**Inserisci nome farmaco o carica PDF.**")
        input_method = st.radio("Metodo:", ("Testo", "Carica PDF"), horizontal=True, label_visibility="collapsed", key="drug_input_method")
        if input_method == "Testo":
            medicine_name = st.text_input("Nome farmaco:", placeholder="Es. Paracetamolo", key="drug_name_text")
            if st.button("Cerca Info", type="primary", key="search_drug_text_btn") and medicine_name:
                with st.spinner(f"Ricerca {medicine_name}..."):
                    analisi_output = generate_gemini_response(SYSTEM_PROMPT_DRUG, f"Farmaco: {medicine_name}")
                    st.subheader(f"Info su {medicine_name}:")
                    st.markdown(analisi_output)
                    if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"info_{medicine_name.replace(' ','_')}")
            elif st.button("Cerca Info", type="primary", key="search_drug_text_btn_empty") and not medicine_name: st.warning("Inserisci nome.")
        elif input_method == "Carica PDF":
             uploaded_file_drug = st.file_uploader("Scegli PDF", type=["pdf"], key="pdf_drug_uploader", label_visibility="collapsed")
             if uploaded_file_drug is not None:
                try:
                    pdf_bytes_drug = uploaded_file_drug.getvalue()
                    text_drug = extract_text_from_pdf(pdf_bytes_drug)
                    if text_drug:
                        st.text_area("Testo Estratto:", text_drug, height=200)
                        st.markdown("---")
                        medicine_from_pdf = st.text_input("Nome farmaco nel PDF:", key="drug_name_pdf")
                        if st.button("Analizza da PDF", type="primary", key="search_drug_pdf_btn") and medicine_from_pdf:
                            with st.spinner(f"Analisi {medicine_from_pdf}..."):
                                context_pdf = f"Farmaco: {medicine_from_pdf}\n\nContesto:\n{text_drug[:1000]}..."
                                analisi_output = generate_gemini_response(SYSTEM_PROMPT_DRUG, context_pdf)
                                st.subheader(f"Info su {medicine_from_pdf} (da PDF):")
                                st.markdown(analisi_output)
                                if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"info_{medicine_from_pdf.replace(' ','_')}_pdf")
                        elif st.button("Analizza da PDF", type="primary", key="search_drug_pdf_btn_empty") and not medicine_from_pdf: st.warning("Inserisci nome.")
                    else: st.error("Impossibile estrarre testo.")
                except Exception as e: st.error(f"Errore PDF: {e}")

    elif page == "🧑‍⚕️ Chiedi a un Esperto":
        st.header("🧑‍⚕️ Contatta un Esperto")
        st.markdown("""Hai bisogno di un parere più specifico o vuoi metterti in contatto? Compila il modulo Google qui sotto. La tua richiesta verrà inoltrata in modo confidenziale.\n\n*Ricorda: questo modulo è per richieste **non urgenti**. Per emergenze, contatta i servizi sanitari.*""")
        # --- LINK AGGIORNATO ---
        google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
        st.link_button("📝 Apri il Modulo di Contatto Sicuro", google_form_url, use_container_width=True, type="primary")
        st.markdown("---")
        st.markdown("""**Esperti Disponibili (Esempio):**\n- Dott.ssa Anjali Sharma (Psicologa)...""")

    elif page == "⚖️ Informativa Privacy":
        st.header("⚖️ Informativa sulla Privacy")
        # --- INSERISCI QUI IL TESTO COMPLETO DELLA TUA INFORMATIVA PRIVACY TRADOTTA ---
        st.markdown("""**Informativa sulla Privacy di SoulCare AI**: \n\n ... (Il tuo testo completo qui, ricorda l'email di contatto) ...""")

    elif page == "🫂 Sostienici":
        st.header("🫂 Sostienici")
        st.info("Grazie per considerare di supportare SoulCare AI! Trovi le opzioni per la donazione nella barra laterale a sinistra.")
        st.write("Per richieste di supporto tecnico o feedback, contattaci a skavtech.in@gmail.com")


# --- Chiamata finale ---
if __name__ == "__main__":
    main()
