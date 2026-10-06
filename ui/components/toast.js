// ui/components/toast.js

class ToastManager {
  constructor() {
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    this.container.setAttribute('role', 'status');
    this.container.setAttribute('aria-live', 'polite');
    document.body.appendChild(this.container);
  }

  show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    
    // Status colors mapping
    let colorVar = 'var(--text-primary)';
    if (type === 'success') colorVar = 'var(--color-passed)';
    if (type === 'error') colorVar = 'var(--color-critical)';
    if (type === 'warning') colorVar = 'var(--color-warning)';
    
    // Circle indicator for type
    toast.innerHTML = `
      <div class="toast-icon" style="border-radius: 50%; background: ${colorVar}; width: 12px; height: 12px;"></div>
      <p class="toast-message"></p>
    `;
    // Text only: messages can include server or site-derived text.
    toast.querySelector('.toast-message').textContent = String(message ?? '');
    
    this.container.appendChild(toast);
    
    // Animate in
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });
    
    // Animate out and remove
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
}

export const toast = new ToastManager();
