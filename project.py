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
import google.generativeai as genai
import fitz  # PyMuPDF
import re
import pandas as pd
from io import BytesIO
import time
from google.api_core import exceptions

# ==================================================
# CONFIGURAZIONE PAGINA
# ==================================================
st.set_page_config(
    page_title="Salute Mentale AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================================================
# CONFIGURAZIONE API KEYS E MODELLO
# ==================================================
try:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        st.error("❌ Errore: Chiave 'GEMINI_API_KEY' mancante nei Secrets.")
        st.stop()
    
    YOUTUBE_API_KEY = st.secrets.get("youtube_api_key")

    genai.configure(api_key=GEMINI_API_KEY)

except Exception as e:
    st.error(f"Errore nella configurazione iniziale: {e}")
    st.stop()

# --- MODELLO AGGIORNATO AL 2025 ---
# Basato sulla tua lista: usiamo la versione stabile più recente
MODEL_NAME = 'gemini-2.5-flash' 

# ==================================================
# PROMPT DI SISTEMA
# ==================================================

SYSTEM_PROMPT_MENTAL_HEALTH = """
Sei "Salute Mentale AI", un assistente virtuale empatico, calmo e professionale dedicato al benessere psicologico.
Il tuo obiettivo è fornire supporto informativo, tecniche di rilassamento e spiegazioni chiare su temi di salute mentale.

**LINEE GUIDA:**
1.  **Empatia:** Rispondi sempre con tono accogliente e non giudicante.
2.  **No Diagnosi:** NON fare mai diagnosi mediche o psicologiche. Se l'utente descrive sintomi gravi, suggerisci di consultare un professionista.
3.  **Chiarezza:** Usa un linguaggio semplice e accessibile.
4.  **Sicurezza:** Se l'utente esprime intenti autolesionistici o situazioni di pericolo immediato, fornisci immediatamente il numero di emergenza (112) e consiglia di recarsi al pronto soccorso.
5.  **Lingua:** Rispondi sempre in ITALIANO.
"""

SYSTEM_PROMPT_REPORT = """
Agisci come un assistente medico esperto. Analizza il seguente testo estratto da un referto medico.
**Obiettivo:** Spiegare il contenuto al paziente in termini semplici.

**Struttura della risposta:**
1.  **Sintesi:** Cosa riguarda questo documento?
2.  **Punti Chiave:** Elenca i valori o le osservazioni principali trovate nel testo.
3.  **Spiegazione Semplice:** Traduci i termini tecnici in linguaggio comune.
4.  **Disclaimer:** Ricorda che questa è una lettura automatica e non sostituisce il medico.

**Lingua:** ITALIANO.
"""

SYSTEM_PROMPT_DRUG = """
Fornisci informazioni generali e chiare sul farmaco richiesto o descritto nel testo fornito.
**Struttura della risposta:**
1.  **A cosa serve:** Indicazioni terapeutiche principali.
2.  **Come si usa (Generale):** Modalità di assunzione tipiche (specificando di seguire sempre la ricetta medica).
3.  **Effetti Collaterali Comuni:** Elenco dei possibili effetti indesiderati più frequenti.
4.  **Avvertenze:** Controindicazioni o interazioni importanti.

**IMPORTANTE:** Specifica che queste sono informazioni da foglietto illustrativo e non sostituiscono il parere del medico o del farmacista.
**Lingua:** ITALIANO.
"""

# Configurazione Sicurezza
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]

GENERATION_CONFIG = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 4096,
}

# ==================================================
# FUNZIONI HELPER
# ==================================================

def generate_gemini_response(system_prompt, user_content):
    """Chiama l'API Gemini 2.5."""
    max_retries = 2
    full_prompt = f"{system_prompt}\n\n---\nRICHIESTA UTENTE:\n{user_content}"
    
    for attempt in range(max_retries):
        try:
            # Creiamo l'istanza del modello ogni volta per evitare conflitti
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                safety_settings=SAFETY_SETTINGS,
                generation_config=GENERATION_CONFIG
            )
            
            response = model.generate_content(full_prompt)
            
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
            
            elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                return f"⚠️ Risposta bloccata per sicurezza: {response.prompt_feedback.block_reason}"
            
            time.sleep(1)
        
        except exceptions.GoogleAPIError as e:
            if "quota" in str(e).lower() or "429" in str(e):
                return "❌ Errore: Quota API giornaliera superata."
            if "not found" in str(e).lower() or "404" in str(e):
                return f"❌ Errore Modello: Il modello {MODEL_NAME} non è stato trovato. Controlla il nome."
            time.sleep(2)
        except Exception as e:
            return f"❌ Errore imprevisto: {str(e)}"
            
    return "❌ Il servizio non risponde al momento. Riprova più tardi."

def download_generated_report(content, filename):
    try:
        cleaned_content = content.replace("**⚠️⚠️ DISCLAIMER FINALE (DA APP) ⚠️⚠️**", "")
        b64 = base64.b64encode(cleaned_content.encode('utf-8')).decode()
        href = f'<a href="data:file/txt;base64,{b64}" download="{filename}.txt">📥 Scarica Report (TXT)</a>'
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Errore generazione download: {e}")

def load_lottie_url(url: str):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200: return None
        return r.json()
    except:
        return None

def extract_text_from_pdf(file_bytes):
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
            return text if text.strip() else None
    except Exception as e:
        st.error(f"Errore lettura PDF: {e}")
        return None

def extract_topic(prompt):
    keywords = prompt.lower()
    remove_words = ["ciao", "vorrei", "sapere", "parlami", "di", "cosa", "è", "sono", "come", "posso", "aiuto", "sto", "male"]
    for word in remove_words:
        keywords = keywords.replace(word, "")
    return keywords.strip() or "benessere mentale"

def fetch_youtube_videos(query):
    if not YOUTUBE_API_KEY: return []
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{query} psicologia benessere",
        "type": "video",
        "maxResults": 3,
        "relevanceLanguage": "it",
        "key": YOUTUBE_API_KEY
    }
    try:
        response = requests.get(search_url, params=params, timeout=5)
        if response.status_code == 200:
            results = response.json().get("items", [])
            videos = []
            for item in results:
                vid = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if vid and snippet:
                    videos.append({
                        "title": snippet.get("title"),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "id": vid
                    })
            return videos
    except: pass
    return []

# ==================================================
# MAIN APP
# ==================================================
def main():
    
    # --- LINKS ---
    buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
    google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
    contact_email = "smartai.riccardo@gmail.com"
    
    # ⚠️ INCOLLA QUI I LINK CHE HAI RECUPERATO DALLE TUE APP ⚠️
    radiografie_url = "https://assistente-ai-per-radiografie.streamlit.app/"
    sangue_url = "https://valutazione-preliminare-del-test-del-sangue.streamlit.app/"

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Menu Principale")
        if os.path.exists("soul.png"):
            st.image("soul.png", width=100)
        
        page_options = [
            "🏠 Home", 
            "🧠 Coach del Benessere", 
            "📝 Analisi Referto Medico", 
            "💊 Info Farmaci",
            "🧑‍⚕️ Chiedi a un Esperto", 
            "--- Strumenti Correlati ---", 
            "☢️ App Analisi Radiografie",
            "🩸 App Analisi Sangue", 
            "--- Info e Supporto ---", 
            "⚖️ Informativa Privacy", 
            "🫂 Sostienici"
        ]
        
        page = st.sidebar.selectbox("Navigazione", page_options, label_visibility="collapsed")
        
        if page == "🫂 Sostienici":
            st.markdown("---")
            st.link_button("☕ Offrimi un caffè", buy_me_a_coffee_url, use_container_width=True)

    # --- Header ---
    header_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try: st.image(header_url, use_container_width=True)
    except: pass

    # --- LOGICA PAGINE ---

    if page == "🏠 Home":
        st.title("Benvenuto/a in Salute Mentale AI 🧠❤️")
        st.markdown("""
        **Salute Mentale AI** è il tuo assistente virtuale per il benessere psicologico e l'informazione sanitaria di base.
        Sfruttiamo la tecnologia **Gemini 2.5** per offrirti supporto avanzato.
        """)
        col_lottie, col_text = st.columns([1, 2])
        with col_lottie:
            lottie_home = load_lottie_url("https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json")
            if lottie_home: st_lottie(lottie_home, height=250, key="home_anim")
        with col_text:
            st.info("⚠️ Questa IA fornisce solo informazioni generali. NON sostituisce il parere di medici o psicologi. In caso di emergenza, chiama il 112.")

    elif page == "🧠 Coach del Benessere":
        st.header("🧠 Coach Virtuale")
        st.caption("Uno spazio sicuro per riflettere.")
        
        if "chat_history_wellness" not in st.session_state:
            st.session_state.chat_history_wellness = []

        for msg in st.session_state.chat_history_wellness:
             with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🧠"):
                 st.markdown(msg["content"])

        user_input = st.chat_input("Come ti senti oggi?")
        
        if user_input:
            st.session_state.chat_history_wellness.append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="👤"): st.markdown(user_input)
            
            with st.chat_message("assistant", avatar="🧠"):
                with st.spinner("Sto riflettendo..."):
                    response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, user_input)
                    st.markdown(response_text)
                    st.session_state.chat_history_wellness.append({"role": "assistant", "content": response_text})
                    
                    if YOUTUBE_API_KEY:
                        topic = extract_topic(user_input)
                        videos = fetch_youtube_videos(topic)
                        if videos:
                            st.markdown("---")
                            st.markdown("**📺 Video consigliati:**")
                            for v in videos: st.markdown(f"- [{v['title']}]({v['url']})")

    elif page == "📝 Analisi Referto Medico":
        st.header("📝 Analisi Referto Medico")
        uploaded_pdf = st.file_uploader("Carica referto (PDF)", type=["pdf"])
        if uploaded_pdf:
            text = extract_text_from_pdf(uploaded_pdf.getvalue())
            if text:
                st.success("Testo estratto.")
                if st.button("🔍 Analizza Referto", type="primary"):
                    with st.spinner("Analisi Gemini 2.5 in corso..."):
                        report = generate_gemini_response(SYSTEM_PROMPT_REPORT, text)
                        st.markdown(report)
                        download_generated_report(report, "analisi_referto")
            else: st.error("PDF vuoto o illeggibile.")

    elif page == "💊 Info Farmaci":
        st.header("💊 Info Farmaci")
        tab1, tab2 = st.tabs(["Cerca Nome", "Analizza PDF"])
        with tab1:
            drug_name = st.text_input("Nome farmaco")
            if st.button("Cerca") and drug_name:
                with st.spinner("Ricerca..."):
                    info = generate_gemini_response(SYSTEM_PROMPT_DRUG, f"Farmaco: {drug_name}")
                    st.markdown(info)
        with tab2:
            uploaded_drug_pdf = st.file_uploader("Foglietto illustrativo (PDF)", type=["pdf"])
            if uploaded_drug_pdf and st.button("Analizza PDF"):
                 text_drug = extract_text_from_pdf(uploaded_drug_pdf.getvalue())
                 if text_drug:
                     with st.spinner("Analisi..."):
                         info_pdf = generate_gemini_response(SYSTEM_PROMPT_DRUG, text_drug[:5000])
                         st.markdown(info_pdf)

    elif page == "🧑‍⚕️ Chiedi a un Esperto":
        st.header("🧑‍⚕️ Contatta un Professionista")
        st.markdown("Utilizza il modulo per inviare una richiesta.")
        st.link_button("📝 Vai al Modulo di Contatto", google_form_url, type="primary")

    elif page == "☢️ App Analisi Radiografie":
        st.info(f"Vai all'App Radiografie: [Clicca qui]({radiografie_url})")
        
    elif page == "🩸 App Analisi Sangue":
        st.info(f"Vai all'App Analisi Sangue: [Clicca qui]({sangue_url})")

    elif page == "⚖️ Informativa Privacy":
        st.header("Privacy Policy")
        st.markdown("Dati processati da Google Gemini. Nessuna archiviazione permanente dei messaggi.")

    st.markdown("---")
    st.caption("© 2025 Salute Mentale AI - Powered by Gemini 2.5 Flash")

if __name__ == "__main__":
    main()
