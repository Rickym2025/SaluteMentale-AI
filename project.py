import streamlit as st
import google.generativeai as genai
import os

st.set_page_config(page_title="Lista Modelli Disponibili", layout="wide")

st.title("🔍 Esploratore Modelli Gemini")

# Recupera la chiave
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("Chiave API mancante nei Secrets!")
    st.stop()

genai.configure(api_key=api_key)

if st.button("Mostra Modelli Disponibili"):
    try:
        st.info("Interrogo Google...")
        # Chiama la lista dei modelli
        models = list(genai.list_models())
        
        found_any = False
        st.write("### Modelli trovati:")
        
        for m in models:
            # Filtriamo solo quelli che generano contenuto (non quelli per embedding)
            if 'generateContent' in m.supported_generation_methods:
                st.success(f"✅ Nome Modello: `{m.name}`")
                st.caption(f"Descrizione: {m.description}")
                found_any = True
                
        if not found_any:
            st.warning("Nessun modello di generazione trovato. La chiave potrebbe avere permessi limitati.")
            
    except Exception as e:
        st.error(f"Errore durante il recupero della lista: {e}")
