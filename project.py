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
    YOUTUBE_API_KEY = st.secrets["youtube_api_key"]
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
SYSTEM_PROMPT_MENTAL_HEALTH = """Sei "Salute Mentale AI", un assistente virtuale focalizzato sul benessere mentale. **Rispondi sempre e solo in ITALIANO.**
Il tuo obiettivo è fornire supporto informativo, psicoeducazione generale e suggerimenti per il benessere, basandoti sulle domande dell'utente.
**NON SEI UN TERAPEUTA E NON PUOI FORNIRE DIAGNOSI O CONSULENZE MEDICHE.**
Quando rispondi:
- Usa un tono empatico, calmo e di supporto.
- Fornisci informazioni generali e basate su concetti noti di psicologia e benessere mentale.
- Suggerisci strategie di coping generali (es. tecniche di rilassamento, mindfulness, importanza del sonno e dell'attività fisica).
- Incoraggia l'utente a cercare supporto professionale qualificato (psicologo, psicoterapeuta, medico) per problemi specifici o persistenti.
- **Includi sempre alla fine un disclaimer chiaro**: "Ricorda, questa è un'interazione con un'IA e non sostituisce il parere di un professionista della salute mentale. Se stai attraversando un momento difficile, considera di parlarne con un medico, uno psicologo o uno psicoterapeuta."
"""
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
    model = GenerativeModel(MODEL_NAME, safety_settings=SAFETY_SETTINGS, generation_config=GENERATION_CONFIG)
except Exception as e:
    st.error(f"Errore creazione modello: {e}"); st.stop()

# ==================================================
# FUNZIONI HELPER
# ==================================================
def download_generated_report(content, filename, format='txt'):
    try:
        output_bytes = content.encode('utf-8')
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
    except Exception as e: st.error(f"Errore ricerca YT: {e}")
    return video_details

def generate_gemini_response(system_prompt, user_content):
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

# ==================================================
# FUNZIONE PRINCIPALE DELL'APP STREAMLIT
# ==================================================
def main():
    st.set_page_config(page_title="Salute Mentale AI", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Menu Principale")
        page_options = ["🏠 Home", "🧠 Coach del Benessere", "📝 Analisi Referto Medico", "💊 Info Farmaci",
                         "🧑‍⚕️ Chiedi a un Esperto", "--- Strumenti Correlati ---", "☢️ App Analisi Radiografie",
                         "🩸 App Analisi Sangue", "--- Info e Supporto ---", "⚖️ Informativa Privacy", "🫂 Sostienici"]
        separator_values = ["--- Strumenti Correlati ---", "--- Info e Supporto ---"]
        def format_func(option): return "---" if option in separator_values else option
        page = st.sidebar.selectbox("**MENU**", page_options, label_visibility="collapsed", format_func=format_func)

        # Mostra pulsanti donazione (come prima)
        if page == "🫂 Sostienici":
            st.markdown("### Sostieni Salute Mentale AI")
            st.markdown("Se trovi utile questa applicazione, considera di supportare il suo sviluppo:")
            buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
            stripe_payment_link = "https://buy.stripe.com/tuo_link_id"
            st.link_button("Offrimi un caffè ☕", buy_me_a_coffee_url, use_container_width=True)
            st.markdown("*(Piattaforma semplice)*"); st.markdown("---")
            st.link_button("Dona con Carta (via Stripe) 💳", stripe_payment_link, use_container_width=True)
            st.markdown("*(Per donazioni con carta)*")

        st.markdown("---")
        st.markdown(" Seguimi su:")
        st.markdown("""<style>...</style><div class="follow-me">...</div>""", unsafe_allow_html=True)

    # --- Contenuto Pagina Principale ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try: st.image(header_image_url)
    except Exception as img_err: st.warning(f"Avviso intestazione: {img_err}", icon="🖼️")

    # --- CONTENUTO SPECIFICO PER PAGINA (Renderizza solo se non è un separatore) ---
    if page not in separator_values:
        if page == "🏠 Home":
            st.title("Benvenuto/a in Salute Mentale AI 🧠❤️")
            st.markdown("""**Salute Mentale AI** è un assistente virtuale progettato per offrirti supporto informativo...""")
            lottie_url_home = "https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json"
            lottie_animation_home = load_lottie_url(lottie_url_home)
            if lottie_animation_home: st_lottie(lottie_animation_home, speed=1, width=400, height=300, key="lottie_home")
            st.markdown("---")
            # --- INSERITE LINEE GUIDA ---
            st.subheader("Linee Guida per l'Utilizzo:")
            st.markdown("""
            *   **Scopo Informativo**: Questa IA fornisce informazioni generali sul benessere mentale. **NON è un sostituto** per diagnosi, terapia o consulenza professionale da parte di medici, psicologi o psicoterapeuti qualificati. Le informazioni potrebbero non essere sempre accurate, complete o aggiornate.
            *   **Condotta Rispettosa**: Interagisci con l'assistente e, se applicabile in futuro, con altri utenti in modo rispettoso. Non sono tollerati linguaggio offensivo, molestie o discorsi d'odio.
            *   **Privacy e Dati**: Le tue conversazioni con l'IA vengono elaborate dall'API di Google Gemini. Non inserire informazioni estremamente sensibili o personali che non desideri vengano processate esternamente. Consulta la nostra Informativa Privacy per maggiori dettagli su come gestiamo i dati.
            *   **Emergenze**: Questa applicazione **NON è progettata per gestire crisi o emergenze**. Se stai vivendo un'emergenza di salute mentale, contatta i servizi di emergenza (es. 112) o una linea di supporto dedicata.
            *   **Uso Responsabile**: Usa le informazioni fornite come punto di partenza per la tua ricerca o come spunto di riflessione. **Prendi decisioni riguardanti la tua salute mentale e fisica solo dopo aver consultato un professionista sanitario qualificato.**
            *   **Feedback**: Il tuo feedback è importante per migliorare l'applicazione.
            """)

        elif page == "🧠 Coach del Benessere":
            st.header("🧠 Coach Virtuale del Benessere")
            lottie_url_coach = "https://lottie.host/0c079fc2-f4df-452a-966b-3a852ffb9801/WjOxpGVduu.json"
            lottie_animation_coach = load_lottie_url(lottie_url_coach)
            if lottie_animation_coach: st_lottie(lottie_animation_coach, speed=1, width=220, height=300, key="lottie_coach")
            st.warning("SoulCare AI può fornire risposte imprecise...")
            # Chat
            if "chat_history_wellness" not in st.session_state: st.session_state.chat_history_wellness = []
            for message in st.session_state.chat_history_wellness:
                with st.chat_message(message["role"], avatar= "❤️" if message["role"]=="assistant" else "user"): st.markdown(message["content"])
            user_prompt = st.chat_input("Scrivi qui...")
            if user_prompt:
                st.chat_message("user").markdown(user_prompt)
                st.session_state.chat_history_wellness.append({"role": "user", "content": user_prompt})
                with st.spinner("..."):
                    # (Passa prompt, non system prompt, alla funzione helper)
                    context = user_prompt
                    response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, context)
                    with st.chat_message("assistant", avatar="❤️"): st.markdown(response_text)
                    st.session_state.chat_history_wellness.append({"role": "assistant", "content": response_text})
                    # Suggerimenti Video
                    topic_for_youtube = extract_topic(user_prompt)
                    video_suggestions = fetch_youtube_videos(topic_for_youtube)
                    if video_suggestions:
                        st.markdown("---")
                        st.markdown("### Risorse Video:")
                        for video in video_suggestions: st.markdown(f"- [{video['title']}]({video['url']})")

        elif page == "📝 Analisi Referto Medico":
            st.header("📝 Analisi Referto Medico")
            # ... (caricamento PDF e analisi, usa generate_gemini_response con SYSTEM_PROMPT_REPORT) ...
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
                            with st.spinner("Analisi..."):
                                analisi_output = generate_gemini_response(SYSTEM_PROMPT_REPORT, f"--- TESTO ---\n{text}\n--- FINE ---")
                                st.subheader("Risultato Analisi:")
                                st.markdown(analisi_output)
                                if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"analisi_referto_{uploaded_file.name[:20]}")
                        else: st.error("...")
                except Exception as e: st.error(f"Errore PDF: {e}")

        elif page == "💊 Info Farmaci":
            st.header("💊 Info Farmaci")
            # ... (Input farmaco e analisi, usa generate_gemini_response con SYSTEM_PROMPT_DRUG) ...
            st.markdown("**Inserisci il nome del farmaco o carica PDF.**")
            input_method = st.radio("Metodo:", ("Testo", "Carica PDF"), horizontal=True, label_visibility="collapsed", key="drug_input_method")
            if input_method == "Testo":
                medicine_name = st.text_input("Nome farmaco:", placeholder="...", key="drug_name_text")
                if st.button("Cerca Info", type="primary", key="search_drug_text_btn") and medicine_name:
                    with st.spinner(f"Ricerca {medicine_name}..."):
                        analisi_output = generate_gemini_response(SYSTEM_PROMPT_DRUG, f"Farmaco: {medicine_name}")
                        st.subheader(f"Info su {medicine_name}:")
                        st.markdown(analisi_output)
                        if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"info_{medicine_name.replace(' ','_')}")
            elif st.button("Cerca Info", type="primary", key="search_drug_text_btn_empty") and not medicine_name: st.warning("...")
        elif input_method == "Carica PDF":
             uploaded_file_drug = st.file_uploader("Scegli PDF", type=["pdf"], key="pdf_drug_uploader", label_visibility="collapsed")
             if uploaded_file_drug is not None:
                try:
                    pdf_bytes_drug = uploaded_file_drug.getvalue()
                    text_drug = extract_text_from_pdf(pdf_bytes_drug)
                    if text_drug:
                        st.text_area("Testo Estratto:", text_drug, height=200)
                        st.markdown("---")
                        medicine_from_pdf = st.text_input("Nome farmaco:", key="drug_name_pdf")
                        if st.button("Analizza da PDF", type="primary", key="search_drug_pdf_btn") and medicine_from_pdf:
                            with st.spinner(f"Analisi {medicine_from_pdf}..."):
                                context_pdf = f"Farmaco: {medicine_from_pdf}\nContesto:\n{text_drug[:1000]}..."
                                analisi_output = generate_gemini_response(SYSTEM_PROMPT_DRUG, context_pdf)
                                st.subheader(f"Info su {medicine_from_pdf}:")
                                st.markdown(analisi_output)
                                if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"info_{medicine_from_pdf.replace(' ','_')}_pdf")
                        elif st.button("Analizza da PDF", type="primary", key="search_drug_pdf_btn_empty") and not medicine_from_pdf: st.warning("...")
                    else: st.error("...")
                except Exception as e: st.error(f"Errore PDF: {e}")

        elif page == "🧑‍⚕️ Chiedi a un Esperto":
            st.header("🧑‍⚕️ Contatta un Esperto")
            st.markdown(""" ... Compila il modulo Google qui sotto...""")
            google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
            st.link_button("📝 Apri il Modulo di Contatto Sicuro", google_form_url, use_container_width=True, type="primary")
            st.markdown("---")
            st.markdown(".. Esperti: ..") # Come prima

        elif page == "⚖️ Informativa Privacy":
            st.header("⚖️ Informativa sulla Privacy")
            st.markdown("""**Informativa...**""")

        elif page == "🫂 Sostienici":
            st.header("🫂 Sostienici")
            st.info("Grazie per considerare di supportare... Le donazioni tramite la barra laterale.")
            st.write("Per supporto, contattaci...")

    # --- AGGIUNTA: Codice per gestione del rendering delle app esterne ---
    elif page == "☢️ App Analisi Radiografie":
        st.markdown("### Apri l'App per l'Analisi Radiografie")
        radiografie_url = "https://assistente-ai-per-radiografie.streamlit.app/"
        st.link_button("Apri App Analisi Radiografie ☢️", radiografie_url, use_container_width=True, type="primary")

    elif page == "🩸 App Analisi Sangue":
        st.markdown("### Apri l'App per l'Analisi del Sangue")
        sangue_url = "https://valutazione-preliminare-del-test-del-sangue.streamlit.app/"
        st.link_button("Apri App Analisi Sangue 🩸", sangue_url, use_container_width=True, type="primary")


# --- Chiamata finale ---
if __name__ == "__main__":
    main()
