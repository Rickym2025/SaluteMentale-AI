# -*- coding: utf-8 -*-

# ==================================================
# IMPORT NECESSARI - DEVONO STARE ALL'INIZIO DEL FILE
# ==================================================
import streamlit as st
from PIL import Image
import base64
import os
import requests
# from urllib.parse import urlparse # Non sembra usato
from streamlit_lottie import st_lottie
import streamlit.components.v1 as components
from google.generativeai import configure, GenerativeModel
import fitz  # PyMuPDF
import re
import pandas as pd # Non sembra usato, ma lo lascio per ora
from io import BytesIO
import time
from google.api_core import exceptions

# ==================================================
# CONFIGURAZIONE MODELLO E API KEYS (DA STREAMLIT SECRETS)
# ==================================================
try:
    # --- CORREZIONE CHIAVE GEMINI ---
    # Cerca la chiave con il nome esatto definito nei segreti
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

    # Assicurati che anche la chiave YouTube sia definita nei segreti
    # con il nome 'youtube_api_key' (tutto minuscolo)
    YOUTUBE_API_KEY = st.secrets["youtube_api_key"]

    # Configura Google Generative AI
    configure(api_key=GEMINI_API_KEY)

except KeyError as e:
    st.error(f"Errore: Chiave API '{e.args[0]}' mancante nei segreti di Streamlit. Vai su 'Manage app' -> 'Settings' -> 'Secrets' per aggiungerla.")
    st.error("Assicurati di aver definito sia 'GEMINI_API_KEY' sia 'youtube_api_key'.")
    st.stop()
except Exception as e:
    st.error(f"Errore nella configurazione iniziale: {e}")
    st.stop()

# Creazione istanza modello Gemini
MODEL_NAME = 'gemini-1.5-flash'
# (Prompt di sistema invariati - assicurati chiedano ITALIANO)
SYSTEM_PROMPT_MENTAL_HEALTH = """Sei "SoulCare AI", un assistente virtuale focalizzato sul benessere mentale. **Rispondi sempre e solo in ITALIANO.** Il tuo obiettivo è fornire supporto informativo, psicoeducazione generale e suggerimenti per il benessere, basandoti sulle domande dell'utente. **NON SEI UN TERAPEUTA E NON PUOI FORNIRE DIAGNOSI O CONSULENZE MEDICHE.** Quando rispondi: - Usa un tono empatico, calmo e di supporto. - Fornisci informazioni generali e basate su concetti noti di psicologia e benessere mentale. - Suggerisci strategie di coping generali (es. tecniche di rilassamento, mindfulness, importanza del sonno e dell'attività fisica). - Incoraggia l'utente a cercare supporto professionale qualificato (psicologo, psicoterapeuta, medico) per problemi specifici o persistenti. - **Includi sempre alla fine un disclaimer chiaro**: "Ricorda, questa è un'interazione con un'IA e non sostituisce il parere di un professionista della salute mentale. Se stai attraversando un momento difficile, considera di parlarne con un medico, uno psicologo o uno psicoterapeuta." """
SYSTEM_PROMPT_REPORT = """Analizza il seguente testo estratto da un referto medico. **Rispondi sempre e solo in ITALIANO.** Fornisci un riassunto conciso dei punti principali o dei risultati menzionati. **NON FARE INTERPRETAZIONI MEDICHE O DIAGNOSI.** Limita l'analisi a quanto scritto nel testo. Alla fine, ricorda all'utente: "Questa è un'analisi automatica del testo fornito e non sostituisce l'interpretazione di un medico. Discuti sempre il referto completo con il tuo medico curante." """
SYSTEM_PROMPT_DRUG = """Fornisci informazioni generali sul farmaco menzionato o descritto nel testo. **Rispondi sempre e solo in ITALIANO.** Includi (se trovi informazioni): indicazioni d'uso generali, meccanismo d'azione di base, effetti collaterali comuni e principali avvertenze. **NON FORNIRE CONSIGLI SUL DOSAGGIO O SULL'USO SPECIFICO.** Enfatizza che queste sono informazioni generali e **NON sostituiscono il foglietto illustrativo o il parere del medico/farmacista.** Concludi con: "Consulta sempre il tuo medico o farmacista prima di assumere qualsiasi farmaco e leggi attentamente il foglietto illustrativo." """

try:
    SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    GENERATION_CONFIG = {
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 4096,
    }
    # Istanzia modello *senza* system prompt globale, lo passeremo per task
    model = GenerativeModel(MODEL_NAME, safety_settings=SAFETY_SETTINGS, generation_config=GENERATION_CONFIG)
except Exception as e:
    st.error(f"Errore nella creazione del modello GenerativeModel: {e}")
    st.stop()


# ==================================================
# FUNZIONI HELPER
# (Incolla qui le definizioni complete delle tue funzioni helper:
# download_generated_report, load_lottie_url, extract_text_from_pdf,
# extract_topic, fetch_youtube_videos)
# ==================================================
def download_generated_report(content, filename, format='txt'):
    try:
        output_bytes = content.encode('utf-8')
        b64 = base64.b64encode(output_bytes).decode()
        href = f'<a href="data:file/txt;base64,{b64}" download="{filename}.txt">Scarica Report (TXT)</a>'
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Errore creazione link download: {e}")

def load_lottie_url(url: str):
     try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
     except requests.exceptions.RequestException: return None
     except Exception: return None

def extract_text_from_pdf(file_bytes):
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            text = "".join(page.get_text() for page in doc)
            if not text.strip(): st.warning("Il PDF sembra vuoto o non contiene testo estraibile.")
            return text
    except Exception as e:
        st.error(f"Errore estrazione testo da PDF: {e}")
        return None

def extract_topic(prompt):
    start_phrases = ["@codex", "codex", "@SoulCare", "soulcare"]
    lower_prompt = prompt.lower()
    for phrase in start_phrases:
        if lower_prompt.startswith(phrase):
            prompt = prompt[len(phrase):].strip()
            break
    return prompt.strip()

def fetch_youtube_videos(query):
    if not YOUTUBE_API_KEY: return [] # Silenzioso se manca chiave
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

# Funzione helper generica per chiamare l'API con re-tentativi e system prompt
def generate_gemini_response(system_prompt, user_content):
    """
    Chiama l'API Gemini con un prompt di sistema e contenuto utente.
    Gestisce errori e tentativi.
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Passiamo il system prompt qui, sovrascrivendo quello globale se presente
            response = model.generate_content(
                f"{system_prompt}\n\n{user_content}",
                # Se passi una history, la struttura è diversa:
                # model.start_chat(history=...).send_message(user_content)
                # ma per ora usiamo generate_content con prompt combinato
            )

            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason
                st.error(f"L'analisi è stata bloccata dall'IA (Motivo: {reason}).")
                return f"Errore: Bloccato dal sistema ({reason})."
            if hasattr(response, 'text') and response.text:
                disclaimer_app = "\n\n---\n**⚠️⚠️ DISCLAIMER FINALE (DA APP) ⚠️⚠️**\n*Ricorda ancora una volta: questa analisi, per quanto dettagliata, è **AUTOMATICA**, **NON PERSONALIZZATA** e **NON SOSTITUISCE IL MEDICO/PROFESSIONISTA**. Errori, omissioni o interpretazioni imprecise sono possibili. **Consulta SEMPRE il tuo medico o un professionista qualificato** per una valutazione corretta e completa.*"
                return response.text.strip() + disclaimer_app
            else:
                st.warning(f"Risposta inattesa o vuota dall'IA (Tentativo {attempt + 1}).")
                if attempt == max_retries - 1: return "Errore: Risposta vuota dall'IA."
                time.sleep(2)

        except exceptions.GoogleAPIError as e:
            st.warning(f"Errore API Google (Tentativo {attempt + 1}): {str(e)}")
            if "quota" in str(e).lower(): return "Errore: Quota API superata."
            if attempt < max_retries - 1: time.sleep(2)
            else: return "Errore: Impossibile contattare l'IA dopo vari tentativi."
        except Exception as e:
            st.error(f"Errore imprevisto durante l'analisi AI: {str(e)}")
            return f"Errore: Analisi fallita ({type(e).__name__})."

    # Se esce dal loop
    return "Errore: Analisi fallita dopo multipli tentativi."


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
        st.markdown("""<style>...</style><div class="follow-me">...</div>""", unsafe_allow_html=True) # Assicurati che l'HTML sia corretto qui

        if page == "🫂 Sostienici":
            st.markdown("### Sostieni SoulCare AI")
            st.markdown("Se trovi utile questa applicazione, considera di supportare il suo sviluppo con una donazione:")
            # SOSTITUISCI CON I TUOI LINK REALI
            buy_me_a_coffee_url = "https://www.buymeacoffee.com/tuonomeutente"
            stripe_payment_link = "https://buy.stripe.com/tuo_link_id"
            st.link_button("Offrimi un caffè ☕", buy_me_a_coffee_url, use_container_width=True)
            st.markdown("*(Piattaforma semplice per piccole donazioni)*")
            st.markdown("---")
            st.link_button("Dona con Carta (via Stripe) 💳", stripe_payment_link, use_container_width=True)
            st.markdown("*(Per donazioni tramite carta di credito/debito)*")

    # --- Contenuto Pagina Principale ---

    # --- IMMAGINE DI INTESTAZIONE ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try:
        st.image(header_image_url)
    except Exception as img_err:
        st.warning(f"Avviso: Impossibile caricare l'immagine di intestazione. ({img_err})", icon="🖼️")

    # --- CONTENUTO SPECIFICO PER PAGINA ---

    if page == "🏠 Home":
        st.title("Benvenuto/a in SoulCare AI 🧑‍⚕️❤️")
        st.markdown("""**SoulCare AI** è un'applicazione...""") # Testo come prima
        lottie_url_home = "https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json"
        lottie_animation_home = load_lottie_url(lottie_url_home)
        if lottie_animation_home: st_lottie(lottie_animation_home, speed=1, width=400, height=300, key="lottie_home")
        st.markdown("""**Linee Guida per l'Utilizzo:**...""") # Testo come prima

    elif page == "🧠 Coach del Benessere":
        st.header("🧠 Coach Virtuale del Benessere")
        lottie_url_coach = "https://lottie.host/0c079fc2-f4df-452a-966b-3a852ffb9801/WjOxpGVduu.json"
        lottie_animation_coach = load_lottie_url(lottie_url_coach)
        if lottie_animation_coach: st_lottie(lottie_animation_coach, speed=1, width=220, height=300, key="lottie_coach")
        st.warning("SoulCare AI può fornire risposte imprecise...") # Avviso come prima

        if "chat_history_wellness" not in st.session_state: st.session_state.chat_history_wellness = []
        for message in st.session_state.chat_history_wellness:
            with st.chat_message(message["role"], avatar= "❤️" if message["role"]=="assistant" else "user"): st.markdown(message["content"])

        user_prompt = st.chat_input("Scrivi qui la tua domanda o riflessione...")
        if user_prompt:
            st.chat_message("user").markdown(user_prompt)
            st.session_state.chat_history_wellness.append({"role": "user", "content": user_prompt})
            with st.spinner("SoulCare AI sta pensando... 🤔"):
                # Prepara il contesto per la funzione helper
                # Si potrebbe ottimizzare passando solo gli ultimi messaggi
                context = f"Storico:\n{st.session_state.chat_history_wellness[:-1]}\n\nDomanda:\n{user_prompt}"
                response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, context)
                with st.chat_message("assistant", avatar="❤️"): st.markdown(response_text)
                st.session_state.chat_history_wellness.append({"role": "assistant", "content": response_text})
                # Suggerimenti Video
                topic_for_youtube = extract_topic(user_prompt)
                video_suggestions = fetch_youtube_videos(topic_for_youtube)
                if video_suggestions:
                    st.markdown("---")
                    st.markdown("### Risorse Video Correlate (YouTube):")
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
                    st.text_area("Testo Estratto dal PDF:", text, height=300)
                    st.markdown("---")
                    if st.button("🔬 Analizza Testo del Referto", type="primary", key="analyze_report_btn"):
                        with st.spinner("Analisi del referto in corso..."):
                            # Usa la funzione helper
                            analisi_output = generate_gemini_response(SYSTEM_PROMPT_REPORT, f"--- TESTO REFERTO ---\n{text}\n--- FINE REFERTO ---")
                            st.subheader("Risultato Analisi:")
                            st.markdown(analisi_output)
                            # Offri download solo se l'analisi non è un errore
                            if not analisi_output.startswith("Errore:"):
                                download_generated_report(analisi_output, f"analisi_referto_{uploaded_file.name[:20]}")
                else: st.error("Impossibile estrarre testo dal PDF caricato.")
            except Exception as e: st.error(f"Errore durante l'elaborazione del PDF: {e}")

    elif page == "💊 Info Farmaci":
        st.header("💊 Informazioni Generali sui Farmaci")
        st.markdown("**Inserisci il nome del farmaco o carica un PDF che lo menziona.**")
        input_method = st.radio("Metodo input:", ("Testo", "Carica PDF"), horizontal=True, label_visibility="collapsed", key="drug_input_method")
        if input_method == "Testo":
            medicine_name = st.text_input("Nome del farmaco:", placeholder="Es. Paracetamolo", key="drug_name_text")
            if st.button("Cerca Info Farmaco", type="primary", key="search_drug_text_btn") and medicine_name:
                with st.spinner(f"Ricerca informazioni per {medicine_name}..."):
                    analisi_output = generate_gemini_response(SYSTEM_PROMPT_DRUG, f"Farmaco: {medicine_name}")
                    st.subheader(f"Informazioni su {medicine_name}:")
                    st.markdown(analisi_output)
                    if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"info_{medicine_name.replace(' ','_')}")
            elif st.button("Cerca Info Farmaco", type="primary", key="search_drug_text_btn_empty") and not medicine_name: st.warning("Inserisci un nome.") # Key diversa per evitare conflitto
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
                        if st.button("Analizza Farmaco dal PDF", type="primary", key="search_drug_pdf_btn") and medicine_from_pdf:
                            with st.spinner(f"Analisi info per {medicine_from_pdf}..."):
                                context_pdf = f"Farmaco da analizzare: {medicine_from_pdf}\n\nContesto PDF:\n{text_drug[:1000]}..."
                                analisi_output = generate_gemini_response(SYSTEM_PROMPT_DRUG, context_pdf)
                                st.subheader(f"Info su {medicine_from_pdf} (dal PDF):")
                                st.markdown(analisi_output)
                                if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"info_{medicine_from_pdf.replace(' ','_')}_pdf")
                        elif st.button("Analizza Farmaco dal PDF", type="primary", key="search_drug_pdf_btn_empty") and not medicine_from_pdf: st.warning("Inserisci nome.") # Key diversa
                    else: st.error("Impossibile estrarre testo dal PDF.")
                except Exception as e: st.error(f"Errore elaborazione PDF: {e}")

    elif page == "🧑‍⚕️ Chiedi a un Esperto":
        st.header("🧑‍⚕️ Contatta un Esperto")
        st.markdown("""Hai bisogno di un parere più specifico o vuoi metterti in contatto?\nCompila il modulo Google qui sotto. La tua richiesta verrà inoltrata in modo confidenziale.\n\n*Ricorda: questo modulo è per richieste **non urgenti**. Per emergenze, contatta i servizi sanitari.*""")
        # --- SOSTITUISCI CON IL TUO LINK REALE ---
        google_form_url = "https://docs.google.com/forms/d/e/TUO_CODICE_FORM/viewform?usp=sf_link"
        st.link_button("📝 Apri il Modulo di Contatto Sicuro", google_form_url, use_container_width=True, type="primary")
        st.markdown("---")
        st.markdown("""**Esperti Disponibili (Esempio):**\n- Dott.ssa Anjali Sharma (Psicologa)...""") # Come prima

    elif page == "⚖️ Informativa Privacy":
        st.header("⚖️ Informativa sulla Privacy")
        # --- INSERISCI QUI IL TESTO COMPLETO DELLA TUA INFORMATIVA PRIVACY TRADOTTA ---
        st.markdown("""**Informativa sulla Privacy di SoulCare AI**: ... (Testo completo come prima, con la tua email)""")

    elif page == "🫂 Sostienici":
        st.header("🫂 Sostienici")
        st.info("Grazie per considerare di supportare SoulCare AI! Trovi le opzioni per la donazione nella barra laterale a sinistra.")
        st.write("Per richieste di supporto tecnico o feedback, contattaci a skavtech.in@gmail.com")


# --- Chiamata finale ---
if __name__ == "__main__":
    main()
