import requests
import json
from typing import List, Dict, Any, Optional, Tuple

def list_gemini_models(api_key: str) -> Tuple[List[str], Optional[str]]:
    """
    Fetches available models directly from the Gemini REST API.
    Returns (list_of_model_names, error_message).
    """
    if not api_key:
        return [], "Chave de API não informada."
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            models = []
            for m in data.get("models", []):
                # Check if supports generateContent
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "").replace("models/", "")
                    if name:
                        models.append(name)
            
            # Sort with newest/fastest first
            priority = [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash-8b",
                "gemini-2.0-flash-lite",
                "gemini-2.5-pro",
                "gemini-1.5-pro",
                "gemini-1.5-pro-latest",
                "gemini-pro"
            ]
            sorted_models = []
            for p in priority:
                for m in models:
                    if (m == p or m.startswith(p)) and m not in sorted_models:
                        sorted_models.append(m)
            for m in models:
                if m not in sorted_models:
                    sorted_models.append(m)
                    
            return sorted_models if sorted_models else models, None
        else:
            try:
                err_data = resp.json()
                err_msg = err_data.get("error", {}).get("message", resp.text)
            except Exception:
                err_msg = resp.text
            return [], f"Erro HTTP {resp.status_code}: {err_msg}"
    except Exception as e:
        return [], f"Erro de conexão com a API do Google: {str(e)}"

def generate_gemini_content(
    api_key: str,
    prompt: str,
    system_instruction: str = "",
    model_name: str = "gemini-2.0-flash",
    history: Optional[List[Dict[str, str]]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generates content using the direct Gemini REST API with intelligent fallback models.
    Returns (response_text, error_message).
    """
    if not api_key:
        return None, "Chave de API não informada."
        
    api_key = api_key.strip()
    
    # List of candidate models to try starting with requested model
    candidate_models = [model_name]
    fallback_chain = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-2.0-flash-lite-preview-02-05",
        "gemini-1.5-pro-latest",
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    for fb in fallback_chain:
        if fb not in candidate_models:
            candidate_models.append(fb)
            
    last_error = ""
    
    for candidate in candidate_models:
        clean_model = candidate.replace("models/", "")
        
        # Build contents array
        contents = []
        if history:
            for h in history:
                role = "user" if h.get("role") in ["user", "human"] else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": h.get("content", "")}]
                })
        
        # Merge system instruction with prompt to maximize compatibility across all model versions
        if system_instruction:
            full_text = f"{system_instruction}\n\nPergunta do Usuário:\n{prompt}"
        else:
            full_text = prompt
            
        contents.append({
            "role": "user",
            "parts": [{"text": full_text}]
        })
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048
            }
        }
        
        # Try v1beta endpoint first, then v1
        for api_version in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{api_version}/models/{clean_model}:generateContent?key={api_key}"
            try:
                resp = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=30
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"], None
                    return "Não foi possível extrair a resposta do modelo.", None
                else:
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                        last_error = f"[{api_version}/{clean_model}] {err_msg}"
                    except Exception:
                        last_error = f"[{api_version}/{clean_model}] HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                last_error = f"[{api_version}/{clean_model}] Exceção: {str(e)}"
                
    return None, f"Falha na comunicação com os modelos Gemini. Último erro: {last_error}"

