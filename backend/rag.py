import os
import re
import pandas as pd
from typing import List, Dict, Any

class RAGEngine:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.chunks = []  # List[Dict[str, Any]] -> { "id": int, "source": str, "content": str, "type": str }
        self.stop_words = {
            "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
            "em", "no", "na", "nos", "nas", "para", "por", "com", "sem", "sob", "sobre", "e", "ou",
            "que", "se", "como", "esta", "este", "isto", "esse", "isso", "aquele", "aquilo", "um", "uma"
        }
        self.load_documents()

    def clean_text(self, text: str) -> str:
        # Lowercase and clean special chars for search
        text = text.lower()
        text = re.sub(r'[^\w\s\-\.]', '', text)
        return text

    def load_documents(self):
        """Loads and processes all files from the data directory into chunks."""
        self.chunks = []
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            return

        chunk_id = 0
        for filename in os.listdir(self.data_dir):
            filepath = os.path.join(self.data_dir, filename)
            if not os.path.isfile(filepath):
                continue

            ext = os.path.splitext(filename)[1].lower()
            try:
                if ext == '.txt':
                    chunk_id = self._parse_txt(filepath, filename, chunk_id)
                elif ext == '.csv':
                    chunk_id = self._parse_csv(filepath, filename, chunk_id)
                elif ext in ['.xlsx', '.xls']:
                    chunk_id = self._parse_xlsx(filepath, filename, chunk_id)
                elif ext == '.pdf':
                    chunk_id = self._parse_pdf(filepath, filename, chunk_id)
            except Exception as e:
                print(f"Erro ao processar arquivo {filename}: {str(e)}")

        print(f"RAG Engine carregado com {len(self.chunks)} blocos de texto.")

    def _parse_txt(self, filepath: str, filename: str, start_id: int) -> int:
        chunk_id = start_id
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Split by double newline to get logical sections/paragraphs
        sections = [s.strip() for s in content.split('\n\n') if s.strip()]
        
        for idx, section in enumerate(sections):
            # If a section is too long, we split it further by lines
            if len(section) > 800:
                subsections = []
                lines = section.split('\n')
                current_sub = ""
                for line in lines:
                    if len(current_sub) + len(line) < 800:
                        current_sub += "\n" + line if current_sub else line
                    else:
                        if current_sub:
                            subsections.append(current_sub.strip())
                        current_sub = line
                if current_sub:
                    subsections.append(current_sub.strip())
            else:
                subsections = [section]

            for sub in subsections:
                self.chunks.append({
                    "id": chunk_id,
                    "source": filename,
                    "content": sub,
                    "type": "Documento de Texto",
                    "position": f"Seção {idx + 1}"
                })
                chunk_id += 1
        return chunk_id

    def _parse_csv(self, filepath: str, filename: str, start_id: int) -> int:
        chunk_id = start_id
        # Read CSV with automatic separator detection
        try:
            df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        except Exception:
            df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
            
        return self._process_dataframe(df, filename, start_id)

    def _parse_xlsx(self, filepath: str, filename: str, start_id: int) -> int:
        df = pd.read_excel(filepath)
        return self._process_dataframe(df, filename, start_id)

    def _parse_pdf(self, filepath: str, filename: str, start_id: int) -> int:
        chunk_id = start_id
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
        except Exception as e:
            print(f"Erro ao ler PDF {filename}: {str(e)}")
            return chunk_id

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text or not text.strip():
                continue

            # Limpar e normalizar espaçamentos do PDF
            text_cleaned = re.sub(r'\s+', ' ', text).strip()
            if not text_cleaned:
                continue

            # Dividir em blocos de até 800 caracteres buscando limites de sentenças/palavras
            max_chars = 800
            start = 0
            subsections = []
            while start < len(text_cleaned):
                end = start + max_chars
                if end >= len(text_cleaned):
                    subsections.append(text_cleaned[start:])
                    break
                
                # Procurar final de frase nos últimos 150 caracteres do bloco
                limit = max(start, end - 150)
                split_pos = -1
                for p in range(end, limit - 1, -1):
                    if text_cleaned[p] in ['.', '!', '?'] and p + 1 < len(text_cleaned) and text_cleaned[p+1] == ' ':
                        split_pos = p + 1
                        break
                
                if split_pos == -1:
                    # Alternativa: procurar o último espaço em branco
                    for p in range(end, limit - 1, -1):
                        if text_cleaned[p] == ' ':
                            split_pos = p
                            break
                
                if split_pos == -1:
                    split_pos = end
                
                subsections.append(text_cleaned[start:split_pos].strip())
                start = split_pos

            for idx, sub in enumerate(subsections):
                self.chunks.append({
                    "id": chunk_id,
                    "source": filename,
                    "content": sub,
                    "type": "Documento PDF",
                    "position": f"Pág. {page_num + 1}" + (f", Parte {idx + 1}" if len(subsections) > 1 else "")
                })
                chunk_id += 1
        return chunk_id

    def _process_dataframe(self, df: pd.DataFrame, filename: str, start_id: int) -> int:
        chunk_id = start_id
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # Group rows or convert row-by-row
        for idx, row in df.iterrows():
            row_parts = []
            for col in df.columns:
                val = row[col]
                if pd.notna(val) and str(val).strip() != "":
                    row_parts.append(f"{col}: {str(val).strip()}")
            
            row_content = " | ".join(row_parts)
            self.chunks.append({
                "id": chunk_id,
                "source": filename,
                "content": f"Registro/Linha {idx + 1}: {row_content}",
                "type": "Planilha/Tabela",
                "position": f"Linha {idx + 1}"
            })
            chunk_id += 1
            
        return chunk_id

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieves the top_k most relevant chunks using word overlap and phrase matching."""
        if not self.chunks:
            return []

        # Tokenize query
        query_cleaned = self.clean_text(query)
        query_words = [w for w in query_cleaned.split() if w not in self.stop_words and len(w) > 1]
        
        if not query_words:
            # Fallback to general tokens if everything is a stopword
            query_words = [w for w in query_cleaned.split() if len(w) > 0]

        scored_chunks = []
        for chunk in self.chunks:
            content_cleaned = self.clean_text(chunk["content"])
            source_cleaned = self.clean_text(chunk["source"])
            
            score = 0.0
            
            # 1. Exact match bonus
            if query_cleaned in content_cleaned:
                score += 5.0
            
            # 2. Term overlap score
            matched_words = 0
            for qw in query_words:
                if qw in content_cleaned:
                    matched_words += 1
                    # Give higher weight to words that are less common (basic TF-IDF style, long words get slightly more weight)
                    score += 1.0 + (len(qw) * 0.1)
                
                # Bonus if the word appears in the filename/source name
                if qw in source_cleaned:
                    score += 2.0
            
            # 3. Ratio of matched query words
            if query_words:
                overlap_ratio = matched_words / len(query_words)
                score += overlap_ratio * 3.0

            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Format results
        results = []
        for score, chunk in scored_chunks[:top_k]:
            results.append({
                "score": round(score, 2),
                "id": chunk["id"],
                "source": chunk["source"],
                "content": chunk["content"],
                "type": chunk["type"],
                "position": chunk["position"]
            })
            
        return results
