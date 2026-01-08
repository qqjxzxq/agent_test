// 通用工具函数
console.log('政府部门多智能体决策仿真系统 - 前端已加载');

// 格式化日期时间
function formatDateTime(dateString) {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

// 格式化数字
function formatNumber(num) {
  if (num >= 1e8) {
    return (num / 1e8).toFixed(2) + '亿';
  } else if (num >= 1e4) {
    return (num / 1e4).toFixed(2) + '万';
  }
  return num.toString();
}

// 加载状态指示器
function showLoading(element) {
  element.classList.add('loading');
  element.style.opacity = '0.5';
}

function hideLoading(element) {
  element.classList.remove('loading');
  element.style.opacity = '1';
}

// 简单的通知提示
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.textContent = message;
  notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
    `;

  document.body.appendChild(notification);

  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

// 导出函数供全局使用
window.formatDateTime = formatDateTime;
window.formatNumber = formatNumber;
window.showNotification = showNotification;
