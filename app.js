const KEY = 'sds-binder-products-v1';

const state = {
  products: JSON.parse(localStorage.getItem(KEY) || '[]'),
};

const alertsEl = document.getElementById('alerts');
const catalogEl = document.getElementById('catalog');
const searchEl = document.getElementById('search');

function notify(msg, kind = 'ok') {
  const div = document.createElement('div');
  div.className = `alert ${kind}`;
  div.textContent = msg;
  alertsEl.prepend(div);
  setTimeout(() => div.remove(), 4000);
}

function save() {
  localStorage.setItem(KEY, JSON.stringify(state.products));
}

function sdsSearchUrl(product, manufacturer) {
  const q = encodeURIComponent(`${product} ${manufacturer} SDS PDF`);
  return `https://duckduckgo.com/?q=${q}`;
}

function addProduct(productName, manufacturer = '', notes = 'Added manually') {
  state.products.push({
    id: crypto.randomUUID(),
    productName: productName.trim(),
    manufacturer: manufacturer.trim(),
    notes,
    sdsUrl: sdsSearchUrl(productName, manufacturer),
    createdAt: new Date().toISOString(),
  });
  save();
  render();
}

function groupProducts(items) {
  return items.reduce((acc, item) => {
    const key = (item.productName[0] || '#').toUpperCase();
    acc[key] ||= [];
    acc[key].push(item);
    return acc;
  }, {});
}

function render() {
  const q = searchEl.value.toLowerCase().trim();
  const filtered = state.products
    .filter(p => !q || p.productName.toLowerCase().includes(q) || p.manufacturer.toLowerCase().includes(q))
    .sort((a, b) => a.productName.localeCompare(b.productName));

  const grouped = groupProducts(filtered);
  const letters = Object.keys(grouped).sort();

  if (!letters.length) {
    catalogEl.innerHTML = '<p>No products yet.</p>';
    return;
  }

  catalogEl.innerHTML = letters.map(letter => `
    <h3 class="shelf">Shelf ${letter}</h3>
    <div class="cards">
      ${grouped[letter].map(p => `
        <article class="card">
          <h4>${p.productName}</h4>
          <p><strong>Manufacturer:</strong> ${p.manufacturer || 'Unknown'}</p>
          <p><strong>Notes:</strong> ${p.notes || '—'}</p>
          <p><a href="${p.sdsUrl}" target="_blank" rel="noopener">Find SDS PDF</a></p>
        </article>
      `).join('')}
    </div>
  `).join('');
}

function parseFilename(fileName) {
  const clean = fileName.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ');
  const parts = clean.split(/\s+by\s+/i);
  return {
    productName: (parts[0] || '').trim(),
    manufacturer: (parts[1] || '').trim(),
  };
}

async function extractByOCR(file) {
  if (!window.Tesseract) return null;
  try {
    const result = await window.Tesseract.recognize(file, 'eng');
    const lines = result.data.text.split('\n').map(x => x.trim()).filter(Boolean);
    const productName = lines.find(line => line.length > 3 && line.length < 45) || '';
    const manufacturerLine = lines.find(line => /manufacturer|company|supplier/i.test(line)) || '';
    const manufacturer = manufacturerLine.replace(/manufacturer|company|supplier|:/ig, '').trim();
    if (!productName) return null;
    return { productName, manufacturer };
  } catch {
    return null;
  }
}

document.getElementById('add-form').addEventListener('submit', e => {
  e.preventDefault();
  const productName = document.getElementById('product-name').value;
  const manufacturer = document.getElementById('manufacturer').value;
  const notes = document.getElementById('notes').value || 'Added manually';
  addProduct(productName, manufacturer, notes);
  e.target.reset();
  notify('Product added to binder.');
});

document.getElementById('scan-form').addEventListener('submit', async e => {
  e.preventDefault();
  const file = document.getElementById('label-photo').files[0];
  if (!file) return;

  let parsed = await extractByOCR(file);
  if (!parsed || !parsed.productName) {
    parsed = parseFilename(file.name);
    notify('OCR unavailable/unclear image, used filename fallback.', 'warn');
  }

  if (!parsed.productName) {
    notify('Could not detect product name. Try clearer image or better filename.', 'warn');
    return;
  }

  addProduct(parsed.productName, parsed.manufacturer, 'Added from uploaded image');
  e.target.reset();
  notify(`Added ${parsed.productName}. SDS search link generated.`);
});

searchEl.addEventListener('input', render);
render();
