import os
import streamlit as st
from backend.rag import RAGEngine
from gemini_client import list_gemini_models, generate_gemini_content

# Page Configuration
st.set_page_config(
    page_title="PrimeAssist AI - PrimePharma",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    /* Global Styles */
    .main-header {
        display: flex;
        align-items: center;
        gap: 15px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 20px;
    }
    .badge-status {
        background: linear-gradient(135deg, #0ea5e9, #10b981);
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .example-btn {
        text-align: left;
        margin-bottom: 5px;
    }
    .source-card {
        background: rgba(14, 165, 233, 0.05);
        border: 1px solid rgba(14, 165, 233, 0.2);
        border-radius: 8px;
        padding: 10px;
        margin-top: 8px;
        font-size: 0.85rem;
    }
    /* Estilo do botao Limpar Conversa abaixo da caixa de pergunta */
    div.st-key-btn_clear_chat {
        display: flex;
        justify-content: center;
        margin: 6px auto 14px auto;
    }
    div.st-key-btn_clear_chat button {
        border-radius: 20px;
        padding: 4px 18px;
        font-size: 0.82rem;
        border: 1px solid rgba(128, 128, 128, 0.25);
        background: rgba(255, 255, 255, 0.04);
        transition: all 0.2s ease;
    }
    div.st-key-btn_clear_chat button:hover {
        border-color: #ef4444;
        color: #ef4444;
        background: rgba(239, 68, 68, 0.08);
    }
</style>
""", unsafe_allow_html=True)

# Define directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "backend", "data")
LOGO_PATH = os.path.join(BASE_DIR, "frontend", "Logo_PrimePharma.png")

# Initialize RAG Engine with Streamlit Caching
@st.cache_resource
def get_rag_engine():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    return RAGEngine(DATA_DIR)

rag_engine = get_rag_engine()

# Helper to get API Key
def get_api_key():
    # 1. From Streamlit Secrets (if configured)
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    
    # 2. From Environment Variable
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv("GEMINI_API_KEY")
        
    # 3. From Session State
    return st.session_state.get("user_gemini_api_key", "")

# Sidebar Configuration
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.title("💊 PrimeAssist AI")
    
    st.caption("Assistente Inteligente Oficial da **PrimePharma**")
    st.divider()

    # API Key Configuration
    st.subheader("🔑 Configuração da API")
    current_key = get_api_key()
    
    api_key_input = st.text_input(
        "Chave de API do Google Gemini",
        value=st.session_state.get("user_gemini_api_key", current_key if current_key else ""),
        type="password",
        placeholder="AIzaSy...",
        help="Obtenha sua chave gratuita no Google AI Studio (aistudio.google.com)."
    )
    if api_key_input:
        st.session_state["user_gemini_api_key"] = api_key_input
        active_key = api_key_input
    else:
        active_key = current_key

    # Dynamic model discovery
    default_models = [
        "gemini-flash-latest",
        "gemini-3.5-flash",
        "gemini-3-flash-preview",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-pro-latest",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]
    
    available_models = default_models
    if active_key:
        models_found, _ = list_gemini_models(active_key)
        if models_found:
            available_models = models_found

    # Conectar API button
    if st.button("🔌 Conectar API"):
        if not active_key:
            st.warning("Insira uma chave de API antes de conectar.")
        else:
            with st.spinner("Conectando e testando chave com a API Google Gemini..."):
                test_models, err = list_gemini_models(active_key)
                if test_models:
                    st.success(f"✅ Conectado com sucesso! ({len(test_models)} modelos disponíveis)")
                    with st.expander("Modelos disponíveis para sua chave"):
                        for m in test_models:
                            st.caption(f"• `{m}`")
                else:
                    st.error(f"❌ Falha ao conectar API:\n\n{err}")

    # Model Selection
    selected_model = st.selectbox(
        "Modelo de IA",
        options=available_models,
        index=0,
        help="Modelos disponíveis para a sua chave de API com fallback automático."
    )

    st.divider()

    # Document Management
    st.subheader("📁 Base de Conhecimento")
    
    # List documents
    if os.path.exists(DATA_DIR):
        files = [f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
        st.write(f"**Documentos Indexados:** {len(files)}")
        st.write(f"**Blocos de RAG ativos:** {len(rag_engine.chunks)}")
        
        with st.expander("Ver arquivos carregados"):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                icon = "📄" if ext == ".pdf" else "📊" if ext in [".csv", ".xlsx", ".xls"] else "📝"
                st.markdown(f"{icon} `{f}`")
    
    # Upload new documents
    uploaded_file = st.file_uploader(
        "Adicionar novo documento",
        type=["pdf", "csv", "xlsx", "xls", "txt"],
        help="Faça upload de arquivos PDF, planilhas CSV/Excel ou TXT para a base."
    )
    
    if uploaded_file is not None:
        save_path = os.path.join(DATA_DIR, uploaded_file.name)
        if st.button("📥 Processar e Indexar Documento"):
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            rag_engine.load_documents()
            st.success(f"Arquivo `{uploaded_file.name}` indexado com sucesso!")
            st.rerun()

    if st.button("🔄 Reindexar Base Completa"):
        rag_engine.load_documents()
        st.success("Base de conhecimento re-indexada!")
        st.rerun()

# Initial Greeting
DEFAULT_MESSAGES = [
    {
        "role": "assistant",
        "content": "Olá! Eu sou o **PrimeAssist AI**, o assistente corporativo da **PrimePharma**.\n\n"
                   "Posso responder a dúvidas sobre políticas internas, procedimentos de atendimento, "
                   "trocas e devoluções, programa de fidelidade, controle de estoque e relatórios de vendas. "
                   "Como posso te ajudar hoje?",
        "sources": []
    }
]

# Main App Header
col1, col2 = st.columns([0.8, 0.2])
with col1:
    st.title("PrimeAssist AI 💬")
    st.markdown("Consulte políticas, manuais, procedimentos, controle de estoque e vendas da **PrimePharma**.")
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f'<span class="badge-status">● RAG Ativo ({len(rag_engine.chunks)} blocos)</span>', unsafe_allow_html=True)

# Initialize Chat History
if "messages" not in st.session_state or not st.session_state.messages:
    st.session_state.messages = [dict(m) for m in DEFAULT_MESSAGES]

# Example Queries Section
with st.expander("💡 Sugestões de perguntas rápidas por categoria", expanded=False):
    tab1, tab2, tab3 = st.tabs(["📄 Documentação & Procedimentos", "📦 Estoque & Produtos", "📈 Vendas & Desempenho"])
    
    def set_query(query_text):
        st.session_state.temp_prompt = query_text

    with tab1:
        st.button("Qual é a política de troca para medicamentos termolábeis?", on_click=set_query, args=("Qual é a política de troca e devoluções para medicamentos termolábeis?",), key="ex1")
        st.button("Como funciona o acúmulo e resgate de pontos no programa Prime+?", on_click=set_query, args=("Como funciona o acúmulo e resgate de pontos no programa Prime+?",), key="ex2")
        st.button("Qual é o procedimento padrão para abertura e sangria de caixa?", on_click=set_query, args=("Qual é o procedimento de abertura de caixa e sangria?",), key="ex3")
        st.button("Quais são as diretrizes de conduta e atendimento ao cliente?", on_click=set_query, args=("Quais são as principais diretrizes de atendimento ao cliente da PrimePharma?",), key="ex4")

    with tab2:
        st.button("Qual é a quantidade atual em estoque do medicamento Aradois 50mg?", on_click=set_query, args=("Qual é a quantidade atual em estoque do medicamento Aradois 50mg?",), key="ex5")
        st.button("Quais medicamentos estão com estoque crítico ou abaixo do mínimo?", on_click=set_query, args=("Quais medicamentos estão com estoque crítico ou abaixo do mínimo?",), key="ex6")
        st.button("Qual é a localização e lote do medicamento Glifage XR 500mg?", on_click=set_query, args=("Qual é a localização e lote do medicamento Glifage XR 500mg no estoque?",), key="ex7")

    with tab3:
        st.button("Qual foi o produto mais vendido no último trimestre?", on_click=set_query, args=("Qual foi o produto mais vendido no último trimestre e qual a receita total?",), key="ex8")
        st.button("Qual filial teve o melhor desempenho de faturamento em vendas?", on_click=set_query, args=("Qual filial teve o melhor desempenho de faturamento em vendas?",), key="ex9")
        st.button("Qual categoria de produtos gerou a maior receita?", on_click=set_query, args=("Qual categoria de produtos gerou a maior receita de vendas?",), key="ex10")

# Render Chat Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="💊" if msg["role"] == "assistant" else "👤"):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📚 Fontes consultadas na resposta"):
                for idx, src in enumerate(msg["sources"]):
                    st.markdown(f"**Fonte {idx+1}:** `{src['source']}` ({src.get('position', 'N/A')}) — *Relevância: {src.get('score', 0)}*")
                    st.caption(f"_{src['content']}_")

# Process User Input
prompt = st.chat_input("Digite sua pergunta sobre a PrimePharma...")
if "temp_prompt" in st.session_state and st.session_state.temp_prompt:
    prompt = st.session_state.temp_prompt
    st.session_state.temp_prompt = None

if prompt:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Assistant Response
    with st.chat_message("assistant", avatar="💊"):
        # 1. Retrieve relevant chunks via RAG
        sources = rag_engine.retrieve(prompt, top_k=5)
        
        # 2. Check for API key
        if not active_key:
            source_summary = "\n".join([f"- **{s['source']}** ({s['position']}): {s['content'][:140]}..." for s in sources])
            placeholder_answer = (
                "⚠️ **Chave de API do Gemini não configurada.**\n\n"
                "Para gerar respostas completas e inteligentes com IA, configure sua **API Key do Google Gemini** "
                "na barra lateral esquerda ou adicione `GEMINI_API_KEY` nos Secrets do Streamlit Cloud.\n\n"
                "**Trechos relevantes encontrados nos documentos:**\n" + 
                (source_summary if sources else "_Nenhum documento relevante encontrado._")
            )
            st.markdown(placeholder_answer)
            st.session_state.messages.append({
                "role": "assistant",
                "content": placeholder_answer,
                "sources": sources
            })
        else:
            with st.spinner("Consultando base de conhecimento e gerando resposta..."):
                # Prepare context
                context_text = ""
                for idx, src in enumerate(sources):
                    context_text += f"Documento [{idx + 1}]: {src['source']} ({src['position']})\nConteúdo: {src['content']}\n\n"

                # System instruction
                system_instruction = (
                    "Você é o PrimeAssist AI, o assistente de inteligência artificial oficial da empresa PrimePharma.\n"
                    "Sua principal diretriz é responder à pergunta do usuário baseando-se EXCLUSIVAMENTE nas "
                    "informações contidas no Contexto Oficial fornecido abaixo. As informações do Contexto vêm de "
                    "documentos e planilhas oficiais da empresa.\n\n"
                    "Regras cruciais:\n"
                    "1. Responda apenas com base no Contexto Oficial fornecido. Se a resposta para a pergunta não estiver presente "
                    "no Contexto, diga exatamente: 'Desculpe, não encontrei essa informação nos documentos oficiais da PrimePharma.'\n"
                    "2. NUNCA utilize conhecimento externo, suposições ou dados fora do contexto. Não adivinhe dados de estoque, preços ou regras.\n"
                    "3. Mantenha um tom profissional, prestativo e corporativo.\n"
                    "4. Não mencione explicitamente termos técnicos de RAG como 'de acordo com o contexto fornecido' ou 'baseado no documento'. "
                    "Responda diretamente e com precisão.\n"
                    "5. Formate a resposta usando Markdown de forma limpa (tabelas, listas, negrito).\n\n"
                    "CONTEXTO OFICIAL:\n"
                    "----------------------\n"
                    f"{context_text if context_text else 'NENHUM DOCUMENTO OU PLANILHA ENCONTRADO NA BASE DE DADOS.'}\n"
                    "----------------------\n"
                )

                # History
                chat_history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]

                # Generate content with robust fallback
                answer_text, err = generate_gemini_content(
                    api_key=active_key,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model_name=selected_model,
                    history=chat_history
                )

                if answer_text:
                    st.markdown(answer_text)
                    if sources:
                        with st.expander("📚 Fontes consultadas na resposta"):
                            for idx, src in enumerate(sources):
                                st.markdown(f"**Fonte {idx+1}:** `{src['source']}` ({src.get('position', 'N/A')}) — *Relevância: {src.get('score', 0)}*")
                                st.caption(f"_{src['content']}_")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer_text,
                        "sources": sources
                    })
                else:
                    err_msg = (
                        f"❌ **Erro ao processar consulta:** {err}\n\n"
                        "**Dicas para resolver:**\n"
                        "1. Certifique-se de que a chave foi criada no **[Google AI Studio](https://aistudio.google.com/)** (Get API Key).\n"
                        "2. Use o botão **'🔌 Conectar API'** na barra lateral para diagnosticar a chave.\n"
                        "3. Se você criou a chave no Google Cloud Console comum, certifique-se de habilitar a **Generative Language API** no seu projeto."
                    )
                    st.error(err_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": err_msg,
                        "sources": sources
                    })

# Botao Limpar Conversa posicionado abaixo da caixa de pergunta
col_l, col_btn, col_r = st.columns([0.38, 0.24, 0.38])
with col_btn:
    if st.button("🗑️ Limpar Conversa", key="btn_clear_chat", use_container_width=True, help="Reiniciar histórico de mensagens"):
        st.session_state.messages = [dict(m) for m in DEFAULT_MESSAGES]
        st.rerun()


