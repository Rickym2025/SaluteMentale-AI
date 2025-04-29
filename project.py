# ==================================================
# FUNZIONE PRINCIPALE DELL'APP STREAMLIT
# ==================================================
def main():
    st.set_page_config(page_title="Salute Mentale AI", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

    # URL per donazioni e contatto (SOSTITUISCI CON I TUOI LINK REALI)
    buy_me_a_coffee_url = "https://buymeacoffee.com/smartai"
    stripe_payment_link = "https://buy.stripe.com/tuo_link_id" # Sostituisci
    google_form_url = "https://docs.google.com/forms/d/e/1FAIpQLScayUn2nEf1WYYEuyzEvxOb5zBvYDKW7G-zqakqHn4kzxza2A/viewform?usp=header"
    contact_email = "[LA TUA EMAIL DI CONTATTO]" # Sostituisci

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Menu Principale")
        # ... (Codice selectbox come prima) ...
        page_options = ["🏠 Home", "🧠 Coach del Benessere", "📝 Analisi Referto Medico", "💊 Info Farmaci",
                         "🧑‍⚕️ Chiedi a un Esperto", "--- Strumenti Correlati ---", "☢️ App Analisi Radiografie",
                         "🩸 App Analisi Sangue", "--- Info e Supporto ---", "⚖️ Informativa Privacy", "🫂 Sostienici"]
        separator_values = ["--- Strumenti Correlati ---", "--- Info e Supporto ---"]
        def format_func(option): return "---" if option in separator_values else option
        page = st.sidebar.selectbox("**MENU**", page_options, label_visibility="collapsed", format_func=format_func)

        # ... (Codice donazioni e social come prima) ...

    # --- Contenuto Pagina Principale ---
    header_image_url = "https://cdn.leonardo.ai/users/8a519dc0-5f27-42a1-a9a3-662461401c5f/generations/1fde2447-b823-4ab1-8afa-77198e290e2d/Leonardo_Phoenix_10_Crea_un_logo_professionale_moderno_e_altam_2.jpg"
    try: st.image(header_image_url)
    except Exception as img_err: st.warning(f"Avviso intestazione: {img_err}", icon="🖼️")

    # --- CONTENUTO SPECIFICO PER PAGINA ---
    if page not in separator_values:
        if page == "🏠 Home":
            st.title("Benvenuto/a in Salute Mentale AI 🧠❤️")
            # ... (Contenuto Home come prima, incluse Linee Guida) ...

        elif page == "🧠 Coach del Benessere":
            st.header("🧠 Coach Virtuale del Benessere")
            # ... (Contenuto Coach come prima, con text_area) ...

        elif page == "📝 Analisi Referto Medico":
            st.header("📝 Analisi Referto Medico")
            # ... (Contenuto Analisi Referto come prima) ...

        elif page == "💊 Info Farmaci":
            st.header("💊 Info Farmaci")
            # ... (Contenuto Info Farmaci come prima) ...

        elif page == "🧑‍⚕️ Chiedi a un Esperto":
            st.header("🧑‍⚕️ Contatta un Esperto")
            # ... (Contenuto Chiedi Esperto con link modulo Google come prima) ...

        # === REINSERITI BLOCCHI PER APP ESTERNE ===
        elif page == "☢️ App Analisi Radiografie":
            st.header("App Analisi Radiografie ☢️") # Titolo della pagina
            st.info("ℹ️ Stai per aprire un'applicazione esterna in una nuova scheda, specificamente progettata per l'analisi preliminare di immagini radiografiche.")
            radiografie_url = "https://assistente-ai-per-radiografie.streamlit.app/"
            st.link_button("Apri App Analisi Radiografie", radiografie_url, use_container_width=True, type="primary")
            st.markdown("---")
            st.caption(f"Link diretto (se il pulsante non funziona): {radiografie_url}")

        elif page == "🩸 App Analisi Sangue":
            st.header("App Analisi Sangue 🩸") # Titolo della pagina
            st.info("ℹ️ Stai per aprire un'applicazione esterna in una nuova scheda, dedicata alla valutazione preliminare dei test del sangue.")
            sangue_url = "https://valutazione-preliminare-del-test-del-sangue.streamlit.app/"
            st.link_button("Apri App Analisi Sangue", sangue_url, use_container_width=True, type="primary")
            st.markdown("---")
            st.caption(f"Link diretto (se il pulsante non funziona): {sangue_url}")
        # === FINE BLOCCHI APP ESTERNE ===

        elif page == "⚖️ Informativa Privacy":
            st.header("⚖️ Informativa sulla Privacy")
            # ... (Testo policy completo come prima) ...

        elif page == "🫂 Sostienici":
            st.header("🫂 Sostienici")
            # ... (Contenuto Sostienici come prima) ...

        # --- SEZIONE DONAZIONE FOOTER (come prima) ---
        if page != "🫂 Sostienici":
            st.markdown("---")
            st.markdown("#### Ti piace questa app? ❤️")
            st.markdown("Mantenere e migliorare **Salute Mentale AI** richiede impegno...")
            st.link_button("☕ Offrimi un caffè...", buy_me_a_coffee_url, use_container_width=True, type="primary")
            st.caption("Anche un piccolo contributo aiuta!")

    # --- Footer Finale (Caption) ---
    st.markdown("---")
    st.caption("Applicazione sviluppata con Streamlit e Google Gemini...") # Come prima

# --- Chiamata finale ---
if __name__ == "__main__":
    main()
