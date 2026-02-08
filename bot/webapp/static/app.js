// ==================== INIT ====================
const tg = window.Telegram?.WebApp;
let currentUser = null;
let allFeedOrders = [];
let allCrmOrders = [];

const API_BASE = '';

const CATEGORIES = {
    python: '🐍 Python',
    web: '🌐 Веб',
    design: '🎨 Дизайн',
    copywriting: '✍️ Копирайтинг',
    mobile: '📱 Мобильные',
    marketing: '📊 Маркетинг',
    data: '📈 Данные',
    devops: '⚙️ DevOps'
};

const STATUS_LABELS = {
    new: '🆕 Новый',
    responded: '✉️ Откликнулся',
    in_progress: '⚙️ В работе',
    completed: '✅ Завершён',
    cancelled: '❌ Отменён'
};

const SOURCE_EMOJI = {
    kwork: '🟢', fl: '🔵', habr: '🟠',
    hh: '🔴', telegram: '✈️',
    freelance_ru: '🟡', weblancer: '🟣'
};

// Init
document.addEventListener('DOMContentLoaded', async () => {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.setHeaderColor('#1a1a2e');
        tg.setBackgroundColor('#1a1a2e');
    }

    await loadUser();
    await loadFeed();
    hideLoading();
});

function hideLoading() {
    const el = document.getElementById('loadingScreen');
    el.classList.add('hidden');
    setTimeout(() => el.style.display = 'none', 300);
}

function getTelegramId() {
    if (tg?.initDataUnsafe?.user?.id) {
        return tg.initDataUnsafe.user.id;
    }
    // Fallback для тестирования
    const params = new URLSearchParams(window.location.search);
    return params.get('user_id') || 0;
}

// ==================== API ====================
async function apiGet(url) {
    try {
        const res = await fetch(`${API_BASE}${url}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error('API GET error:', e);
        return null;
    }
}

async function apiPost(url, data) {
    try {
        const res = await fetch(`${API_BASE}${url}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error('API POST error:', e);
        return null;
    }
}

// ==================== USER ====================
async function loadUser() {
    const id = getTelegramId();
    if (!id) return;

    currentUser = await apiGet(`/webapp/api/user?telegram_id=${id}`);
    if (currentUser) {
        renderProfile();
        renderCategories();
    }
}

// ==================== TABS ====================
function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));

    document.getElementById(`tab-${tab}`).classList.add('active');
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

    // Загружаем данные при переключении
    if (tab === 'feed') loadFeed();
    if (tab === 'crm') loadCRM();
    if (tab === 'profile') loadUser();

    // Haptic feedback
    if (tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();

    // Закрываем все панели инструментов
    document.querySelectorAll('.tool-panel').forEach(p => p.style.display = 'none');
}

// ==================== FEED ====================
async function loadFeed() {
    const id = getTelegramId();
    if (!id) return;

    const orders = await apiGet(`/webapp/api/feed?telegram_id=${id}`);
    allFeedOrders = orders || [];
    renderFeed(allFeedOrders);
}

function renderFeed(orders) {
    const container = document.getElementById('feedList');

    if (!orders || orders.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📭</span>
                <p>Пока нет заказов. Запустите парсер!</p>
            </div>`;
        return;
    }

    container.innerHTML = orders.map(order => `
        <div class="order-card" onclick="openOrderModal(${JSON.stringify(order).replace(/"/g, '&quot;')})">
            <div class="order-source">
                <span>${SOURCE_EMOJI[order.source] || '📌'} ${order.source.toUpperCase()}</span>
                <span class="order-time">${formatTime(order.created_at)}</span>
            </div>
            <div class="order-title">${escapeHtml(order.title)}</div>
            ${order.description ? `<div class="order-desc">${escapeHtml(order.description)}</div>` : ''}
            <div class="order-footer">
                <span class="order-budget">${order.budget || 'Договорная'}</span>
                ${order.client_name ? `<span style="font-size:12px;color:var(--text-secondary)">👤 ${escapeHtml(order.client_name)}</span>` : ''}
            </div>
        </div>
    `).join('');
}

function filterFeed(source, btn) {
    document.querySelectorAll('#tab-feed .filter-chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');

    if (source === 'all') {
        renderFeed(allFeedOrders);
    } else {
        renderFeed(allFeedOrders.filter(o => o.source === source));
    }
}

// ==================== CRM ====================
async function loadCRM() {
    const id = getTelegramId();
    if (!id) return;

    allCrmOrders = await apiGet(`/webapp/api/orders?telegram_id=${id}`) || [];

    // Stats
    const stats = {
        total: allCrmOrders.length,
        in_progress: allCrmOrders.filter(o => o.status === 'in_progress').length,
        completed: allCrmOrders.filter(o => o.status === 'completed').length,
        earned: allCrmOrders.filter(o => o.status === 'completed').reduce((s, o) => s + (o.my_price || 0), 0)
    };

    document.getElementById('crmStats').innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${stats.total}</div>
            <div class="stat-label">Всего</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.in_progress}</div>
            <div class="stat-label">В работе</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.completed}</div>
            <div class="stat-label">Завершено</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${formatMoney(stats.earned)}</div>
            <div class="stat-label">Заработано</div>
        </div>
    `;

    renderCRM(allCrmOrders);
}

function renderCRM(orders) {
    const container = document.getElementById('crmList');

    if (!orders || orders.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📋</span>
                <p>В CRM пока пусто. Сохраняйте заказы из ленты!</p>
            </div>`;
        return;
    }

    container.innerHTML = orders.map(order => `
        <div class="order-card" onclick="openCRMModal(${order.id})">
            <div class="order-source">
                <span>${SOURCE_EMOJI[order.source] || '📌'} ${order.source.toUpperCase()}</span>
                <span class="order-status status-${order.status}">${STATUS_LABELS[order.status] || order.status}</span>
            </div>
            <div class="order-title">${escapeHtml(order.title)}</div>
            <div class="order-footer">
                <span class="order-budget">${order.budget || 'Договорная'}</span>
                ${order.my_price ? `<span style="color:var(--success);font-weight:700">💵 ${formatMoney(order.my_price)}</span>` : ''}
            </div>
            ${order.notes ? `<div style="font-size:12px;color:var(--text-secondary);margin-top:6px">📝 ${escapeHtml(order.notes).substring(0, 80)}</div>` : ''}
        </div>
    `).join('');
}

function filterCRM(status, btn) {
    document.querySelectorAll('#tab-crm .filter-chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');

    if (status === 'all') {
        renderCRM(allCrmOrders);
    } else {
        renderCRM(allCrmOrders.filter(o => o.status === status));
    }
}

// ==================== MODALS ====================
function openOrderModal(order) {
    const modal = document.getElementById('orderModal');
    document.getElementById('modalTitle').textContent = order.title;

    document.getElementById('modalBody').innerHTML = `
        <p><strong>Источник:</strong> ${SOURCE_EMOJI[order.source] || ''} ${order.source.toUpperCase()}</p>
        <p><strong>Бюджет:</strong> ${order.budget || 'Договорная'}</p>
        ${order.client_name ? `<p><strong>Заказчик:</strong> ${escapeHtml(order.client_name)}</p>` : ''}
        <hr style="border-color:var(--border);margin:12px 0">
        <p>${escapeHtml(order.description || 'Описание отсутствует')}</p>
    `;

    document.getElementById('modalActions').innerHTML = `
        ${order.url ? `<a href="${order.url}" target="_blank" class="btn-primary" style="text-align:center;text-decoration:none;display:block">🔗 Открыть заказ</a>` : ''}
        <button class="btn-secondary" onclick="generateResponseModal('${escapeHtml(order.title)}', '${escapeHtml((order.description || '').substring(0, 500))}')">✍️ Сгенерировать отклик</button>
        <button class="btn-secondary" onclick="saveToCRM('${order.hash || ''}'); closeModal()">📥 Сохранить в CRM</button>
        <button class="btn-secondary" onclick="closeModal()">Закрыть</button>
    `;

    modal.style.display = 'flex';
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

function openCRMModal(orderId) {
    const order = allCrmOrders.find(o => o.id === orderId);
    if (!order) return;

    const modal = document.getElementById('orderModal');
    document.getElementById('modalTitle').textContent = order.title;

    const statusOptions = Object.entries(STATUS_LABELS).map(([key, label]) =>
        `<option value="${key}" ${order.status === key ? 'selected' : ''}>${label}</option>`
    ).join('');

    document.getElementById('modalBody').innerHTML = `
        <p><strong>Источник:</strong> ${order.source.toUpperCase()}</p>
        <p><strong>Бюджет:</strong> ${order.budget || 'Договорная'}</p>
        <p><strong>Моя цена:</strong> ${order.my_price ? formatMoney(order.my_price) : 'Не указана'}</p>

        <div style="margin-top:16px">
            <label style="font-size:13px;font-weight:600;color:var(--text-secondary)">Статус:</label>
            <select id="modalStatus" class="input-field" style="margin-top:4px">
                ${statusOptions}
            </select>
        </div>

        <div style="margin-top:8px">
            <label style="font-size:13px;font-weight:600;color:var(--text-secondary)">Моя цена (₽):</label>
            <input type="number" id="modalPrice" class="input-field" value="${order.my_price || ''}" placeholder="0" style="margin-top:4px">
        </div>

        <div style="margin-top:8px">
            <label style="font-size:13px;font-weight:600;color:var(--text-secondary)">Заметки:</label>
            <textarea id="modalNotes" class="input-field" rows="3" style="margin-top:4px">${order.notes || ''}</textarea>
        </div>
    `;

    document.getElementById('modalActions').innerHTML = `
        <button class="btn-primary" onclick="saveCRMChanges(${orderId})">💾 Сохранить</button>
        ${order.url ? `<a href="${order.url}" target="_blank" class="btn-secondary" style="text-align:center;text-decoration:none;display:block">🔗 Открыть заказ</a>` : ''}
        <button class="btn-secondary" onclick="closeModal()">Закрыть</button>
    `;

    modal.style.display = 'flex';
}

async function saveCRMChanges(orderId) {
    const status = document.getElementById('modalStatus').value;
    const price = document.getElementById('modalPrice').value;
    const notes = document.getElementById('modalNotes').value;

    await apiPost(`/webapp/api/orders/${orderId}/status`, { status });
    await apiPost(`/webapp/api/orders/${orderId}/note`, {
        notes,
        my_price: price ? parseFloat(price) : null,
    });

    showToast('✅ Сохранено!');
    closeModal();
    await loadCRM();
}

function closeModal() {
    document.getElementById('orderModal').style.display = 'none';
}

// ==================== TOOLS ====================
function openTool(tool) {
    document.querySelectorAll('.tool-panel').forEach(p => p.style.display = 'none');
    const panel = document.getElementById(`panel-${tool}`);
    if (panel) {
        panel.style.display = 'block';
        panel.scrollIntoView({ behavior: 'smooth' });
    }
}

async function calculatePrice() {
    const desc = document.getElementById('calcDescription').value;
    if (!desc.trim()) { showToast('⚠️ Опишите задачу'); return; }

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳ Анализирую...';

    const result = await apiPost('/webapp/api/calculate-price', {
        description: desc,
        category: 'general'
    });

    btn.disabled = false;
    btn.textContent = '🤖 Рассчитать';

    const box = document.getElementById('calcResult');
    if (result && result.result) {
        box.textContent = result.result;
        box.classList.add('visible');
    } else {
        box.textContent = 'Ошибка расчёта. Попробуйте позже.';
        box.classList.add('visible');
    }
}

async function generateResponse() {
    const title = document.getElementById('respTitle').value;
    const desc = document.getElementById('respDescription').value;
    if (!title.trim()) { showToast('⚠️ Введите название заказа'); return; }

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳ Генерирую...';

    const result = await apiPost('/webapp/api/generate-response', {
        telegram_id: getTelegramId(),
        title,
        description: desc
    });

    btn.disabled = false;
    btn.textContent = '✍️ Сгенерировать';

    const box = document.getElementById('respResult');
    if (result && result.response) {
        box.textContent = result.response;
        box.classList.add('visible');
    } else {
        box.textContent = result?.error || 'Ошибка. Нужна активная подписка.';
        box.classList.add('visible');
    }
}

async function generateResponseModal(title, description) {
    showToast('⏳ Генерирую отклик...');

    const result = await apiPost('/webapp/api/generate-response', {
        telegram_id: getTelegramId(),
        title,
        description
    });

    if (result && result.response) {
        document.getElementById('modalBody').innerHTML = `
            <h3 style="margin-bottom:12px">✍️ Сгенерированный отклик:</h3>
            <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:10px;padding:16px;white-space:pre-wrap;line-height:1.5">${escapeHtml(result.response)}</div>
            <p style="margin-top:12px;font-size:12px;color:var(--text-secondary)">💡 Скопируйте и отправьте заказчику</p>
        `;
        document.getElementById('modalActions').innerHTML = `
            <button class="btn-primary" onclick="copyText('${escapeHtml(result.response).replace(/'/g, "\\'")}')">📋 Скопировать</button>
            <button class="btn-secondary" onclick="closeModal()">Закрыть</button>
        `;
    } else {
        showToast('❌ ' + (result?.error || 'Ошибка генерации'));
    }
}

async function checkClient() {
    const info = document.getElementById('clientInfo').value;
    if (!info.trim()) { showToast('⚠️ Введите информацию о заказчике'); return; }

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳ Проверяю...';

    const result = await apiPost('/webapp/api/check-client', { info });

    btn.disabled = false;
    btn.textContent = '🔍 Проверить';

    const box = document.getElementById('clientResult');
    if (result && result.result) {
        box.textContent = result.result;
        box.classList.add('visible');
    } else {
        box.textContent = 'Ошибка проверки. Попробуйте позже.';
        box.classList.add('visible');
    }
}

// ==================== PROFILE ====================
function renderProfile() {
    if (!currentUser) return;

    document.getElementById('profileName').textContent = currentUser.full_name || 'Не указано';
    document.getElementById('subBadge').textContent = currentUser.subscription_status;

    // Form
    document.getElementById('profName').value = currentUser.full_name || '';
    document.getElementById('profBio').value = currentUser.bio || '';
    document.getElementById('profPortfolio').value = currentUser.portfolio_url || '';
    document.getElementById('profRate').value = currentUser.hourly_rate || '';
    document.getElementById('profExperience').value = currentUser.experience_years || '';

    // Stats
    document.getElementById('profileStats').innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${currentUser.orders_viewed}</div>
            <div class="stat-label">Просмотрено</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${currentUser.responses_sent}</div>
            <div class="stat-label">Откликов</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${currentUser.orders_won}</div>
            <div class="stat-label">Выиграно</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${formatMoney(currentUser.total_earned)}</div>
            <div class="stat-label">Заработано</div>
        </div>
    `;

    // Parser
    const parserActive = currentUser.parser_active;
    document.getElementById('parserStatus').textContent = parserActive ? '🟢 Активен' : '🔴 Выключен';
    const btn = document.getElementById('parserBtn');
    btn.textContent = parserActive ? 'Выключить' : 'Включить';
    btn.className = parserActive ? 'btn-toggle active' : 'btn-toggle';
}

function renderCategories() {
    const grid = document.getElementById('categoriesGrid');
    const selected = currentUser?.categories || [];

    grid.innerHTML = Object.entries(CATEGORIES).map(([key, name]) => `
        <div class="category-chip ${selected.includes(key) ? 'active' : ''}"
             onclick="toggleCategory('${key}', this)">
            ${name}
        </div>
    `).join('');
}

async function toggleCategory(key, el) {
    if (!currentUser) return;

    let cats = [...(currentUser.categories || [])];
    if (cats.includes(key)) {
        cats = cats.filter(c => c !== key);
        el.classList.remove('active');
    } else {
        cats.push(key);
        el.classList.add('active');
    }

    currentUser.categories = cats;

    await apiPost('/webapp/api/profile/update', {
        telegram_id: getTelegramId(),
        categories: cats
    });

    if (tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

async function saveProfile() {
    const data = {
        telegram_id: getTelegramId(),
        full_name: document.getElementById('profName').value,
        bio: document.getElementById('profBio').value,
        portfolio_url: document.getElementById('profPortfolio').value,
        hourly_rate: document.getElementById('profRate').value,
        experience_years: document.getElementById('profExperience').value,
    };

    const result = await apiPost('/webapp/api/profile/update', data);
    if (result?.ok) {
        showToast('✅ Профиль сохранён!');
        await loadUser();
    } else {
        showToast('❌ Ошибка сохранения');
    }
}

async function toggleParser() {
    const result = await apiPost('/webapp/api/parser/toggle', {
        telegram_id: getTelegramId()
    });

    if (result?.ok) {
        currentUser.parser_active = result.parser_active;
        renderProfile();
        showToast(result.parser_active ? '🟢 Парсер запущен!' : '🔴 Парсер остановлен');
    }
}

// ==================== UTILS ====================
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diff = (now - date) / 1000;

    if (diff < 60) return 'только что';
    if (diff < 3600) return `${Math.floor(diff / 60)}м назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}ч назад`;
    return `${Math.floor(diff / 86400)}д назад`;
}

function formatMoney(amount) {
    if (!amount) return '0 ₽';
    if (amount >= 1000000) return `${(amount / 1000000).toFixed(1)}M ₽`;
    if (amount >= 1000) return `${(amount / 1000).toFixed(0)}K ₽`;
    return `${amount} ₽`;
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('visible');
    setTimeout(() => toast.classList.remove('visible'), 2500);
}

function copyText(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('📋 Скопировано!');
    }).catch(() => {
        showToast('❌ Не удалось скопировать');
    });
}

// Close modal on backdrop click
document.getElementById('orderModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'orderModal') closeModal();
});