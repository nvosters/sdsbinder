let latestScan = null;

const scanForm = document.getElementById('scan-form');
const statusEl = document.getElementById('scan-status');
const verifyPanel = document.getElementById('verify-panel');
const vProduct = document.getElementById('v-product');
const vManufacturer = document.getElementById('v-manufacturer');
const vSds = document.getElementById('v-sds');
const confirmBtn = document.getElementById('confirm-btn');
const searchEl = document.getElementById('search');
const catalogEl = document.getElementById('catalog');

function msg(text, ok = true) {
  statusEl.textContent = text;
  statusEl.className = ok ? 'ok' : 'err';
}

function shelfGroup(products) {
  const g = {};
  for (const p of products) {
    const k = (p.product_name?.[0] || '#').toUpperCase();
    g[k] ||= [];
    g[k].push(p);
  }
  return g;
}

async function loadCatalog() {
  const q = (searchEl.value || '').toLowerCase().trim();
  const rows = await fetch('/api/products').then(r => r.json());
  const filtered = rows.filter(x => !q || x.product_name.toLowerCase().includes(q) || (x.manufacturer || '').toLowerCase().includes(q));
  const grouped = shelfGroup(filtered);
  const letters = Object.keys(grouped).sort();

  if (!letters.length) {
    catalogEl.innerHTML = '<p>No products yet.</p>';
    return;
  }

  catalogEl.innerHTML = letters.map(letter => `
    <h3>Shelf ${letter}</h3>
    <div class="cards">
      ${grouped[letter].map(p => `
        <article class="card">
          <h4>${p.product_name}</h4>
          <p><b>Manufacturer:</b> ${p.manufacturer || 'Unknown'}</p>
          <p><a target="_blank" rel="noopener" href="${p.sds_url}">Open SDS</a></p>
        </article>
      `).join('')}
    </div>
  `).join('');
}

scanForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = document.getElementById('image').files[0];
  if (!file) return;

  msg('Analyzing image and searching SDS candidates...');
  const fd = new FormData();
  fd.append('image', file);

  const res = await fetch('/api/scan', { method: 'POST', body: fd });
  const data = await res.json();
  if (!res.ok) {
    msg(data.error || 'Scan failed', false);
    return;
  }

  latestScan = data;
  vProduct.value = data.product_name || '';
  vManufacturer.value = data.manufacturer || '';
  vSds.innerHTML = '';

  (data.candidates || []).forEach((c) => {
    const opt = document.createElement('option');
    opt.value = c.url;
    opt.textContent = `[${c.confidence || 'low'}] ${c.url}`;
    vSds.appendChild(opt);
  });

  verifyPanel.hidden = false;
  msg('Please verify the extracted data before adding.', true);
});

confirmBtn.addEventListener('click', async () => {
  if (!latestScan) return;
  const payload = {
    product_name: vProduct.value.trim(),
    manufacturer: vManufacturer.value.trim(),
    sds_url: vSds.value,
    source: 'ai-assisted-verified',
  };
  const res = await fetch('/api/verify-add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    msg(data.error || 'Could not save', false);
    return;
  }
  msg('Saved to binder.', true);
  verifyPanel.hidden = true;
  scanForm.reset();
  await loadCatalog();
});

searchEl.addEventListener('input', loadCatalog);
loadCatalog();
