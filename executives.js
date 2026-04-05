// This script dynamically loads executives.json and renders the executive summary table.
// Place this after the existing <script> in index.html or merge with your main JS.

async function loadExecutives() {
    try {
        const response = await fetch('executives.json');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        renderExecutivesTable(data);
    } catch (error) {
        console.error('Error loading executives:', error);
        const section = document.getElementById('executives-section');
        section.innerHTML += '<div class="error">Error loading executive data.</div>';
    }
}

function renderExecutivesTable(data) {
    const tbody = document.querySelector('#executives-section table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    for (const [assoc, execs] of Object.entries(data.associations)) {
        for (const exec of execs) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${assoc}</td>
                <td>${exec.role || ''}</td>
                <td>${exec.name || ''}</td>
                <td>${exec.phone || ''}</td>
                <td>${exec.email ? `<a href="mailto:${exec.email}">${exec.email}</a>` : ''}</td>
            `;
            tbody.appendChild(tr);
        }
    }
    // Update last updated time if present
    if (data.last_updated) {
        const summary = document.querySelector('#executives-section .summary');
        if (summary) {
            summary.innerHTML += `<div style="margin-top:0.5rem;font-size:0.95em;color:#888;">Last updated: ${new Date(data.last_updated).toLocaleString()}</div>`;
        }
    }
}

document.addEventListener('DOMContentLoaded', loadExecutives);
