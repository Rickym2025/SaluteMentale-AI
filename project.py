# -*- coding: utf-8 -*-
import streamlit as st
import google.generativeai as genai
import requests
from streamlit_lottie import st_lottie
import fitz  # PyMuPDF
import re
import os
import time
from google.api_core import exceptions

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Salute Mentale AI - DEBUG", page_icon="🔧", layout="wide")

# --- RECUPERO SECRETS ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
YOUTUBE_API_KEY = st.secrets.get("youtube_api_key")

# --- CONTROLLO CHIAVI (DEBUG) ---
if not GEMINI_API_KEY:
    st.error("🚨 CRITICO: GEMINI_API_KEY non trovata nei secrets!")
    st.stop()
else:
    # Mostriamo (solo per debug) se la chiave sembra valida come formato
    if len(GEMINI_API_KEY) < 30:
        st.warning(f"⚠️ La chiave API sembra troppo corta ({len(GEMINI_API_KEY)} caratteri). Controllala.")
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        st.error(f"🚨 Errore in genai.configure: {e}")

MODEL_NAME = 'gemini-1.5-flash'

# --- FUNZIONE GENERAZIONE CON ERRORI VISIBILI ---
def generate_gemini_response(system_prompt, user_content):
    # Creiamo il modello DENTRO la funzione per evitare problemi di sessione
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        full_prompt = f"{system_prompt}\n\nDomanda utente: {user_content}"
        
        # Chiamata diretta senza try-catch complessi per vedere l'errore puro
        response = model.generate_content(full_prompt)
        
        if response.text:
            return response.text
        else:
            return "⚠️ L'IA ha risposto ma il testo è vuoto (Blocco sicurezza?)"
            
    except Exception as e:
        # QUESTO È IL PUNTO FONDAMENTALE: Ti mostro l'errore esatto
        error_msg = str(e)
        if "400" in error_msg:
            return f"❌ ERRORE 400 (Bad Request): La chiave API potrebbe essere non valida o il progetto Google Cloud ha problemi. Dettaglio: {error_msg}"
        if "403" in error_msg:
            return f"❌ ERRORE 403 (Permission Denied): La chiave API è corretta ma non ha i permessi o è scaduta. Dettaglio: {error_msg}"
        if "429" in error_msg:
            return "❌ ERRORE 429 (Quota): Hai finito le richieste gratis per oggi."
        if "500" in error_msg:
            return "❌ ERRORE 500: Problema temporaneo dei server Google."
            
        return f"🚨 ERRORE GENERICO: {error_msg}"

# --- FUNZIONI HELPER MINIME ---
def extract_topic(prompt): return "benessere" # Semplificato per debug
def fetch_youtube_videos(query): return [] # Disabilitato per debug

# --- INTERFACCIA MINIMALE ---
st.title("🔧 Salute Mentale AI - MODALITÀ RIPARAZIONE")

st.info(f"Stato Chiave API: Presente ({len(GEMINI_API_KEY)} chars)")
st.info(f"Modello impostato: {MODEL_NAME}")

user_input = st.text_input("Scrivi qui la tua domanda (es. 'Ciao, come stai?'):")

if st.button("Invia Richiesta"):
    if not user_input:
        st.warning("Scrivi qualcosa prima.")
    else:
        with st.spinner("Contattando Gemini..."):
            risposta = generate_gemini_response("Sei un assistente utile.", user_input)
            
            st.markdown("### Risposta dell'IA (o Errore):")
            st.code(risposta) # Uso .code così non formatta il markdown e vediamo il testo grezzo
            
            if "❌" in risposta or "🚨" in risposta:
                st.error("👆 Leggi attentamente l'errore qui sopra.")
                st.markdown("Se dice **400** o **Key not valid**, devi rigenerare la chiave su [Google AI Studio](https://aistudio.google.com/).")
