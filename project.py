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
    YOUTUBE_API_KEY = st.secrets.get("youtube_api_key") # Usiamo .get
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
    st.set_page_config( page_title="Salute Mentale AI", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

    # URL per donazioni e contatto (SOSTITUISCI CON I TUOI LINK REALI)
    buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
    stripe_payment_link = "https://buy.stripe.com/tuo_link_id"
    google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
    contact_email = "[LA TUA EMAIL DI CONTATTO]" # Sostituisci

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Menu Principale")

        # --- IMMAGINE PERSONALIZZATA SIDEBAR (OPZIONALE) ---
        # Sostituisci 'path/to/your/image.png' con il percorso relativo
        # alla tua immagine nel repository GitHub (es. 'assets/logo.png')
        # o con un URL diretto se ospitata altrove.
        your_sidebar_image_path = None # Esempio: "assets/logo_sidebar.png"
        if your_sidebar_image_path and os.path.exists(your_sidebar_image_path):
            try: st.image(your_sidebar_image_path)
            except Exception as e: st.warning(f"Impossibile caricare immagine sidebar: {e}")
        elif your_sidebar_image_path:
             st.warning(f"Immagine sidebar non trovata: '{your_sidebar_image_path}'")
        # --- FINE IMMAGINE PERSONALIZZATA ---


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
        st.markdown("- [GitHub](...)")
        st.markdown("- [Twitter/X](...)")
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
            # --- LINEE GUIDA COMPILATE ---
            st.subheader("Linee Guida per l'Utilizzo:")
            st.markdown(f"""
            *   **Scopo Informativo**: Fornisce informazioni generali sul benessere mentale, non sostituisce pareri medici/psicologici professionali. L'accuratezza non è garantita.
            *   **Condotta Rispettosa**: Utilizzare un linguaggio appropriato e rispettoso durante le interazioni.
            *   **Privacy e Dati**: Le interazioni vengono processate da Google Gemini. Non inserire dati personali sensibili. Per richieste di contatto usa il [Modulo Google]({google_form_url}). Consulta la nostra Informativa Privacy.
            *   **Emergenze**: **Non usare per emergenze**. Contatta il 112 o linee di supporto dedicate se necessario.
            *   **Uso Responsabile**: Le informazioni sono spunti di riflessione, non consigli medici. Consulta sempre un professionista per decisioni sulla salute.
            *   **Feedback**: Aiutaci a migliorare segnalando problemi o suggerimenti tramite il [Modulo Google]({google_form_url}) o all'email {contact_email}.
            """)

        elif page == "🧠 Coach del Benessere":
            st.header("🧠 Coach Virtuale del Benessere")
            lottie_url_coach = "https://lottie.host/0c079fc2-f4df-452a-966b-3a852ffb9801/WjOxpGVduu.json"
            lottie_animation_coach = load_lottie_url(lottie_url_coach)
            if lottie_animation_coach: st_lottie(lottie_animation_coach, speed=1, width=220, height=300, key="lottie_coach")
            st.warning("**Promemoria:** Sono un'IA di supporto...")

            # Inizializza/mostra history (semplificata)
            if "chat_history_wellness" not in st.session_state: st.session_state.chat_history_wellness = []
            response_area = st.container() # Contenitore per la risposta
            if st.session_state.chat_history_wellness:
                 with response_area:
                     last_resp = st.session_state.chat_history_wellness[-1]
                     if last_resp["role"] == "assistant":
                          with st.chat_message("assistant", avatar="❤️"): st.markdown(last_resp["content"])
                     st.markdown("---")

            # --- MODIFICA: TEXT AREA CON PLACEHOLDER ---
            user_prompt_wellness = st.text_area(
                "Scrivi qui la tua domanda o riflessione...",
                height=150,
                key="wellness_input",
                label_visibility="collapsed",
                placeholder="Es: Come posso gestire l'ansia prima di un esame? Quali sono tecniche di rilassamento efficaci?" # Esempio placeholder
            )
            submit_wellness = st.button("Invia al Coach AI ➡️", key="wellness_submit", type="primary")

            if submit_wellness and user_prompt_wellness:
                # Mostra input utente (opzionale qui, dipende se vuoi stile chat o Q&A)
                # with st.chat_message("user"): st.markdown(user_prompt_wellness)
                with response_area: # Mostra spinner e risposta nel contenitore
                    with st.spinner("Salute Mentale AI sta elaborando... 🤔"):
                        response_text = generate_gemini_response(SYSTEM_PROMPT_MENTAL_HEALTH, user_prompt_wellness)
                        with st.chat_message("assistant", avatar="❤️"): st.markdown(response_text)
                        # Salva solo l'ultima risposta
                        if not response_text.startswith("Errore:"):
                            st.session_state.chat_history_wellness = [{"role": "assistant", "content": response_text}]
                        # Suggerimenti Video
                        topic_for_youtube = extract_topic(user_prompt_wellness)
                        video_suggestions = fetch_youtube_videos(topic_for_youtube)
                        if video_suggestions:
                            st.markdown("---"); st.markdown("### Risorse Video:")
                            for video in video_suggestions: st.markdown(f"- [{video['title']}]({video['url']})")
            elif submit_wellness and not user_prompt_wellness:
                 st.warning("Inserisci una domanda prima di inviare.")


        elif page == "📝 Analisi Referto Medico":
            st.header("📝 Analisi Referto Medico")
            st.markdown("**Carica PDF:**")
            uploaded_file = st.file_uploader("Scegli PDF", type=["pdf"], label_visibility="collapsed", key="pdf_report_uploader")
            if uploaded_file is not None:
                try:
                    pdf_bytes = uploaded_file.getvalue()
                    text = extract_text_from_pdf(pdf_bytes)
                    if text is not None: # Controlla che l'estrazione non sia fallita
                        st.text_area("Testo Estratto:", text, height=300)
                        st.markdown("---")
                        if st.button("🔬 Analizza Testo", type="primary", key="analyze_report_btn"):
                            with st.spinner("Analisi..."):
                                analisi_output = generate_gemini_response(SYSTEM_PROMPT_REPORT, f"--- TESTO ---\n{text}\n--- FINE ---")
                                st.subheader("Risultato Analisi:")
                                st.markdown(analisi_output)
                                if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"analisi_referto_{uploaded_file.name[:20]}")
                    # else: gestito da extract_text_from_pdf
                except Exception as e: st.error(f"Errore elaborazione PDF: {e}")

        elif page == "💊 Info Farmaci":
            st.header("💊 Info Farmaci")
            st.markdown("**Inserisci nome o carica PDF.**")
            input_method = st.radio("Metodo:", ("Testo", "Carica PDF"), horizontal=True, label_visibility="collapsed", key="drug_input_method")
            if input_method == "Testo":
                medicine_name = st.text_input("Nome farmaco:", placeholder="Es. Paracetamolo", key="drug_name_text")
                if st.button("Cerca Info", type="primary", key="search_drug_text_btn") and medicine_name:
                    with st.spinner(f"Ricerca {medicine_name}..."):
                        analisi_output = generate_gemini_response(SYSTEM_PROMPT_DRUG, f"Farmaco: {medicine_name}")
                        st.subheader(f"Info su {medicine_name}:")
                        st.markdown(analisi_output)
                        if not analisi_output.startswith("Errore:"): download_generated_report(analisi_output, f"info_{medicine_name.replace(' ','_')}")
                #elif not medicine_name and st.session_state.get('search_drug_text_btn'): # Gestione click senza testo
                 #   st.warning("Inserisci un nome di farmaco.")

            elif input_method == "Carica PDF":
                 uploaded_file_drug = st.file_uploader("Scegli PDF", type=["pdf"], key="pdf_drug_uploader", label_visibility="collapsed")
                 if uploaded_file_drug is not None:
                    try:
                        pdf_bytes_drug = uploaded_file_drug.getvalue()
                        text_drug = extract_text_from_pdf(pdf_bytes_drug)
                        if text_drug is not None:
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
                            #elif not medicine_from_pdf and st.session_state.get('search_drug_pdf_btn'):
                             #   st.warning("Inserisci nome farmaco.")
                        # else: gestito da extract_text_from_pdf
                    except Exception as e: st.error(f"Errore PDF: {e}")

        elif page == "🧑‍⚕️ Chiedi a un Esperto":
            st.header("🧑‍⚕️ Contatta un Esperto")
            st.markdown("""Hai bisogno di un parere più specifico...? Compila il modulo Google qui sotto...""")
            # --- LINK AL MODULO GOOGLE FORNITO ---
            st.link_button("📝 Apri il Modulo di Contatto Sicuro", google_form_url, use_container_width=True, type="primary")
            st.markdown("---")
            st.markdown("""**Esperti Disponibili (Esempio):**\n- Dott.ssa Anjali Sharma...""")

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

            Ultimo aggiornamento: 29 Aprile 2024 *(Sostituisci con data reale)*

            Noi di Salute Mentale AI ("noi", "nostro") ci impegniamo a proteggere la tua privacy. Questa informativa spiega come raccogliamo, utilizziamo e proteggiamo le informazioni quando utilizzi la nostra applicazione Streamlit ("App").

            **1. Informazioni Raccolte**

            *   **Input Utente per l'IA:** Quando interagisci con le funzionalità AI dell'App (es. Coach del Benessere, Analisi Referto, Info Farmaci), il testo o le immagini che fornisci vengono inviati all'API di Google Gemini per l'elaborazione. Questi dati vengono utilizzati da Google secondo la loro [informativa sulla privacy](https://policies.google.com/privacy). **Non archiviamo permanentemente i contenuti specifici** delle tue domande o dei tuoi documenti sulla nostra piattaforma oltre la durata necessaria per l'elaborazione della richiesta.
            *   **Dati di Utilizzo Anonimi:** Potremmo raccogliere dati anonimi sull'utilizzo dell'App (es. pagine visitate, funzionalità utilizzate) tramite le funzionalità integrate di Streamlit per aiutarci a migliorare il servizio. Questi dati non sono collegati alla tua identità personale.
            *   **Modulo di Contatto (Google Form):** Se scegli di contattarci tramite il Modulo Google linkato nella sezione "Chiedi a un Esperto", le informazioni che inserisci (es. nome, email, messaggio) verranno raccolte e gestite secondo l'informativa sulla privacy di Google e utilizzate da noi esclusivamente per rispondere alla tua specifica richiesta.

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

            Poiché non archiviamo dati personali identificabili legati all'uso diretto dell'IA nell'app, le richieste di accesso, correzione o cancellazione si applicano principalmente ai dati eventualmente forniti tramite il Modulo Google. Puoi gestire tali richieste contattandoci tramite lo stesso [Modulo Google]({google_form_url}) o all'indirizzo email sottostante. Puoi anche gestire le tue impostazioni sulla privacy direttamente con Google per i dati elaborati dalle loro API.

            **7. Contatti**

            Per domande relative a questa informativa sulla privacy, puoi utilizzare il [Modulo Google]({google_form_url}) oppure scriverci a: **{contact_email}** *(Assicurati che contact_email sia definito con la tua email)*

            **8. Modifiche all'Informativa**

            Potremmo aggiornare questa informativa periodicamente. La versione più recente sarà sempre disponibile all'interno dell'App. Ti invitiamo a consultarla regolarmente.
            """)

        elif page == "🫂 Sostienici":
            st.header("🫂 Sostienici")
            st.success("🙏 Grazie per aver visitato questa pagina! 🙏")
            st.info("Trovi le opzioni per la donazione nella barra laterale a sinistra...")
            st.write("Per supporto tecnico o feedback: skavtech.in@gmail.com")

        # --- SEZIONE DONAZIONE FOOTER ---
        # Mostra solo se NON siamo nella pagina Sostienici (per evitare duplicati)
        if page != "🫂 Sostienici":
            st.markdown("---")
            st.markdown("#### Ti piace questa app? ❤️")
            st.markdown("Mantenere e migliorare **Salute Mentale AI** richiede impegno...")
            st.link_button("☕ Offrimi un caffè (Buy Me a Coffee)", buy_me_a_coffee_url, use_container_width=True, type="primary")
            st.caption("Anche un piccolo contributo aiuta!")

    # --- Footer Finale (Caption) ---
    st.markdown("---")
    st.caption("Applicazione sviluppata con Streamlit e Google Gemini. Ricorda: consulta sempre un medico o professionista qualificato.")

# --- Chiamata finale ---
if __name__ == "__main__":
    main()
