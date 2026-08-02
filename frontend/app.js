// Constants and State
const API_BASE = window.location.origin;
let chatHistory = [];
let selectedFile = null;

// DOM Elements
const navItems = document.querySelectorAll('.nav-item');
const tabContents = document.querySelectorAll('.tab-content');
const apiStatusText = document.getElementById('api-status-text');
const apiStatusDot = document.querySelector('.status-dot');

// Chat Elements
const chatMessagesContainer = document.getElementById('chat-messages-container');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const btnClearChat = document.getElementById('btn-clear-chat');

// KB Elements
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const selectedFileName = document.getElementById('selected-file-name');
const btnUpload = document.getElementById('btn-upload');
const documentListBody = document.getElementById('document-list-body');
const statDocsCount = document.getElementById('stat-docs-count');
const statChunksCount = document.getElementById('stat-chunks-count');
const kbBadgeCount = document.getElementById('kb-badge-count');

// Settings Elements
const geminiApiKeyInput = document.getElementById('gemini-api-key');
const btnSaveSettings = document.getElementById('btn-save-settings');
const toggleApiKeyBtn = document.getElementById('toggle-api-key');

// Toast Element
const toast = document.getElementById('toast');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSettings();
    initChat();
    initKB();
    checkAPIStatus();
    loadDocuments(); // Initial load of KB
});

// Toast System
function showToast(message, type = 'info') {
    toast.className = 'toast';
    toast.textContent = message;
    toast.classList.add(type);
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3500);
}

// Check Connection Status
async function checkAPIStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/documents`);
        if (res.ok) {
            apiStatusText.textContent = "Conectado ao Servidor";
            apiStatusDot.className = "status-dot online";
        } else {
            throw new Error();
        }
    } catch (e) {
        apiStatusText.textContent = "Erro de Conexão";
        apiStatusDot.className = "status-dot offline";
        showToast("Não foi possível conectar ao servidor backend.", "danger");
    }
}

// 1. Navigation Logic
function initNavigation() {
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');
            
            // Toggle active menu item
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            
            // Toggle active content section
            tabContents.forEach(content => {
                if (content.id === targetTab) {
                    content.classList.add('active');
                } else {
                    content.classList.remove('active');
                }
            });
            
            // If switched to KB, refresh documents
            if (targetTab === 'kb-tab') {
                loadDocuments();
            }
        });
    });
}

// 2. Settings Logic (Gemini API Key)
function initSettings() {
    // Load stored key
    const storedKey = localStorage.getItem('gemini_api_key');
    if (storedKey) {
        geminiApiKeyInput.value = storedKey;
    }

    // Toggle password visibility
    toggleApiKeyBtn.addEventListener('click', () => {
        const type = geminiApiKeyInput.getAttribute('type') === 'password' ? 'text' : 'password';
        geminiApiKeyInput.setAttribute('type', type);
        
        // Toggle icon visual states by changing internal SVG or coloring
        toggleApiKeyBtn.classList.toggle('active');
        if (type === 'text') {
            toggleApiKeyBtn.style.color = 'var(--color-primary-hover)';
        } else {
            toggleApiKeyBtn.style.color = 'var(--color-text-muted)';
        }
    });

    // Save key
    btnSaveSettings.addEventListener('click', () => {
        const keyVal = geminiApiKeyInput.value.trim();
        if (keyVal) {
            localStorage.setItem('gemini_api_key', keyVal);
            showToast("Configurações salvas com sucesso!", "success");
        } else {
            localStorage.removeItem('gemini_api_key');
            showToast("Chave de API removida.", "info");
        }
    });
}

// 3. Chat Logic
function initChat() {
    // Auto resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = (chatInput.scrollHeight) + 'px';
    });

    // Submit form (Enter triggers send, Shift+Enter new line)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.requestSubmit();
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message) return;

        // Reset input height & value
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // Add user message to UI & history
        appendMessage('user', message);
        chatHistory.push({ role: 'user', content: message });

        // Add typing indicator
        const typingId = appendTypingIndicator();
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;

        // Call backend API
        try {
            const apiKey = localStorage.getItem('gemini_api_key');
            const response = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    history: chatHistory.slice(0, -1), // Send previous history
                    apiKey: apiKey || null
                })
            });

            // Remove typing indicator
            removeTypingIndicator(typingId);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Erro ao gerar resposta.");
            }

            const data = await response.json();
            
            // Append assistant response
            appendMessage('system', data.answer, data.sources);
            
            if (data.success) {
                chatHistory.push({ role: 'model', content: data.answer });
            }
        } catch (error) {
            removeTypingIndicator(typingId);
            appendMessage('system', `❌ **Erro:** ${error.message || "Ocorreu um erro ao processar sua pergunta. Tente novamente."}`);
        }

        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    });

    // Clear Chat History
    btnClearChat.addEventListener('click', () => {
        chatMessagesContainer.innerHTML = '';
        chatHistory = [];
        
        // Restore initial welcome message
        appendMessage('system', 
            `Olá! Eu sou o **PrimeAssist AI**, o assistente oficial de inteligência artificial da **PrimePharma**.\n` +
            `Consigo consultar documentos, políticas, tabelas de preço e estoque para responder suas dúvidas com precisão.\n\n` +
            `Como posso ajudar você hoje? Experimente perguntar algo como:\n` +
            `- *\"Qual é a política de devolução de medicamentos termolábeis?\"*\n` +
            `- *\"Tem Ritalina ou Amoxicilina em estoque? Quais os preços e se exige receita?\"*\n` +
            `- *\"Como posso entrar em contato com o SAC ou Ouvidoria da empresa?\"*`
        );
        showToast("Conversa limpa.", "info");
    });
}

// Chat Helpers
function appendMessage(sender, text, sources = []) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    if (sender === 'user') {
        avatarDiv.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
        `;
    } else {
        avatarDiv.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                <line x1="12" y1="22.08" x2="12" y2="12"></line>
            </svg>
        `;
    }

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'message-body';

    const senderName = document.createElement('div');
    senderName.className = 'message-sender';
    senderName.textContent = sender === 'user' ? 'Você' : 'PrimeAssist AI';

    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.innerHTML = parseMarkdown(text);

    bodyDiv.appendChild(senderName);
    bodyDiv.appendChild(textDiv);

    // If sources are present, render them
    if (sources && sources.length > 0) {
        const sourcesWrapper = document.createElement('div');
        sourcesWrapper.className = 'sources-container';
        
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'sources-toggle';
        toggleBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
            Fontes e Referências Oficiais (${sources.length})
        `;
        
        const sourcesList = document.createElement('div');
        sourcesList.className = 'sources-list';
        
        sources.forEach((src) => {
            const item = document.createElement('div');
            item.className = 'source-item';
            item.innerHTML = `
                <div class="source-header">
                    <span class="source-name">📄 ${src.source}</span>
                    <span class="source-position">${src.position} (Relevância: ${src.score})</span>
                </div>
                <div class="source-body">${src.content}</div>
            `;
            sourcesList.appendChild(item);
        });
        
        toggleBtn.addEventListener('click', () => {
            toggleBtn.classList.toggle('open');
            sourcesList.classList.toggle('open');
        });
        
        sourcesWrapper.appendChild(toggleBtn);
        sourcesWrapper.appendChild(sourcesList);
        bodyDiv.appendChild(sourcesWrapper);
    }

    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(bodyDiv);
    chatMessagesContainer.appendChild(msgDiv);
}

function appendTypingIndicator() {
    const id = 'typing-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system typing-indicator';
    msgDiv.id = id;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
            <line x1="12" y1="22.08" x2="12" y2="12"></line>
        </svg>
    `;

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'message-body';

    const senderName = document.createElement('div');
    senderName.className = 'message-sender';
    senderName.textContent = 'PrimeAssist AI';

    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.innerHTML = `<span style="color:var(--color-text-muted)">Consultando documentos e formulando resposta...</span>`;

    bodyDiv.appendChild(senderName);
    bodyDiv.appendChild(textDiv);
    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(bodyDiv);
    chatMessagesContainer.appendChild(msgDiv);
    return id;
}

function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// Simple Markdown parser (safe and custom)
function parseMarkdown(text) {
    let html = text;
    // Escaping basic HTML to prevent injection
    html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italics
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/_(.*?)_/g, '<em>$1</em>');
    
    // Lists
    html = html.replace(/^\s*-\s+(.*?)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*?<\/li>)/s, '<ul>$1</ul>'); // wrap sequential list items in ul
    
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    
    return html;
}

// 4. Knowledge Base (KB) Logic
function initKB() {
    // Dropzone events
    dropzone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    // Upload Action
    btnUpload.addEventListener('click', async () => {
        if (!selectedFile) return;

        btnUpload.disabled = true;
        btnUpload.textContent = "Processando arquivo...";

        const formData = new FormData();
        formData.append("file", selectedFile);

        try {
            const res = await fetch(`${API_BASE}/api/upload`, {
                method: "POST",
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Erro no upload.");
            }

            showToast("Documento indexado com sucesso!", "success");
            resetDropzone();
            loadDocuments();
        } catch (e) {
            showToast(`Erro ao indexar arquivo: ${e.message}`, "danger");
            btnUpload.disabled = false;
            btnUpload.textContent = "Indexar Arquivo";
        }
    });
}

function handleFileSelect(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const allowed = ['txt', 'csv', 'xlsx', 'xls'];
    
    if (!allowed.includes(ext)) {
        showToast("Formato inválido. Escolha apenas arquivos .txt, .csv ou .xlsx", "danger");
        resetDropzone();
        return;
    }

    selectedFile = file;
    selectedFileName.textContent = `📁 ${file.name} (${(file.size / 1024).toFixed(2)} KB)`;
    btnUpload.disabled = false;
    btnUpload.className = "btn btn-primary";
}

function resetDropzone() {
    selectedFile = null;
    fileInput.value = '';
    selectedFileName.textContent = '';
    btnUpload.disabled = true;
    btnUpload.textContent = "Indexar Arquivo";
}

// Fetch documents and load stats
async function loadDocuments() {
    try {
        const res = await fetch(`${API_BASE}/api/documents`);
        if (!res.ok) throw new Error();
        
        const docs = await res.json();
        renderDocumentsTable(docs);
        
        // Update stats
        statDocsCount.textContent = docs.length;
        kbBadgeCount.textContent = docs.length;
        
        // Calculate total chunks/lines
        let totalItems = 0;
        docs.forEach(d => {
            const match = d.items.match(/^(\d+)/);
            if (match) {
                totalItems += parseInt(match[1], 10);
            }
        });
        statChunksCount.textContent = totalItems;
        
    } catch (e) {
        showToast("Erro ao buscar documentos da base.", "danger");
    }
}

function renderDocumentsTable(docs) {
    if (docs.length === 0) {
        documentListBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-table">Nenhum documento indexado. Adicione arquivos para alimentar o cérebro da IA!</td>
            </tr>
        `;
        return;
    }

    documentListBody.innerHTML = '';
    docs.forEach(doc => {
        const tr = document.createElement('tr');
        
        // Format icon based on type
        let iconHtml = '';
        if (doc.filename.endsWith('.csv')) {
            iconHtml = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="doc-icon" style="color: #10b981">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
            `;
        } else if (doc.filename.endsWith('.xlsx') || doc.filename.endsWith('.xls')) {
            iconHtml = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="doc-icon" style="color: #10b981">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
            `;
        } else {
            iconHtml = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="doc-icon" style="color: #3b82f6">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
            `;
        }

        tr.innerHTML = `
            <td>
                <div class="doc-icon-wrapper">
                    ${iconHtml}
                    <span>${doc.filename}</span>
                </div>
            </td>
            <td>${doc.type}</td>
            <td>${doc.size}</td>
            <td>${doc.items}</td>
            <td>
                <button class="btn-delete-doc" data-filename="${doc.filename}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        <line x1="10" y1="11" x2="10" y2="17"></line>
                        <line x1="14" y1="11" x2="14" y2="17"></line>
                    </svg>
                </button>
            </td>
        `;

        // Delete Event
        tr.querySelector('.btn-delete-doc').addEventListener('click', (e) => {
            const filename = e.currentTarget.getAttribute('data-filename');
            confirmDelete(filename);
        });

        documentListBody.appendChild(tr);
    });
}

async function confirmDelete(filename) {
    if (confirm(`Tem certeza que deseja remover o documento "${filename}" da base de conhecimento da IA?`)) {
        try {
            const res = await fetch(`${API_BASE}/api/documents/${filename}`, {
                method: 'DELETE'
            });

            if (!res.ok) throw new Error();

            showToast("Documento deletado e base re-indexada.", "success");
            loadDocuments();
        } catch (e) {
            showToast("Erro ao deletar documento.", "danger");
        }
    }
}
