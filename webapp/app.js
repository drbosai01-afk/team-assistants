// Утилиты для Mini App

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMessage(m) {
    const time = new Date(m.ts).toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'});
    return `<div class="message ${m.role}">${escapeHtml(m.content)}<div class="meta">${time}</div></div>`;
}

function showTyping(container, agentName) {
    const id = 'typing-' + Date.now();
    container.insertAdjacentHTML('beforeend', `<div class="message assistant" id="${id}"><em>${agentName} печатает...</em></div>`);
    return id;
}

function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// Авто-рост textarea
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// Прокрутка чата вниз
function scrollDown(container) {
    setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
}
