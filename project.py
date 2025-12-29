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
# CONFIGURAZIONE PAGINA (DEVE ESSERE LA PRIMA ISTRUZIONE)
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
    # Gemini API Key
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        st.error("❌ Errore: Chiave 'GEMINI_API_KEY' mancante nei Secrets.")
        st.stop()
    
    # YouTube API Key (Opzionale, non blocca l'app se manca)
    YOUTUBE_API_KEY = st.secrets.get("youtube_api_key")

    genai.configure(api_key=GEMINI_API_KEY)

except Exception as e:
    st.error(f"Errore nella configurazione iniziale: {e}")
    st.stop()

# Nome del modello (Versione 2025 Free Tier)
MODEL_NAME = 'gemini-1.5-flash'

# ==================================================
# PROMPT DI SISTEMA (RICOSTRUITI E COMPLETI)
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

# Configurazione Sicurezza e Generazione
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

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    safety_settings=SAFETY_SETTINGS,
    generation_config=GENERATION_CONFIG
)

# ==================================================
# FUNZIONI HELPER
# ==================================================

def generate_gemini_response(system_prompt, user_content):
    """Chiama l'API Gemini con gestione errori avanzata per debug."""
    max_retries = 2
    last_error = "Nessun dettaglio disponibile."
    
    # Combina prompt di sistema e input utente
    full_prompt = f"{system_prompt}\n\n---\nRICHIESTA UTENTE:\n{user_content}"
    
    for attempt in range(max_retries):
        try:
            # Configurazione esplicita per ogni chiamata per evitare conflitti
            model_instance = genai.GenerativeModel(
                model_name=MODEL_NAME,
                safety_settings=SAFETY_SETTINGS,
                generation_config=GENERATION_CONFIG
            )
            
            response = model_instance.generate_content(full_prompt)
            
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
            
            elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                return f"⚠️ Blocco Sicurezza: {response.prompt_feedback.block_reason}"
            
            time.sleep(1)
        
        except exceptions.GoogleAPIError as e:
            last_error = str(e)
            if "quota" in last_error.lower() or "429" in last_error:
                return f"❌ Errore Quota: Hai superato il limite di richieste gratuite per oggi (Error 429). Riprova domani o usa una nuova API Key."
            if "key" in last_error.lower() or "400" in last_error:
                 return f"❌ Errore Chiave: La API Key sembra non valida. Controlla i Secrets. ({last_error})"
            time.sleep(1)
            
        except Exception as e:
            last_error = str(e)
            time.sleep(1)
            
    # Se arriviamo qui, restituiamo l'errore esatto per capire il problema
    return f"❌ Errore Tecnico Gemini: {last_error}"

def download_generated_report(content, filename):
    """Crea un link per scaricare il report."""
    try:
        # Pulisci eventuale disclaimer duplicato se presente
        cleaned_content = content.replace("**⚠️⚠️ DISCLAIMER FINALE (DA APP) ⚠️⚠️**", "")
        b64 = base64.b64encode(cleaned_content.encode('utf-8')).decode()
        href = f'<a href="data:file/txt;base64,{b64}" download="{filename}.txt">📥 Scarica Report (TXT)</a>'
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Errore generazione download: {e}")

def load_lottie_url(url: str):
    """Carica animazione Lottie da URL."""
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200: return None
        return r.json()
    except:
        return None

def extract_text_from_pdf(file_bytes):
    """Estrae testo da PDF usando PyMuPDF (fitz)."""
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
    """Estrae un argomento base per la ricerca YouTube."""
    keywords = prompt.lower()
    # Rimuovi parole comuni
    remove_words = ["ciao", "vorrei", "sapere", "parlami", "di", "cosa", "è", "sono", "come", "posso"]
    for word in remove_words:
        keywords = keywords.replace(word, "")
    return keywords.strip() or "benessere mentale"

def fetch_youtube_videos(query):
    """Cerca video su YouTube se la chiave è presente."""
    if not YOUTUBE_API_KEY:
        return []
    
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{query} benessere psicologia",
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
    except:
        pass # Ignora errori YouTube silenziosamente
    return []

# ==================================================
# MAIN APP
# ==================================================
def main():
    
    # --- URL LINK ---
    buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
    stripe_payment_link = "https://buy.stripe.com/LINK_ID_STRIPE_DA_INSERIRE" # Metti il tuo link vero o commentalo
    google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
    contact_email = "smartai.riccardo@gmail.com"
    radiografie_url = "https://assistente-ai-per-radiografie.streamlit.app/"
    sangue_url = "https://valutazione-preliminare-del-test-del-sangue.streamlit.app/"

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Menu Principale")
        
        # Gestione immagine sidebar (soul.png)
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
        
        page = st.sidebar.selectbox(
            "Navigazione", 
            page_options, 
            index=0,
            label_visibility="collapsed"
        )

        if page == "🫂 Sostienici":
            st.markdown("---")
            st.link_button("☕ Offrimi un caffè", buy_me_a_coffee_url, use_container_width=True)

    # --- Header ---
    header_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try:
        st.image(header_url, use_container_width=True)
    except:
        pass

    # --- LOGICA PAGINE ---

    # 1. HOME
    if page == "🏠 Home":
        st.title("Benvenuto/a in Salute Mentale AI 🧠❤️")
        st.markdown("""
        **Salute Mentale AI** è il tuo assistente virtuale per il benessere psicologico e l'informazione sanitaria di base.
        
        Cosa puoi fare qui?
        *   Conversare con un **Coach del Benessere** empatico.
        *   Ottenere spiegazioni su **Referti Medici**.
        *   Cercare informazioni sui **Farmaci**.
        """)
        
        col_lottie, col_text = st.columns([1, 2])
        with col_lottie:
            lottie_home = load_lottie_url("https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json")
            if lottie_home: st_lottie(lottie_home, height=250, key="home_anim")
        
        with col_text:
            st.info("""
            **⚠️ IMPORTANTE:**
            Questa IA fornisce solo informazioni generali. 
            **NON sostituisce il parere di medici o psicologi.**
            In caso di emergenza, chiama il 112.
            """)

    # 2. COACH BENESSERE
    elif page == "🧠 Coach del Benessere":
        st.header("🧠 Coach Virtuale")
        st.caption("Uno spazio sicuro per riflettere e trovare strategie di coping.")
        
        # Cronologia Chat
        if "chat_history_wellness" not in st.session_state:
            st.session_state.chat_history_wellness = []

        # Mostra messaggi precedenti (limitati all'ultimo scambio per pulizia)
        for msg in st.session_state.chat_history_wellness:
             with st.chat_message(msg["role"], avatar="👤" if msg["role"]=="user" else "🧠"):
                 st.markdown(msg["content"])

        user_input = st.chat_input("Come ti senti oggi? O cosa vorresti chiedere?")
        
        if user_input:
            # 1. Mostra messaggio utente
            st.session_state.chat_history_wellness.append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_input)
            
            # 2. Genera risposta IA
            with st.chat_message("assistant", avatar="🧠"):
                with st.spinner("Sto riflettendo..."):
                    response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, user_input)
                    st.markdown(response_text)
                    st.session_state.chat_history_wellness.append({"role": "assistant", "content": response_text})
                    
                    # 3. Suggerimenti Video (solo se API Key presente)
                    if YOUTUBE_API_KEY:
                        topic = extract_topic(user_input)
                        videos = fetch_youtube_videos(topic)
                        if videos:
                            st.markdown("---")
                            st.markdown("**📺 Video consigliati:**")
                            for v in videos:
                                st.markdown(f"- [{v['title']}]({v['url']})")

    # 3. REFERTO MEDICO
    elif page == "📝 Analisi Referto Medico":
        st.header("📝 Analisi Referto Medico")
        st.warning("Carica un PDF per ottenere una spiegazione semplificata.")
        
        uploaded_pdf = st.file_uploader("Carica referto (PDF)", type=["pdf"])
        
        if uploaded_pdf:
            text = extract_text_from_pdf(uploaded_pdf.getvalue())
            if text:
                st.success("Testo estratto correttamente.")
                if st.button("🔍 Analizza Referto", type="primary"):
                    with st.spinner("Analisi in corso..."):
                        report = generate_gemini_response(SYSTEM_PROMPT_REPORT, text)
                        st.markdown("### Risultato:")
                        st.markdown(report)
                        download_generated_report(report, "analisi_referto")
            else:
                st.error("Impossibile leggere il testo del PDF. Potrebbe essere una scansione (immagine).")

    # 4. INFO FARMACI
    elif page == "💊 Info Farmaci":
        st.header("💊 Info Farmaci")
        
        tab1, tab2 = st.tabs(["Cerca per Nome", "Analizza Foglio Illustrativo (PDF)"])
        
        with tab1:
            drug_name = st.text_input("Nome del farmaco (es. Tachipirina)")
            if st.button("Cerca Info") and drug_name:
                with st.spinner("Ricerca in corso..."):
                    info = generate_gemini_response(SYSTEM_PROMPT_DRUG, f"Parlami del farmaco: {drug_name}")
                    st.markdown(info)
                    download_generated_report(info, f"info_{drug_name}")
        
        with tab2:
            uploaded_drug_pdf = st.file_uploader("Carica foglietto illustrativo", type=["pdf"], key="drug_pdf")
            if uploaded_drug_pdf:
                text_drug = extract_text_from_pdf(uploaded_drug_pdf.getvalue())
                if text_drug and st.button("Analizza PDF"):
                    with st.spinner("Lettura in corso..."):
                        info_pdf = generate_gemini_response(SYSTEM_PROMPT_DRUG, f"Analizza questo testo: {text_drug[:4000]}") # Tronca per sicurezza
                        st.markdown(info_pdf)

    # 5. ESPERTO
    elif page == "🧑‍⚕️ Chiedi a un Esperto":
        st.header("🧑‍⚕️ Contatta un Professionista")
        st.markdown(f"""
        Hai bisogno di supporto specifico?
        
        Utilizza il modulo sottostante per inviare una richiesta. 
        Ti metteremo in contatto con uno dei nostri esperti partner.
        """)
        st.link_button("📝 Vai al Modulo di Contatto", google_form_url, type="primary")

    # 6. APP ESTERNE
    elif page == "☢️ App Analisi Radiografie":
        st.info(f"Vai all'App Radiografie: [Clicca qui]({radiografie_url})")
    elif page == "🩸 App Analisi Sangue":
        st.info(f"Vai all'App Analisi Sangue: [Clicca qui]({sangue_url})")

    # 7. PRIVACY
    elif page == "⚖️ Informativa Privacy":
        st.header("Privacy Policy")
        st.markdown("""
        **In sintesi:**
        1. **Dati AI:** I testi inviati all'IA vengono processati da Google Gemini e non salvati permanentemente da noi.
        2. **Contatti:** Le email inviate tramite modulo sono riservate.
        3. **Cookie:** Usiamo solo cookie tecnici di Streamlit.
        
        Per domande: smartai.riccardo@gmail.com
        """)

    # FOOTER GLOBALE
    st.markdown("---")
    st.caption("© 2025 Salute Mentale AI - Powered by Gemini 1.5 Flash")

if __name__ == "__main__":
    main()

