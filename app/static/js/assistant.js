/**
 * DocuMind AI — Financial Assistant Copilot Module
 * Handles:
 * - Asynchronous communication with POST /api/assistant/ask & GET /api/assistant/history
 * - User and Assistant message rendering with XSS sanitization
 * - Verified evidence breakdown, source document cards, anomaly badges, and metric cards
 * - Suggested question prompt selection
 * - Conversation history sidebar and mobile drawer toggle
 * - Smooth auto-scrolling, loading indicators, and error handling
 */

document.addEventListener('DOMContentLoaded', () => {
    const chatThread = document.getElementById('chatThread');
    const emptyState = document.getElementById('emptyState');
    const chatForm = document.getElementById('assistantForm');
    const chatInput = document.getElementById('assistantInput');
    const btnSend = document.getElementById('btnSendAssistant');
    const btnNewChat = document.getElementById('btnNewChat');
    const historyList = document.getElementById('historyList');
    const convDrawerToggle = document.getElementById('convDrawerToggle');
    const historySidebar = document.getElementById('historySidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    if (!chatThread || !chatForm || !chatInput) return;

    let isLoading = false;

    // Helper: CSRF token retrieval from meta tag
    const getCsrfToken = () => {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    };

    // Helper: HTML Escaping for XSS Safety
    const escapeHtml = (str) => {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    };

    // Helper: Auto scroll chat thread to bottom
    const scrollToBottom = () => {
        setTimeout(() => {
            chatThread.scrollTop = chatThread.scrollHeight;
        }, 50);
    };

    // Mobile drawer toggle handlers
    const openHistoryDrawer = () => {
        if (historySidebar) historySidebar.classList.add('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.add('show');
    };

    const closeHistoryDrawer = () => {
        if (historySidebar) historySidebar.classList.remove('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
    };

    if (convDrawerToggle) {
        convDrawerToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            if (historySidebar && historySidebar.classList.contains('open')) {
                closeHistoryDrawer();
            } else {
                openHistoryDrawer();
            }
        });
    }

    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', closeHistoryDrawer);
    }

    let currentConversationId = null;

    // Load conversation history on initial view
    const loadHistory = async () => {
        if (!historyList) return;
        try {
            const res = await fetch('/api/assistant/history', {
                headers: { 'Accept': 'application/json' }
            });
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'success') {
                const conversations = data.conversations || [];
                renderHistoryItems(conversations);
            }
        } catch (err) {
            console.warn('Could not load assistant conversations:', err);
        }
    };

    // Render history sidebar conversation items
    const renderHistoryItems = (conversations) => {
        if (!historyList) return;
        historyList.innerHTML = '';

        if (!Array.isArray(conversations) || conversations.length === 0) {
            historyList.innerHTML = '<div style="color: var(--muted); font-size: 12px; padding: 10px 4px;">No previous conversations.</div>';
            return;
        }

        conversations.forEach(conv => {
            const el = document.createElement('div');
            const isActive = conv.conversation_id === currentConversationId;
            el.className = 'history-item' + (isActive ? ' active' : '');
            el.setAttribute('title', conv.first_question || conv.title);
            el.setAttribute('data-conv-id', conv.conversation_id);
            
            el.innerHTML = `
                <div style="font-weight: 600; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                    💬 ${escapeHtml(conv.title || 'Financial Analysis')}
                </div>
                <small style="color: var(--muted); font-size: 10.5px; display: block; margin-top: 2px;">
                    ${escapeHtml(conv.last_updated || '')}
                </small>
            `;
            
            el.addEventListener('click', () => {
                selectConversation(conv.conversation_id);
            });

            historyList.appendChild(el);
        });
    };

    // Select and load an existing conversation thread
    const selectConversation = async (convId) => {
        if (!convId) return;
        currentConversationId = convId;

        // Visual update on sidebar
        document.querySelectorAll('.history-item').forEach(item => {
            if (item.getAttribute('data-conv-id') === convId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        closeHistoryDrawer();

        try {
            const res = await fetch(`/api/assistant/conversation/${convId}`, {
                headers: { 'Accept': 'application/json' }
            });
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'success' && Array.isArray(data.messages)) {
                // Clear existing bubbles
                chatThread.querySelectorAll('.bubble').forEach(b => b.remove());
                if (emptyState) emptyState.style.display = 'none';

                // Render conversation messages chronologically
                data.messages.forEach(msg => {
                    if (msg.role === 'user') {
                        appendUserMessage(msg.message);
                    } else if (msg.role === 'assistant') {
                        appendAssistantMessage({
                            status: 'success',
                            intent: 'ASSISTANT_RESPONSE',
                            answer: msg.message,
                            facts: {},
                            sources: []
                        });
                    }
                });

                // Input remains empty as required
                chatInput.value = '';
                chatInput.focus();
                scrollToBottom();
            }
        } catch (err) {
            console.error('Error loading conversation messages:', err);
        }
    };

    // Render User Message Bubble
    const appendUserMessage = (text) => {
        if (emptyState) emptyState.style.display = 'none';

        const bubble = document.createElement('div');
        bubble.className = 'bubble user-bubble';
        bubble.innerHTML = `
            <div class="bubble-content">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
        `;
        chatThread.appendChild(bubble);
        scrollToBottom();
    };

    // Render Loading Bubble
    const showLoadingBubble = () => {
        const loading = document.createElement('div');
        loading.id = 'assistantLoadingBubble';
        loading.className = 'bubble ai-bubble loading-bubble';
        loading.innerHTML = `
            <div class="ai-avatar">✦</div>
            <div class="bubble-content">
                <div class="pulsating-dots">
                    <span></span><span></span><span></span>
                </div>
                <small style="color: var(--muted); font-size: 12px; display: block; margin-top: 6px;">
                    DocuMind is retrieving verified financial evidence...
                </small>
            </div>
        `;
        chatThread.appendChild(loading);
        scrollToBottom();
    };

    const removeLoadingBubble = () => {
        const el = document.getElementById('assistantLoadingBubble');
        if (el) el.remove();
    };

    // Format badge based on response status & intent
    const renderStatusBadge = (status, intent, llmUsed) => {
        if (status === 'insufficient_data') {
            return `<span class="evidence-badge status-warning">⚠ INSUFFICIENT DATA</span>`;
        }
        if (status === 'not_found' || status === 'unauthorized') {
            return `<span class="evidence-badge status-muted">◈ RECORD NOT FOUND</span>`;
        }
        if (status === 'error') {
            return `<span class="evidence-badge status-danger">✖ SYSTEM ALERT</span>`;
        }
        if (intent === 'ANOMALIES' || intent === 'DUPLICATE_DOCUMENTS' || intent === 'DOCUMENT_RISK') {
            return `<span class="evidence-badge status-danger">🛡 RISK SIGNAL VERIFIED</span>`;
        }
        if (llmUsed) {
            return `<span class="evidence-badge status-success">✦ AI-ASSISTED EVIDENCE</span>`;
        }
        return `<span class="evidence-badge status-success">✓ VERIFIED EVIDENCE</span>`;
    };

    // Render Evidence Breakdown & Source Document Cards
    const renderEvidenceDetails = (facts, sources, status, intent) => {
        if (status !== 'success') return '';

        let html = '';

        // 1. Facts Summary Box
        if (facts && Object.keys(facts).length > 0) {
            if (intent === 'TOTAL_SPENDING' && facts.total_spending !== undefined) {
                html += `
                    <div class="facts-summary-box">
                        <div class="fact-metric">
                            <span>TOTAL SPENDING</span>
                            <strong>₹${Number(facts.total_spending).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
                        </div>
                        <div class="fact-metric">
                            <span>ANALYZED DOCUMENTS</span>
                            <strong>${facts.analyzed_documents || 0}</strong>
                        </div>
                        <div class="fact-metric">
                            <span>AVG TRANSACTION</span>
                            <strong>₹${Number(facts.average_transaction || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
                        </div>
                    </div>
                `;
            } else if (intent === 'DUE_DILIGENCE' && facts.overall_score !== undefined) {
                html += `
                    <div class="facts-summary-box">
                        <div class="fact-metric">
                            <span>AUDIT HEALTH INDEX</span>
                            <strong style="color: ${facts.overall_score >= 80 ? '#177e61' : '#ad710e'};">${facts.overall_score}/100</strong>
                        </div>
                        <div class="fact-metric">
                            <span>COMPLETENESS</span>
                            <strong>${facts.completeness_score}%</strong>
                        </div>
                        <div class="fact-metric">
                            <span>CONSISTENCY</span>
                            <strong>${facts.consistency_score}%</strong>
                        </div>
                    </div>
                `;
            }
        }

        // 2. Source Document Cards Grid
        if (Array.isArray(sources) && sources.length > 0) {
            html += `
                <div style="margin-top: 14px;">
                    <div style="font-size: 11px; font-weight: 800; color: var(--muted); letter-spacing: 0.6px; margin-bottom: 8px;">
                        VERIFIED SOURCE DOCUMENTS (${sources.length})
                    </div>
                    <div class="source-cards-grid">
            `;

            sources.forEach(src => {
                const docId = src.document_id;
                const filename = escapeHtml(src.original_filename || 'Document');
                const vendor = escapeHtml(src.vendor_name || 'Vendor Unspecified');
                const invNum = escapeHtml(src.invoice_number ? `#${src.invoice_number}` : `ID: ${docId}`);
                const amount = Number(src.total_amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2});

                html += `
                    <div class="source-card">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                            <span class="doc-badge">${escapeHtml(src.file_type ? src.file_type.split('/').pop().toUpperCase() : 'DOC')}</span>
                            <strong style="color: var(--blue); font-size: 13px;">₹${amount}</strong>
                        </div>
                        <div style="font-weight: 700; color: var(--ink); font-size: 12.5px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                            ${filename}
                        </div>
                        <div style="color: var(--muted); font-size: 11.5px; margin: 2px 0 8px;">
                            ${vendor} · ${invNum}
                        </div>
                        <a href="/documents/${docId}" class="source-link">View document ➔</a>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        }

        return html;
    };

    // Render Assistant Response Bubble
    const appendAssistantMessage = (response) => {
        const bubble = document.createElement('div');
        bubble.className = 'bubble ai-bubble';

        const status = response.status || 'success';
        const intent = response.intent || 'UNKNOWN';
        const answerText = escapeHtml(response.answer || '').replace(/\n/g, '<br>');
        const badgeHtml = renderStatusBadge(status, intent);
        const evidenceHtml = renderEvidenceDetails(response.facts, response.sources, status, intent);

        bubble.innerHTML = `
            <div class="ai-avatar">✦</div>
            <div class="bubble-content">
                <div class="bubble-header">
                    <span class="ai-name">DocuMind Copilot</span>
                    ${badgeHtml}
                </div>
                <div class="answer-text">${answerText}</div>
                ${evidenceHtml}
            </div>
        `;

        chatThread.appendChild(bubble);
        scrollToBottom();
    };

    // Main submit question handler
    const askQuestion = async (questionText) => {
        if (!questionText || isLoading) return;

        const text = questionText.trim();
        if (text.length === 0 || text.length > 500) return;

        isLoading = true;
        if (btnSend) btnSend.disabled = true;
        if (chatInput) chatInput.disabled = true;

        // 1. Render User Message
        appendUserMessage(text);
        chatInput.value = '';

        // 2. Render Pulsating Loading
        showLoadingBubble();

        try {
            // 3. API Fetch with conversation_id payload
            const payload = { question: text };
            if (currentConversationId) {
                payload.conversation_id = currentConversationId;
            }

            const res = await fetch('/api/assistant/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify(payload)
            });

            removeLoadingBubble();

            if (res.ok) {
                const data = await res.json();
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                }
                appendAssistantMessage(data);
            } else {
                const errorData = await res.json().catch(() => ({}));
                appendAssistantMessage({
                    status: 'error',
                    intent: 'UNKNOWN',
                    answer: errorData.answer || "I couldn't process that financial request right now. Please try again.",
                    facts: {},
                    sources: []
                });
            }
        } catch (err) {
            removeLoadingBubble();
            console.error('Error sending assistant request:', err);
            appendAssistantMessage({
                status: 'error',
                intent: 'UNKNOWN',
                answer: "A network error occurred while connecting to the assistant. Please check your connection and retry.",
                facts: {},
                sources: []
            });
        } finally {
            isLoading = false;
            if (btnSend) btnSend.disabled = false;
            if (chatInput) {
                chatInput.disabled = false;
                chatInput.focus();
            }
            loadHistory();
        }
    };

    // Bind form submit
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        askQuestion(chatInput.value);
    });

    // Handle Enter key vs Shift+Enter
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Bind Suggested Question Cards Click
    const suggestedCards = document.querySelectorAll('.suggested-card');
    suggestedCards.forEach(card => {
        card.addEventListener('click', () => {
            const prompt = card.getAttribute('data-prompt') || card.textContent.trim();
            askQuestion(prompt);
        });
    });

    // New Conversation Button Click
    if (btnNewChat) {
        btnNewChat.addEventListener('click', (e) => {
            e.preventDefault();
            currentConversationId = null;
            document.querySelectorAll('.history-item').forEach(item => item.classList.remove('active'));
            // Clear current thread and show empty state
            chatThread.querySelectorAll('.bubble').forEach(b => b.remove());
            if (emptyState) emptyState.style.display = 'block';
            chatInput.value = '';
            chatInput.focus();
            closeHistoryDrawer();
        });
    }

    // Initial load
    loadHistory();
});
