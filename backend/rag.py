import os
import re
import unicodedata
import pandas as pd
from typing import List, Dict, Any

class RAGEngine:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.chunks = []  # List[Dict[str, Any]] -> { "id": int, "source": str, "content": str, "type": str, "position": str, "keywords": str }
        self.dataframes = {}  # Dict[str, pd.DataFrame]
        self.stop_words = {
            "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
            "em", "no", "na", "nos", "nas", "para", "por", "com", "sem", "sob", "sobre", "e", "ou",
            "que", "se", "como", "esta", "este", "isto", "esse", "isso", "aquele", "aquilo", "qual",
            "quais", "quem", "quando", "onde", "porque", "por que", "tem", "ha", "foi", "foram", "sao", "ser"
        }
        self.load_documents()

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalizes text by removing accents, lowercasing, and stripping special characters."""
        if not text:
            return ""
        # Remove accents
        text_norm = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
        text_norm = text_norm.lower()
        # Replace non-alphanumeric with spaces
        text_norm = re.sub(r'[^a-z0-9\s]', ' ', text_norm)
        return " ".join(text_norm.split())

    def clean_text(self, text: str) -> str:
        return self.normalize_text(text)

    def load_documents(self):
        """Loads and processes all files from the data directory into structured RAG chunks."""
        self.chunks = []
        self.dataframes = {}
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            return

        chunk_id = 0
        for filename in sorted(os.listdir(self.data_dir)):
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

        sections = [s.strip() for s in content.split('\n\n') if s.strip()]
        
        for idx, section in enumerate(sections):
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
                    "position": f"Seção {idx + 1}",
                    "keywords": self.normalize_text(sub)
                })
                chunk_id += 1
        return chunk_id

    def _df_to_markdown(self, df: pd.DataFrame) -> str:
        """Converts a pandas DataFrame to a clean Markdown table string without external tabulate dependency."""
        headers = [str(c).strip() for c in df.columns]
        header_line = "| " + " | ".join(headers) + " |"
        separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
        rows = []
        for _, row in df.iterrows():
            row_str = "| " + " | ".join([str(row[c]).strip() if pd.notna(row[c]) else "" for c in df.columns]) + " |"
            rows.append(row_str)
        return "\n".join([header_line, separator_line] + rows)

    def _parse_csv(self, filepath: str, filename: str, start_id: int) -> int:
        # Read CSV with encoding and delimiter fallback
        df = None
        for enc in ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']:
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding=enc)
                break
            except Exception:
                continue
        
        if df is None:
            # Fallback to standard comma
            df = pd.read_csv(filepath, encoding='utf-8', errors='ignore')

        return self._process_dataframe(df, filename, start_id)

    def _parse_xlsx(self, filepath: str, filename: str, start_id: int) -> int:
        df = pd.read_excel(filepath)
        return self._process_dataframe(df, filename, start_id)

    def _process_dataframe(self, df: pd.DataFrame, filename: str, start_id: int) -> int:
        chunk_id = start_id
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        self.dataframes[filename] = df

        # 1. Generate Table Summary Chunk
        cols_str = ", ".join(df.columns.tolist())
        row_count = len(df)
        
        # Extract unique categories or products if available
        summary_details = []
        for col in df.columns:
            norm_col = self.normalize_text(col)
            if any(k in norm_col for k in ["mes", "categoria", "unidade"]):
                unique_vals = [str(v) for v in df[col].dropna().unique().tolist()[:10]]
                summary_details.append(f"{col}: {', '.join(unique_vals)}")
        
        summary_text = (
            f"Tabela/Planilha: {filename}\n"
            f"Total de Registros: {row_count} linhas\n"
            f"Colunas disponíveis: {cols_str}\n"
        )
        if summary_details:
            summary_text += "Amostras/Categorias: " + " | ".join(summary_details) + "\n"

        self.chunks.append({
            "id": chunk_id,
            "source": filename,
            "content": summary_text.strip(),
            "type": "Resumo de Planilha",
            "position": "Metadados da Tabela",
            "keywords": self.normalize_text(summary_text + " " + " ".join([str(v) for v in df.values.flatten() if pd.notna(v)]))
        })
        chunk_id += 1

        # 2. Generate Full or Segmented Markdown Table Chunks
        # If <= 120 rows, one complete table chunk gives the LLM full global analytical capability (sums, mins, maxes, rankings)
        if row_count <= 120:
            md_table = self._df_to_markdown(df)
            full_content = (
                f"### DADOS COMPLETOS DA PLANILHA: `{filename}` ({row_count} registros)\n\n"
                f"{md_table}"
            )
            self.chunks.append({
                "id": chunk_id,
                "source": filename,
                "content": full_content,
                "type": "Tabela Completa (CSV/Excel)",
                "position": f"Tabela Completa (Linhas 1 a {row_count})",
                "keywords": self.normalize_text(filename + " " + cols_str + " " + " ".join([str(v) for v in df.values.flatten() if pd.notna(v)]))
            })
            chunk_id += 1
        else:
            # Segment large tables in blocks of 50 rows, preserving headers
            block_size = 50
            for start_row in range(0, row_count, block_size):
                end_row = min(start_row + block_size, row_count)
                sub_df = df.iloc[start_row:end_row]
                md_table = self._df_to_markdown(sub_df)
                block_content = (
                    f"### PLANILHA `{filename}` (Registros {start_row + 1} a {end_row} de {row_count})\n\n"
                    f"{md_table}"
                )
                self.chunks.append({
                    "id": chunk_id,
                    "source": filename,
                    "content": block_content,
                    "type": "Bloco de Planilha",
                    "position": f"Linhas {start_row + 1}-{end_row}",
                    "keywords": self.normalize_text(filename + " " + cols_str + " " + " ".join([str(v) for v in sub_df.values.flatten() if pd.notna(v)]))
                })
                chunk_id += 1

        # 3. Generate Individual Row Chunks for precise item lookups
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
                "content": f"Registro {idx + 1}: {row_content}",
                "type": "Registro de Planilha",
                "position": f"Linha {idx + 1}",
                "keywords": self.normalize_text(f"{filename} {row_content}")
            })
            chunk_id += 1
            
        return chunk_id

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

            text_cleaned = re.sub(r'\s+', ' ', text).strip()
            if not text_cleaned:
                continue

            # Split in sections of up to 800 chars
            max_chars = 800
            start = 0
            subsections = []
            while start < len(text_cleaned):
                end = start + max_chars
                if end >= len(text_cleaned):
                    subsections.append(text_cleaned[start:])
                    break
                
                limit = max(start, end - 150)
                split_pos = -1
                for p in range(end, limit - 1, -1):
                    if text_cleaned[p] in ['.', '!', '?'] and p + 1 < len(text_cleaned) and text_cleaned[p+1] == ' ':
                        split_pos = p + 1
                        break
                
                if split_pos == -1:
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
                    "position": f"Pág. {page_num + 1}" + (f", Parte {idx + 1}" if len(subsections) > 1 else ""),
                    "keywords": self.normalize_text(f"{filename} {sub}")
                })
                chunk_id += 1
        return chunk_id

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieves the most relevant chunks using normalized term matching, phrase detection, and table intelligence."""
        if not self.chunks:
            return []

        query_norm = self.normalize_text(query)
        query_words = [w for w in query_norm.split() if w not in self.stop_words and len(w) > 1]
        
        if not query_words:
            query_words = [w for w in query_norm.split() if len(w) > 0]

        # Table-related intent indicators
        sales_keywords = {"venda", "vendas", "vendido", "vendidos", "faturamento", "receita", "mes", "abril", "maio", "junho", "trimestre"}
        stock_keywords = {"estoque", "quantidade", "unidade", "unidades", "lote", "lotes", "validade", "validades", "critico", "minimo"}
        general_table_keywords = {"planilha", "tabela", "csv", "excel", "relatorio", "categoria", "categorias", "produto", "produtos", "medicamento", "medicamentos", "generico", "genericos", "suplemento", "dermocosmetico", "higiene", "infantil", "equipamento"}
        
        is_sales_query = any(k in query_norm for k in sales_keywords)
        is_stock_query = any(k in query_norm for k in stock_keywords)
        is_table_query = is_sales_query or is_stock_query or any(k in query_norm for k in general_table_keywords)

        scored_chunks = []
        for chunk in self.chunks:
            chunk_type = chunk.get("type", "")
            chunk_keywords = chunk.get("keywords", "")
            source_norm = self.normalize_text(chunk["source"])
            
            score = 0.0

            # 1. Exact query phrase match
            if query_norm in chunk_keywords:
                score += 8.0

            # 2. Term overlap matching
            matched_words = 0
            for qw in query_words:
                if qw in chunk_keywords:
                    matched_words += 1
                    # Weight by word length
                    score += 1.5 + (len(qw) * 0.15)
                
                # Bonus if term matches filename/source
                if qw in source_norm:
                    score += 1.5

            # Overlap ratio bonus
            if query_words:
                overlap_ratio = matched_words / len(query_words)
                score += overlap_ratio * 4.0

            # 3. Intelligent Table Chunk Boosting:
            # If the user asks about sales or general sales report, boost Plan01 complete table
            if ("Tabela Completa" in chunk_type or "Resumo de Planilha" in chunk_type):
                if is_sales_query and "vendas" in source_norm:
                    score += 15.0
                elif is_stock_query and "estoque" in source_norm:
                    score += 15.0
                elif is_table_query and matched_words > 0:
                    score += 10.0

            # If user asks specific question matching individual product in row
            if "Registro de Planilha" in chunk_type and matched_words >= 2:
                score += 3.0

            if score > 0.5:
                scored_chunks.append((score, chunk))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        # Select top chunks with deduplication
        results = []
        seen_contents = set()
        
        for score, chunk in scored_chunks:
            # Short signature to avoid identical duplicate blocks
            sig = chunk["content"][:100]
            if sig in seen_contents:
                continue
            seen_contents.add(sig)

            results.append({
                "score": round(score, 2),
                "id": chunk["id"],
                "source": chunk["source"],
                "content": chunk["content"],
                "type": chunk["type"],
                "position": chunk["position"]
            })

            if len(results) >= top_k:
                break

        return results
