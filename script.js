// static/script.js
// Глобальные функции для взаимодействия с сайтом

// Покупка NFT
async function buyNFT(nftId) {
    try {
        const response = await fetch(`/api/buy/${nftId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('✅ Покупка успешно завершена!', 'success');
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            showNotification('❌ ' + data.error, 'error');
        }
    } catch (error) {
        showNotification('❌ Произошла ошибка при покупке', 'error');
    }
}

// Передача NFT
async function transferNFT(nftId, toUsername) {
    try {
        const response = await fetch('/api/transfer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nft_id: nftId,
                to_username: toUsername
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`✅ Код передачи: ${data.transfer_code}`, 'success', 10000);
            return data;
        } else {
            showNotification('❌ ' + data.error, 'error');
            return null;
        }
    } catch (error) {
        showNotification('❌ Ошибка при передаче NFT', 'error');
        return null;
    }
}

// Пополнение баланса
async function depositStars(amount) {
    try {
        const response = await fetch('/api/deposit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ amount: amount })
        });
        
        const data = await response.json();
        
        if (data.success && data.payment_link) {
            // Открываем ссылку на оплату
            window.open(data.payment_link, '_blank');
        } else {
            showNotification('❌ Ошибка при создании ссылки на оплату', 'error');
        }
    } catch (error) {
        showNotification('❌ Ошибка при пополнении', 'error');
    }
}

// Получение статистики пользователя
async function getUserStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.success) {
            return data.stats;
        }
        return null;
    } catch (error) {
        console.error('Error fetching stats:', error);
        return null;
    }
}

// Показать уведомление
function showNotification(message, type = 'info', duration = 3000) {
    // Создаем контейнер для уведомлений если его нет
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        `;
        document.body.appendChild(container);
    }
    
    // Создаем уведомление
    const notification = document.createElement('div');
    notification.style.cssText = `
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#6366f1'};
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        animation: slideIn 0.3s ease;
        cursor: pointer;
    `;
    
    notification.innerHTML = message;
    
    // Добавляем анимацию
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
    
    // Добавляем в контейнер
    container.appendChild(notification);
    
    // Удаляем через указанное время
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, duration);
    
    // Клик для закрытия
    notification.addEventListener('click', () => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    });
}

// Загрузка NFT для превью
function previewNFT(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const preview = document.getElementById('nft-preview');
            if (preview) {
                preview.src = e.target.result;
                preview.style.display = 'block';
            }
        }
        
        reader.readAsDataURL(input.files[0]);
    }
}

// Валидация формы
function validateForm(formId) {
    const form = document.getElementById(formId);
    const inputs = form.querySelectorAll('input[required], textarea[required]');
    
    for (let input of inputs) {
        if (!input.value.trim()) {
            showNotification(`❌ Поле ${input.name} обязательно`, 'error');
            input.focus();
            return false;
        }
    }
    
    return true;
}

// Копирование текста в буфер обмена
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('✅ Скопировано в буфер обмена', 'success');
    }).catch(() => {
        showNotification('❌ Ошибка при копировании', 'error');
    });
}

// Форматирование даты
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Добавляем классы для анимации
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.classList.add('fade-in-up');
        card.style.animationDelay = `${index * 0.1}s`;
    });
    
    // Инициализируем Telegram Login Widget если есть
    if (typeof TelegramLoginWidget !== 'undefined') {
        TelegramLoginWidget.init();
    }
    
    // Загружаем статистику если нужно
    const statsElement = document.getElementById('user-stats');
    if (statsElement) {
        getUserStats().then(stats => {
            if (stats) {
                statsElement.innerHTML = `
                    <div class="row">
                        <div class="col-3">
                            <div class="stats-card">
                                <div class="stats-number">${stats.total_nfts}</div>
                                <div class="stats-label">Всего NFT</div>
                            </div>
                        </div>
                        <div class="col-3">
                            <div class="stats-card">
                                <div class="stats-number">${stats.balance}</div>
                                <div class="stats-label">Баланс ⭐️</div>
                            </div>
                        </div>
                        <div class="col-3">
                            <div class="stats-card">
                                <div class="stats-number">${stats.sold_nfts}</div>
                                <div class="stats-label">Продано</div>
                            </div>
                        </div>
                        <div class="col-3">
                            <div class="stats-card">
                                <div class="stats-number">${stats.total_earned}</div>
                                <div class="stats-label">Заработано ⭐️</div>
                            </div>
                        </div>
                    </div>
                `;
            }
        });
    }
});