import os
import sys
import shutil
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.rag import RAGEngine
from gemini_client import generate_gemini_content

app = FastAPI(title="PrimeAssist AI API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG Engine
DATA_DIR = os.path.join(BASE_DIR, "data")
rag_engine = RAGEngine(DATA_DIR)

class ChatMessage(BaseModel):
    role: str  # "user" or "model" / "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    apiKey: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    success: bool
    requiresKey: bool = False

@app.get("/api/documents")
async def list_documents():
    """Lists all files in the data directory with metadata."""
    if not os.path.exists(DATA_DIR):
        return []
    
    docs = []
    for filename in os.listdir(DATA_DIR):
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            size_kb = round(stat.st_size / 1024, 2)
            ext = os.path.splitext(filename)[1].lower()
            
            # Simple content summary
            item_count = 0
            if ext == '.txt':
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    item_count = len([line for line in f if line.strip()])
                doc_type = "Documento de Texto (.txt)"
                unit = "linhas com conteúdo"
            elif ext == '.csv':
                try:
                    import pandas as pd
                    df = pd.read_csv(filepath)
                    item_count = len(df)
                except Exception:
                    item_count = 0
                doc_type = "Planilha (.csv)"
                unit = "registros/linhas"
            elif ext in ['.xlsx', '.xls']:
                try:
                    import pandas as pd
                    df = pd.read_excel(filepath)
                    item_count = len(df)
                except Exception:
                    item_count = 0
                doc_type = "Planilha Excel (.xlsx)"
                unit = "registros/linhas"
            elif ext == '.pdf':
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(filepath)
                    item_count = len(reader.pages)
                except Exception:
                    item_count = 0
                doc_type = "Documento PDF (.pdf)"
                unit = "páginas"
            else:
                doc_type = "Outro"
                unit = "bytes"
                item_count = stat.st_size
                
            docs.append({
                "filename": filename,
                "size": f"{size_kb} KB",
                "type": doc_type,
                "items": f"{item_count} {unit}",
                "updated_at": stat.st_mtime
            })
            
    # Sort docs by updated_at descending
    docs.sort(key=lambda x: x["updated_at"], reverse=True)
    return docs

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Uploads a document to the data folder and re-indexes the RAG Engine."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.txt', '.csv', '.xlsx', '.xls', '.pdf']:
        raise HTTPException(
            status_code=400, 
            detail="Tipo de arquivo não suportado. Envie apenas .txt, .csv, .xlsx ou .pdf"
        )
        
    filepath = os.path.join(DATA_DIR, file.filename)
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Re-index
        rag_engine.load_documents()
        return {"filename": file.filename, "message": "Arquivo enviado e indexado com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")

@app.delete("/api/documents/{filename}")
async def delete_document(filename: str):
    """Deletes a document from the data folder and re-indexes the RAG Engine."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        
    try:
        os.remove(filepath)
        # Re-index
        rag_engine.load_documents()
        return {"message": f"Arquivo '{filename}' deletado e base re-indexada."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar arquivo: {str(e)}")

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handles chat query by retrieving sources and calling Gemini API."""
    # Retrieve top 5 most relevant chunks from local database
    sources = rag_engine.retrieve(request.message, top_k=5)
    
    # Check for API Key
    api_key = request.apiKey or os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        source_summary = "\n".join([f"- {s['source']} ({s['position']}): {s['content'][:150]}..." for s in sources])
        placeholder_answer = (
            "Olá! Eu sou o **PrimeAssist AI**, o assistente oficial da PrimePharma.\n\n"
            "Encontrei informações relevantes na base de conhecimento sobre sua pergunta, mas para que eu "
            "possa gerar uma resposta inteligente em linguagem natural, **você precisa configurar sua Chave de API "
            "do Gemini nas Configurações** (no menu lateral).\n\n"
            "**Informações encontradas que podem ajudar:**\n" + (source_summary if sources else "*Nenhuma informação encontrada nos documentos.*")
        )
        return ChatResponse(
            answer=placeholder_answer,
            sources=sources,
            success=True,
            requiresKey=True
        )

    # Format the context text for the model
    context_text = ""
    for idx, source in enumerate(sources):
        context_text += f"Documento [{idx + 1}]: {source['source']} ({source['position']})\nConteúdo: {source['content']}\n\n"

    # Strict system instruction
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
        "4. Não mencione explicitamente termos técnicos de RAG como 'de acordo com o contexto fornecido', 'baseado nas informações acima' "
        "ou 'no documento X'. Responda diretamente e naturalmente, citando os dados de forma fluida (ex: 'O preço do Aradois é R$ 34,90' ou "
        "'Medicamentos termolábeis não podem ser devolvidos').\n"
        "5. Formate a resposta usando Markdown de forma limpa (negritos, listas) para facilitar a leitura.\n\n"
        "CONTEXTO OFICIAL:\n"
        "----------------------\n"
        f"{context_text if context_text else 'NENHUM DOCUMENTO OU PLANILHA ENCONTRADO NA BASE DE DADOS.'}\n"
        "----------------------\n"
    )

    formatted_history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.history
    ]

    answer_text, err = generate_gemini_content(
        api_key=api_key,
        prompt=request.message,
        system_instruction=system_instruction,
        model_name="gemini-flash-latest",
        history=formatted_history
    )

    if answer_text:
        return ChatResponse(
            answer=answer_text,
            sources=sources,
            success=True
        )

    return ChatResponse(
        answer=f"Erro ao gerar resposta com o Gemini: {err}. Verifique se sua chave de API possui cotas ativas no Google AI Studio.",
        sources=sources,
        success=False
    )

# Mount the static files folder (frontend)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    print(f"Diretório frontend '{FRONTEND_DIR}' não encontrado. API rodando apenas no backend.")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
