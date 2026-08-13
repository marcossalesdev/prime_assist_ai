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
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "").replace("models/", "")
                    if name:
                        models.append(name)
            
            # Sort with newest/fastest first
            priority = [
                "gemini-flash-latest",
                "gemini-3.5-flash",
                "gemini-3-flash-preview",
                "gemini-3.5-flash-lite",
                "gemini-3.6-flash",
                "gemini-pro-latest",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash-8b",
                "gemini-2.0-flash-lite",
                "gemini-1.5-pro",
                "gemini-1.5-pro-latest"
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


def build_sanitized_contents(
    history: Optional[List[Dict[str, str]]],
    prompt: str,
    system_instruction: str = ""
) -> List[Dict[str, Any]]:
    """
    Builds a strictly valid Gemini multiturn 'contents' array:
    - Must start with 'user' role.
    - Must alternate strictly between 'user' and 'model'.
    - Merges consecutive turns of the same role.
    - Embeds system instruction in the first user turn or prompt.
    """
    user_prompt = f"{system_instruction}\n\nPergunta do Usuário:\n{prompt}" if system_instruction else prompt
    
    turns = []
    if history:
        for h in history:
            role_raw = str(h.get("role", "")).lower()
            role = "user" if role_raw in ["user", "human"] else "model"
            text = str(h.get("content", "")).strip()
            if text:
                turns.append({"role": role, "text": text})
                
    # Gemini requires first turn to be 'user'. Drop any leading 'model' messages (e.g. initial greeting).
    first_user_idx = -1
    for i, turn in enumerate(turns):
        if turn["role"] == "user":
            first_user_idx = i
            break
            
    valid_turns: List[Dict[str, str]] = []
    if first_user_idx != -1:
        for turn in turns[first_user_idx:]:
            if not valid_turns:
                valid_turns.append({"role": turn["role"], "text": turn["text"]})
            else:
                if valid_turns[-1]["role"] == turn["role"]:
                    valid_turns[-1]["text"] += "\n\n" + turn["text"]
                else:
                    valid_turns.append({"role": turn["role"], "text": turn["text"]})
                    
    # Append the current prompt
    if not valid_turns:
        valid_turns.append({"role": "user", "text": user_prompt})
    elif valid_turns[-1]["role"] == "user":
        valid_turns[-1]["text"] += "\n\n" + user_prompt
    else:
        valid_turns.append({"role": "user", "text": user_prompt})
        
    return [{"role": t["role"], "parts": [{"text": t["text"]}]} for t in valid_turns]


def generate_gemini_content(
    api_key: str,
    prompt: str,
    system_instruction: str = "",
    model_name: str = "gemini-flash-latest",
    history: Optional[List[Dict[str, str]]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generates content using the direct Gemini REST API with intelligent fallback models.
    Returns (response_text, error_message).
    """
    if not api_key:
        return None, "Chave de API não informada."
        
    api_key = api_key.strip()
    
    # Priority list of models to try
    candidate_models = [model_name]
    fallback_chain = [
        "gemini-flash-latest",
        "gemini-3.5-flash",
        "gemini-3-flash-preview",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-pro-latest",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
        "gemini-1.5-pro-latest"
    ]
    for fb in fallback_chain:
        if fb not in candidate_models:
            candidate_models.append(fb)
            
    contents = build_sanitized_contents(history, prompt, system_instruction)
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }
    
    last_error = ""
    
    for candidate in candidate_models:
        clean_model = candidate.replace("models/", "")
        
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
                    return "Não foi possível extrair o texto da resposta do modelo.", None
                else:
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                        err_status = err_json.get("error", {}).get("status", "")
                    except Exception:
                        err_msg = resp.text
                        err_status = ""
                    
                    last_error = f"[{api_version}/{clean_model}] {err_msg}"
                    
                    # Stop early on critical authentication or billing/quota errors that affect all models
                    if resp.status_code in [400, 401, 403, 429]:
                        if any(term in err_msg.lower() for term in ["api key not valid", "api_key_invalid", "permission_denied", "quota", "resource_exhausted", "billing"]):
                            return None, f"Erro na API do Google Gemini: {err_msg}"
            except Exception as e:
                last_error = f"[{api_version}/{clean_model}] Exceção: {str(e)}"
                
    return None, f"Falha na comunicação com os modelos Gemini. Último erro: {last_error}"


