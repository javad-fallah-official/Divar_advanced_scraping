// Single-page view: no pagination

function getFilters() {
  const source = document.getElementById('source').value;
  const city = document.getElementById('city').value || '';
  const district = document.getElementById('district').value || '';
  const brand = document.getElementById('brand').value || '';
  const min_price = document.getElementById('min_price').value || '';
  const max_price = document.getElementById('max_price').value || '';
  const min_year = document.getElementById('min_year').value || '';
  const max_year = document.getElementById('max_year').value || '';
  const min_mileage = document.getElementById('min_mileage').value || '';
  const max_mileage = document.getElementById('max_mileage').value || '';
  const negotiable = document.getElementById('negotiable').value || '';
  const search = document.getElementById('search').value || '';
  return { source, city, district, brand, min_price, max_price, min_year, max_year, min_mileage, max_mileage, negotiable, search };
}

async function loadPosts() {
  const f = getFilters();
  const params = new URLSearchParams();
  params.set('source', f.source);
  if (f.city) params.set('city', f.city);
  if (f.district) params.set('district', f.district);
  if (f.brand) params.set('brand', f.brand);
  if (f.min_price) params.set('min_price', f.min_price);
  if (f.max_price) params.set('max_price', f.max_price);
  if (f.min_year) params.set('min_year', f.min_year);
  if (f.max_year) params.set('max_year', f.max_year);
  if (f.min_mileage) params.set('min_mileage', f.min_mileage);
  if (f.max_mileage) params.set('max_mileage', f.max_mileage);
  if (f.negotiable) params.set('negotiable', f.negotiable);
  if (f.search) params.set('search', f.search);
  // No page/page_size in single-page mode

  const res = await fetch('/api/posts?' + params.toString());
  const data = await res.json();
  render(data);
}

function render(data) {
  const cards = document.getElementById('cards');
  const stats = document.getElementById('stats');
  cards.innerHTML = '';
  stats.textContent = `Total: ${data.total} | Showing ${data.items.length} items`;
  // No page label in single-page mode
  data.items.forEach(item => {
    const div = document.createElement('div');
    div.className = 'card';
    const price = item.price_toman ? new Intl.NumberFormat('fa-IR').format(item.price_toman) + ' تومان' : '—';
    const year = item.model_year_jalali || '—';
    const mileage = item.mileage_km ? new Intl.NumberFormat('fa-IR').format(item.mileage_km) + ' km' : '—';
    const loc = [item.city, item.district].filter(Boolean).join('، ');
    const brand = item.brand || '—';
    const source = item.source || 'playwright';
    const desc = item.description || '';
    div.innerHTML = `
      <h3><a href="${item.url}" target="_blank" rel="noopener">${item.title}</a></h3>
      <div class="price">${price}</div>
      <div class="meta">برند: ${brand} | سال: ${year} | کارکرد: ${mileage}</div>
      <div class="meta">${loc} | منبع: ${source}</div>
      <div class="desc">${desc.substring(0, 160)}</div>
    `;
    cards.appendChild(div);
  });
}

document.getElementById('apply').addEventListener('click', () => { loadPosts(); });
document.getElementById('reset').addEventListener('click', () => {
  document.getElementById('source').value = 'playwright';
  document.getElementById('city').value = '';
  document.getElementById('district').value = '';
  document.getElementById('brand').value = '';
  document.getElementById('min_price').value = '';
  document.getElementById('max_price').value = '';
  document.getElementById('min_year').value = '';
  document.getElementById('max_year').value = '';
  document.getElementById('min_mileage').value = '';
  document.getElementById('max_mileage').value = '';
  document.getElementById('negotiable').value = '';
  document.getElementById('search').value = '';
  // No page size or page state in single-page mode
  loadPosts();
});

// Initial load
loadPosts();
