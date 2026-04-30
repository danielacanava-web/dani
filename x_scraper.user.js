// ==UserScript==
// @name         X/Twitter Metrics Collector
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Collect views, likes, comments, reposts from X posts and export CSV
// @match        https://x.com/*
// @match        https://twitter.com/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    const STORAGE_KEY = 'x_metrics_collected';

    function parseCount(text) {
        if (!text) return '';
        const clean = text.replace(/,/g, '').trim();
        const upper = clean.toUpperCase();
        try {
            if (upper.endsWith('B')) return Math.round(parseFloat(upper) * 1_000_000_000);
            if (upper.endsWith('M')) return Math.round(parseFloat(upper) * 1_000_000);
            if (upper.endsWith('K')) return Math.round(parseFloat(upper) * 1_000);
            const n = parseInt(clean, 10);
            return isNaN(n) ? '' : n;
        } catch { return ''; }
    }

    function getMetric(testId, labelWord) {
        const el = document.querySelector(`[data-testid="${testId}"]`);
        if (!el) return '';
        // Try aria-label first
        const label = el.getAttribute('aria-label') || '';
        const m = label.match(/([\d,\.]+[KkMmBb]?)\s*/);
        if (m) return parseCount(m[1]);
        // Try inner span
        const span = el.querySelector('span[data-testid="app-text-transition-container"]');
        if (span) return parseCount(span.innerText.trim());
        return '';
    }

    function getViews() {
        const el = document.querySelector('a[href$="/analytics"]');
        if (!el) return '';
        const nums = el.innerText.match(/([\d,\.]+[KkMmBb]?)/);
        return nums ? parseCount(nums[1]) : '';
    }

    function collectCurrentPage() {
        const url = window.location.href.split('?')[0];
        if (!url.includes('/status/')) return null;

        return {
            url: window.location.href,
            views:    getViews(),
            likes:    getMetric('like', 'like'),
            comments: getMetric('reply', 'repl'),
            reposts:  getMetric('retweet', 'repost'),
        };
    }

    function saveData(row) {
        const existing = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        // Replace if URL already collected
        const idx = existing.findIndex(r => r.url.includes(row.url.split('/status/')[1].split('?')[0]));
        if (idx >= 0) existing[idx] = row;
        else existing.push(row);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
        return existing.length;
    }

    function downloadCSV() {
        const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        if (!data.length) { alert('No data collected yet.'); return; }
        const header = 'post_url,views,likes,comments,reposts\n';
        const rows = data.map(r =>
            `"${r.url}",${r.views},${r.likes},${r.comments},${r.reposts}`
        ).join('\n');
        const blob = new Blob([header + rows], { type: 'text/csv' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'x_metrics.csv';
        a.click();
    }

    function clearData() {
        localStorage.removeItem(STORAGE_KEY);
        updateStatus();
        alert('Data cleared.');
    }

    // --- UI ---
    function buildUI() {
        const box = document.createElement('div');
        box.id = 'xmc-box';
        box.style.cssText = `
            position: fixed; bottom: 20px; right: 20px; z-index: 99999;
            background: #000; color: #fff; border: 1px solid #333;
            border-radius: 12px; padding: 12px 16px; font-family: sans-serif;
            font-size: 13px; min-width: 220px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        `;

        const title = document.createElement('div');
        title.textContent = '📊 X Metrics Collector';
        title.style.cssText = 'font-weight: bold; margin-bottom: 8px; font-size: 14px;';

        const status = document.createElement('div');
        status.id = 'xmc-status';
        status.style.cssText = 'color: #aaa; margin-bottom: 10px; font-size: 12px;';

        const collectBtn = document.createElement('button');
        collectBtn.textContent = '⬇ Collect this page';
        collectBtn.style.cssText = btnStyle('#1d9bf0');
        collectBtn.onclick = () => {
            const row = collectCurrentPage();
            if (!row) { alert('Not on a tweet page.'); return; }
            const count = saveData(row);
            updateStatus();
            collectBtn.textContent = '✓ Collected!';
            setTimeout(() => { collectBtn.textContent = '⬇ Collect this page'; }, 1500);
        };

        const downloadBtn = document.createElement('button');
        downloadBtn.textContent = '⬇ Download CSV';
        downloadBtn.style.cssText = btnStyle('#00ba7c');
        downloadBtn.onclick = downloadCSV;

        const clearBtn = document.createElement('button');
        clearBtn.textContent = '🗑 Clear data';
        clearBtn.style.cssText = btnStyle('#444');
        clearBtn.onclick = clearData;

        box.appendChild(title);
        box.appendChild(status);
        box.appendChild(collectBtn);
        box.appendChild(downloadBtn);
        box.appendChild(clearBtn);
        document.body.appendChild(box);

        updateStatus();
    }

    function btnStyle(bg) {
        return `display:block; width:100%; margin-bottom:6px; padding:7px 10px;
            background:${bg}; color:#fff; border:none; border-radius:8px;
            cursor:pointer; font-size:13px; font-weight:600; text-align:center;`;
    }

    function updateStatus() {
        const el = document.getElementById('xmc-status');
        if (!el) return;
        const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        el.textContent = `${data.length} post(s) collected`;
    }

    // Wait for page to settle before building UI
    setTimeout(buildUI, 2000);

    // Auto-update status when navigating between tweets (X is a SPA)
    const observer = new MutationObserver(() => updateStatus());
    observer.observe(document.body, { childList: true, subtree: true });
})();
