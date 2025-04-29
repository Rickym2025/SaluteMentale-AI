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
    # Modello base senza system prompt globale, lo passiamo per task
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
    if not YOUTUBE_API_KEY: return []
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
    except Exception as e: st.error(f"Errore ricerca YT: {e}")
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
    st.set_page_config(page_title="Salute Mentale AI", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

    # URL per donazioni e contatto (SOSTITUISCI CON I TUOI LINK REALI)
    buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
    stripe_payment_link = "https://buy.stripe.com/tuo_link_id"
    google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
    # SOSTITUISCI CON LA TUA EMAIL REALE PER LA POLICY
    contact_email = "[LA TUA EMAIL DI CONTATTO]"

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Menu Principale")
        page_options = ["🏠 Home", "🧠 Coach del Benessere", "📝 Analisi Referto Medico", "💊 Info Farmaci",
                         "🧑‍⚕️ Chiedi a un Esperto", "--- Strumenti Correlati ---", "☢️ App Analisi Radiografie",
                         "🩸 App Analisi Sangue", "--- Info e Supporto ---", "⚖️ Informativa Privacy", "🫂 Sostienici"]
        separator_values = ["--- Strumenti Correlati ---", "--- Info e Supporto ---"]
        def format_func(option): return "---" if option in separator_values else option
        page = st.sidebar.selectbox("**MENU**", page_options, label_visibility="collapsed", format_func=format_func)

        if page == "🫂 Sostienici":
            st.markdown("### Sostieni Salute Mentale AI")
            st.markdown("...") # Testo sidebar
            st.link_button("Offrimi un caffè ☕", buy_me_a_coffee_url, use_container_width=True)
            st.markdown("...") # Testo sidebar
            st.link_button("Dona con Carta (via Stripe) 💳", stripe_payment_link, use_container_width=True)
            st.markdown("...") # Testo sidebar

        st.markdown("---"); st.markdown(" Seguimi su:")
        st.markdown("""<style>...</style><div class="follow-me">...</div>""", unsafe_allow_html=True) # Tuo HTML

    # --- Contenuto Pagina Principale ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try: st.image(header_image_url)
    except Exception: st.warning("Avviso: Impossibile caricare immagine intestazione.", icon="🖼️")

    # --- CONTENUTO SPECIFICO PER PAGINA ---
    if page not in separator_values:
        if page == "🏠 Home":
            st.title("Benvenuto/a in Salute Mentale AI 🧠❤️")
            st.markdown("""**Salute Mentale AI** è un assistente virtuale...""")
            lottie_url_home = "https://lottie.host/d7233830-b2c0-4719-a5c0-0389bd2ab539/qHF7qyXl5q.json"
            lottie_animation_home = load_lottie_url(lottie_url_home)
            if lottie_animation_home: st_lottie(lottie_animation_home, speed=1, width=400, height=300, key="lottie_home")
            st.markdown("---")
            # --- LINEE GUIDA COMPILATE ---
            st.subheader("Linee Guida per l'Utilizzo:")
            st.markdown(f"""
            *   **Scopo Informativo**: Questa IA fornisce informazioni e spunti generali sul benessere mentale. **Non è un sostituto** per diagnosi, terapie o consulenze professionali fornite da medici, psicologi o psicoterapeuti. Le informazioni generate dall'IA potrebbero non essere sempre accurate, complete o aggiornate.
            *   **Condotta Rispettosa**: Ti preghiamo di interagire con l'assistente virtuale in modo costruttivo e rispettoso. Qualsiasi forma di abuso, linguaggio offensivo o inappropriato non è tollerata.
            *   **Privacy e Dati**: Le tue interazioni testuali vengono inviate ai server di Google per essere processate dall'API Gemini. Non inserire dati personali altamente sensibili (es. numeri di telefono, indirizzi, dati finanziari specifici) nelle tue domande. Per richieste di contatto o supporto, utilizza il modulo Google dedicato. Consulta la nostra Informativa Privacy completa (disponibile nel menu) per maggiori dettagli.
            *   **Emergenze**: Questa applicazione **NON può gestire situazioni di crisi o emergenze mediche/psicologiche**. Se stai vivendo un'emergenza o hai pensieri urgenti di farti del male o farne ad altri, contatta immediatamente i servizi di emergenza locali (Numero Unico Emergenze 112) o una linea di supporto telefonico specializzata (es. Telefono Amico Italia 02 2327 2327).
            *   **Uso Responsabile**: Utilizza le risposte dell'IA come spunto di riflessione o punto di partenza per ulteriori ricerche. **Non basare decisioni importanti riguardanti la tua salute fisica o mentale esclusivamente sulle informazioni fornite da questa applicazione.** Discuti sempre qualsiasi preoccupazione o decisione con un professionista sanitario qualificato.
            *   **Feedback**: Apprezziamo il tuo feedback per migliorare l'applicazione! Se riscontri problemi tecnici o hai suggerimenti, puoi utilizzare il modulo di contatto nella sezione "Chiedi a un Esperto" o contattarci all'indirizzo email fornito nella sezione Privacy.
            """)

        elif page == "🧠 Coach del Benessere":
            st.header("🧠 Coach Virtuale del Benessere")
            lottie_url_coach = "https://lottie.host/0c079fc2-f4df-452a-966b-3a852ffb9801/WjOxpGVduu.json"
            lottie_animation_coach = load_lottie_url(lottie_url_coach)
            if lottie_animation_coach: st_lottie(lottie_animation_coach, speed=1, width=220, height=300, key="lottie_coach")
            st.warning("**Promemoria:** Sono un'IA di supporto informativo...")

            # --- NUOVO INPUT TEXT AREA E PULSANTE ---
            st.markdown("#### Scrivi qui la tua domanda o riflessione:")
            user_prompt_wellness = st.text_area(
                "Inserisci il testo qui...",
                height=150, # Altezza per circa 5 righe
                key="wellness_input",
                label_visibility="collapsed"
            )
            submit_wellness = st.button("Invia al Coach AI ➡️", key="wellness_submit", type="primary")
            st.markdown("---") # Separatore prima della risposta

            # Inizializza/mostra cronologia (opzionale, si potrebbe mostrare solo la risposta corrente)
            if "chat_history_wellness" not in st.session_state: st.session_state.chat_history_wellness = []
            if st.session_state.chat_history_wellness:
                 st.markdown("**Risposta Precedente:**")
                 # Mostra solo l'ultima risposta per semplicità
                 last_resp = st.session_state.chat_history_wellness[-1]
                 if last_resp["role"] == "assistant":
                      with st.chat_message("assistant", avatar="❤️"):
                           st.markdown(last_resp["content"])
                 st.markdown("---")


            if submit_wellness and user_prompt_wellness:
                # Aggiungi input utente (visivamente, non alla history passata all'AI per semplicità)
                with st.chat_message("user"): st.markdown(user_prompt_wellness)

                with st.spinner("Salute Mentale AI sta elaborando... 🤔"):
                    response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, user_prompt_wellness)
                    with st.chat_message("assistant", avatar="❤️"): st.markdown(response_text)
                    # Salva solo l'ultima risposta nello stato per visualizzarla al prossimo rerun
                    st.session_state.chat_history_wellness = [{"role": "assistant", "content": response_text}]

                    # Suggerimenti Video
                    topic_for_youtube = extract_topic(user_prompt_wellness)
                    video_suggestions = fetch_youtube_videos(topic_for_youtube)
                    if video_suggestions:
                        st.markdown("---")
                        st.markdown("### Risorse Video Correlate (YouTube):")
                        for video in video_suggestions: st.markdown(f"- [{video['title']}]({video['url']})")
            elif submit_wellness and not user_prompt_wellness:
                 st.warning("Inserisci una domanda o una riflessione prima di inviare.")
            # --- FINE MODIFICHE COACH ---


        elif page == "📝 Analisi Referto Medico":
            st.header("📝 Analisi Referto Medico")
            # ... (Logica caricamento PDF e analisi come prima) ...

        elif page == "💊 Info Farmaci":
            st.header("💊 Info Farmaci")
            # ... (Logica input testo/PDF e analisi come prima) ...

        elif page == "🧑‍⚕️ Chiedi a un Esperto":
            st.header("🧑‍⚕️ Contatta un Esperto")
            st.markdown("""Hai bisogno di un parere...? Compila il modulo Google...""")
            st.link_button("📝 Apri Modulo Contatto", google_form_url, use_container_width=True, type="primary")
            st.markdown("---")
            st.markdown("""**Esperti (Esempio):**...""")

        elif page == "☢️ App Analisi Radiografie":
            st.header("App Analisi Radiografie ☢️")
            st.info("Stai per aprire l'applicazione esterna...")
            radiografie_url = "https://assistente-ai-per-radiografie.streamlit.app/"
            st.link_button("Apri App Radiografie", radiografie_url, use_container_width=True, type="primary")

        elif page == "🩸 App Analisi Sangue":
            st.header("App Analisi Sangue 🩸")
            st.info("Stai per aprire l'applicazione esterna...")
            sangue_url = "https://valutazione-preliminare-del-test-del-sangue.streamlit.app/"
            st.link_button("Apri App Analisi Sangue", sangue_url, use_container_width=True, type="primary")

        elif page == "⚖️ Informativa Privacy":
            st.header("⚖️ Informativa sulla Privacy")
            # --- TESTO POLICY COMPILATO ---
            st.markdown(f"""
            **Informativa sulla Privacy di Salute Mentale AI**

            Ultimo aggiornamento: [INSERISCI DATA]

            Noi di Salute Mentale AI ("noi", "nostro") ci impegniamo a proteggere la tua privacy. Questa informativa spiega come raccogliamo, utilizziamo e proteggiamo le informazioni quando utilizzi la nostra applicazione Streamlit ("App").

            **1. Informazioni Raccolte**

            *   **Input Utente per l'IA:** Quando interagisci con le funzionalità AI dell'App (es. Coach del Benessere, Analisi Referto, Info Farmaci), il testo o le immagini che fornisci vengono inviati all'API di Google Gemini per l'elaborazione. Questi dati vengono utilizzati da Google secondo la loro [informativa sulla privacy](https://policies.google.com/privacy). **Non archiviamo permanentemente i contenuti specifici** delle tue domande o dei tuoi documenti sulla nostra piattaforma oltre la durata necessaria per l'elaborazione della richiesta.
            *   **Dati di Utilizzo Anonimi:** Potremmo raccogliere dati anonimi sull'utilizzo dell'App (es. pagine visitate, funzionalità utilizzate) tramite le funzionalità integrate di Streamlit per aiutarci a migliorare il servizio. Questi dati non sono collegati alla tua identità personale.
            *   **Modulo di Contatto (Google Form):** Se scegli di contattarci tramite il Modulo Google linkato nella sezione "Chiedi a un Esperto", le informazioni che inserisci (es. nome, email, messaggio) verranno raccolte e gestite secondo l'informativa sulla privacy di Google e utilizzate da noi esclusivamente per rispondere alla tua richiesta.

            **2. Come Utilizziamo le Informazioni**

            *   Per fornire le funzionalità principali dell'App, elaborando i tuoi input tramite l'API Gemini.
            *   Per rispondere alle tue richieste inviate tramite il Modulo Google.
            *   Per analizzare dati di utilizzo anonimi al fine di migliorare le prestazioni e le funzionalità dell'App.

            **3. Condivisione delle Informazioni**

            *   **API Google Gemini:** Condividiamo i tuoi input testuali/immagini con Google al solo scopo di ottenere una risposta dall'IA generativa.
            *   **Modulo Google:** I dati inviati tramite il modulo sono gestiti da Google.
            *   **Terze Parti:** Non condividiamo le tue informazioni personali identificabili con altre terze parti, tranne se richiesto dalla legge o per proteggere i nostri diritti.

            **4. Sicurezza dei Dati**

            Adottiamo misure ragionevoli per proteggere le informazioni durante la trasmissione (l'App è servita tramite HTTPS). Tuttavia, nessuna trasmissione via Internet è completamente sicura. L'elaborazione da parte di Google è soggetta alle loro misure di sicurezza.

            **5. Cookie**

            L'App utilizza cookie essenziali gestiti dalla piattaforma Streamlit per il suo corretto funzionamento (es. gestione della sessione). Non utilizziamo cookie di tracciamento per pubblicità o analisi di terze parti.

            **6. I Tuoi Diritti**

            Poiché non archiviamo dati personali identificabili legati all'uso dell'IA, le richieste di accesso, correzione o cancellazione si applicano principalmente ai dati eventualmente forniti tramite il Modulo Google. Puoi gestire tali richieste contattandoci tramite lo stesso Modulo Google o all'indirizzo email sottostante. Puoi anche gestire le tue impostazioni sulla privacy direttamente con Google per i dati elaborati dalle loro API.

            **7. Contatti**

            Per domande relative a questa informativa sulla privacy, puoi contattarci tramite il [Modulo Google]({google_form_url}) oppure via email a: **{contact_email}** *(Sostituisci con la tua email)*

            **8. Modifiche all'Informativa**

            Potremmo aggiornare questa informativa periodicamente. La versione più recente sarà sempre disponibile all'interno dell'App. Ti invitiamo a consultarla regolarmente.
            """)

        elif page == "🫂 Sostienici":
            st.header("🫂 Sostienici")
            st.success("🙏 Grazie per aver visitato questa pagina! 🙏")
            st.info("Trovi le opzioni per la donazione nella barra laterale a sinistra...")
            st.write("Per supporto tecnico o feedback: ...")

        # --- SEZIONE DONAZIONE FOOTER ---
        st.markdown("---")
        st.markdown("#### Ti piace questa app? ❤️")
        st.markdown("...") # Testo donazione come prima
        st.link_button("☕ Offrimi un caffè...", buy_me_a_coffee_url, ...)

    # --- Footer Finale (Caption) ---
    st.markdown("---")
    st.caption("Applicazione sviluppata...") # Come prima

# --- Chiamata finale ---
if __name__ == "__main__":
    main()
