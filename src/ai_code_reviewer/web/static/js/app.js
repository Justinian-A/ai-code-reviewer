/**
 * AI Code Reviewer - Main JavaScript
 * Handles API interactions and UI updates
 */

// API Base URL
const API_BASE = '';

/**
 * Utility function to make API requests
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const response = await fetch(`${API_BASE}${url}`, { ...defaultOptions, ...options });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP error ${response.status}`);
    }

    return response.json();
}

/**
 * Show status alert
 */
function showStatus(type, title, message, showSpinner = false) {
    const alert = document.getElementById('statusAlert');
    const spinner = document.getElementById('statusSpinner');
    const titleEl = document.getElementById('statusTitle');
    const messageEl = document.getElementById('statusMessage');

    if (!alert) return;

    // Remove all alert classes
    alert.className = 'alert mb-4';

    // Add appropriate class
    switch (type) {
        case 'success':
            alert.classList.add('alert-success');
            break;
        case 'danger':
            alert.classList.add('alert-danger');
            break;
        case 'warning':
            alert.classList.add('alert-warning');
            break;
        case 'info':
            alert.classList.add('alert-info');
            break;
    }

    titleEl.textContent = title;
    messageEl.textContent = message;

    if (spinner) {
        spinner.classList.toggle('d-none', !showSpinner);
    }

    alert.classList.remove('d-none');
}

/**
 * Hide status alert
 */
function hideStatus() {
    const alert = document.getElementById('statusAlert');
    if (alert) {
        alert.classList.add('d-none');
    }
}

/**
 * Format date string
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';

    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;

    return date.toLocaleDateString('zh-CN');
}

/**
 * Format cost
 */
function formatCost(cost) {
    if (cost === null || cost === undefined) return '$0.00';
    return `$${cost.toFixed(2)}`;
}

/**
 * Get status badge HTML
 */
function getStatusBadge(status) {
    const statusMap = {
        'pending': { class: 'bg-warning-subtle text-warning-emphasis', icon: 'hourglass-split', text: '等待中' },
        'running': { class: 'bg-info-subtle text-info-emphasis', icon: 'arrow-repeat', text: '分析中' },
        'completed': { class: 'bg-success-subtle text-success-emphasis', icon: 'check-circle', text: '完成' },
        'failed': { class: 'bg-danger-subtle text-danger-emphasis', icon: 'x-circle', text: '失败' },
    };

    const config = statusMap[status] || statusMap['pending'];
    return `<span class="badge ${config.class}"><i class="bi bi-${config.icon} me-1"></i>${config.text}</span>`;
}

/**
 * Load dashboard data
 */
async function loadDashboardData() {
    try {
        // Load recent analyses
        const historyData = await apiRequest('/api/analyses?limit=5');
        renderRecentAnalyses(historyData.items || []);

        // Load cost summary
        const costData = await apiRequest('/api/costs/summary');

        // Update stats
        const statAnalyses = document.getElementById('statAnalyses');
        const statRisks = document.getElementById('statRisks');
        const statSuggestions = document.getElementById('statSuggestions');
        const statCost = document.getElementById('statCost');

        if (statAnalyses) statAnalyses.textContent = costData.total_analyses || 0;
        if (statRisks) statRisks.textContent = costData.total_risks || 0;
        if (statSuggestions) statSuggestions.textContent = costData.total_suggestions || 0;
        if (statCost) statCost.textContent = formatCost(costData.total_cost_usd);

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

/**
 * Render recent analyses table
 */
function renderRecentAnalyses(analyses) {
    const tbody = document.getElementById('recentAnalyses');
    if (!tbody) return;

    if (analyses.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-4 text-muted">
                    <i class="bi bi-inbox fs-4 d-block mb-2"></i>
                    暂无分析记录
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = analyses.map(analysis => `
        <tr>
            <td>
                <a href="${analysis.pr_url}" target="_blank" class="fw-medium">
                    ${analysis.repository}
                </a>
            </td>
            <td>
                <span class="text-muted">#${analysis.pr_number}</span>
            </td>
            <td>${getStatusBadge(analysis.status)}</td>
            <td>
                <span class="${analysis.risk_count > 0 ? 'text-danger fw-medium' : 'text-muted'}">
                    ${analysis.risk_count}
                </span>
            </td>
            <td>
                <span class="${analysis.suggestion_count > 0 ? 'text-info fw-medium' : 'text-muted'}">
                    ${analysis.suggestion_count}
                </span>
            </td>
            <td class="text-muted">${formatCost(analysis.cost_usd)}</td>
            <td class="text-muted">${formatDate(analysis.created_at)}</td>
            <td>
                <a href="/analysis/${analysis.id}" class="btn btn-sm btn-outline-secondary">
                    <i class="bi bi-eye"></i>
                </a>
            </td>
        </tr>
    `).join('');
}

/**
 * Handle analysis form submission
 */
function initAnalysisForm() {
    const form = document.getElementById('analysisForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const prUrl = document.getElementById('prUrl').value;
        const analyzeBtn = document.getElementById('analyzeBtn');

        // Disable button
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>提交中...';

        try {
            const result = await apiRequest('/api/analyze', {
                method: 'POST',
                body: JSON.stringify({ pr_url: prUrl }),
            });

            showStatus('success', '分析已启动', `分析ID: ${result.analysis_id}`);

            // Clear form
            form.reset();

            // Reload dashboard data after a short delay
            setTimeout(loadDashboardData, 1000);

        } catch (error) {
            showStatus('danger', '提交失败', error.message);
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = '<i class="bi bi-play-fill"></i> 开始分析';
        }
    });
}

/**
 * Initialize tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Main initialization
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    initTooltips();

    // Initialize forms
    initAnalysisForm();

    // Close alert on click
    const statusAlert = document.getElementById('statusAlert');
    if (statusAlert) {
        statusAlert.addEventListener('click', function() {
            this.classList.add('d-none');
        });
    }
});

// Export functions for use in other scripts
window.AIReviewer = {
    apiRequest,
    showStatus,
    hideStatus,
    formatDate,
    formatCost,
    getStatusBadge,
    loadDashboardData,
};