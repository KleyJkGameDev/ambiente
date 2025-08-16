// Multi-item sales page JS com autosave ao alterar Produto
(function () {
  const $  = (sel, el=document) => el.querySelector(sel);
  const $$ = (sel, el=document) => Array.from(el.querySelectorAll(sel));

  const fmt = (n) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(n || 0));

  const form = $('#sale-form');
  if (!form) return;

  const tbody        = $('#items-body');
  const rowTemplate  = $('#row-template');
  const addBtn       = $('#add-item');
  const subtotalEl   = $('#subtotal-amount');
  const totalEl      = $('#total-amount');
  const submitBtn    = $('#submit-btn');
  const saleIdInput  = $('#sale_id');

  const statusBar    = $('#status-bar');
  const savingPill   = $('#saving-pill');
  const savedPill    = $('#saved-pill');

  const csrfToken    = form.querySelector('input[name=csrfmiddlewaretoken]').value;

  function showSaving() {
    statusBar.style.display = 'block';
    savingPill.style.display = 'inline-block';
    savedPill.style.display  = 'none';
  }
  function showSaved() {
    statusBar.style.display = 'block';
    savingPill.style.display = 'none';
    savedPill.style.display  = 'inline-block';
    setTimeout(() => { savedPill.style.display = 'none'; }, 1200);
  }

  function parseBRL(str) {
    if (typeof str === 'number') return str;
    if (!str) return 0;
    const s = String(str).replace(/[^0-9,.-]/g, '').replace('.', '').replace(',', '.');
    const val = parseFloat(s);
    return isNaN(val) ? 0 : val;
  }

  function setMoneyInput(input, value) {
    input.value = fmt(value);
  }

  function canSubmit() {
    const rows = $$('.item-row', tbody);
    if (rows.length === 0) return false;
    return rows.some(r => $('.product-select', r).value);
  }

  function recompute() {
    let subtotal = 0;
    $$('.item-row', tbody).forEach(row => {
      const qty  = Math.max(1, parseInt($('.qty', row).value || '1', 10));
      const unit = parseBRL($('.unit', row).dataset.value || $('.unit', row).value);
      const line = unit * qty;
      setMoneyInput($('.line_total', row), line);
      $('.line_total', row).dataset.value = String(line);
      subtotal += line;
    });
    subtotalEl.textContent = fmt(subtotal);
    totalEl.textContent    = fmt(subtotal); // total == subtotal (sem descontos/taxas)
    submitBtn.disabled     = !canSubmit();
  }

  async function fetchProduct(id) {
    const url = `/sales/product-info/?id=${encodeURIComponent(id)}`;
    const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    if (!res.ok) throw new Error('Falha ao carregar o produto');
    return await res.json();
  }

  async function onProductChange(row, id) {
    if (!id) {
      $('.desc', row).value = '';
      $('.category', row).value = '';
      $('.brandline', row).textContent = '';
      setMoneyInput($('.unit', row), 0);
      $('.unit', row).dataset.value = '0';
      recompute();
      // autosave mesmo limpando? vamos salvar o estado atual
      autoSave();
      return;
    }
    try {
      const data = await fetchProduct(id);
      $('.desc', row).value = data.description || '';
      $('.category', row).value = data.category_name || '';
      $('.brandline', row).textContent = data.brand_name ? `Marca: ${data.brand_name}` : '';
      const price = Number(data.price || 0);
      setMoneyInput($('.unit', row), price);
      $('.unit', row).dataset.value = String(price);
    } catch (err) {
      console.error(err);
      alert('Não foi possível carregar as informações do produto.');
      setMoneyInput($('.unit', row), 0);
      $('.unit', row).dataset.value = '0';
    } finally {
      recompute();
      // requisito: ao alterar Produto, salvar automaticamente
      autoSave();
    }
  }

  function bindRow(row) {
    $('.qty', row).addEventListener('input', () => recompute());
    $('.remove-row', row).addEventListener('click', () => {
      row.remove();
      recompute();
      // (opcional) autosave ao remover linha
      autoSave();
    });
    $('.product-select', row).addEventListener('change', (e) => onProductChange(row, e.target.value));
  }

  function addRow() {
    const node = rowTemplate.content.firstElementChild.cloneNode(true);
    tbody.appendChild(node);
    bindRow(node);
    recompute();
  }

  addBtn.addEventListener('click', () => {
    addRow();
    // (opcional) salvar logo após criar a linha vazia? Vamos esperar escolher o produto.
  });

  // primeira linha
  addRow();

  // Debounce simples para evitar múltiplos POSTs em sequência
  let saveTimer = null;
  function autoSave() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNow, 300);
  }

  async function saveNow() {
    try {
      showSaving();

      // Antes de enviar: trocar os campos monetários formatados por números brutos
      $$('.item-row', tbody).forEach(row => {
        const unit = parseBRL($('.unit', row).dataset.value || $('.unit', row).value);
        const line = parseBRL($('.line_total', row).dataset.value || $('.line_total', row).value);
        $('.unit', row).value = unit;
        $('.line_total', row).value = line;
      });

      const fd = new FormData(form);
      const res = await fetch('/sales/new/', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken },
        body: fd,
      });
      if (!res.ok) throw new Error('Falha no autosave');
      const data = await res.json();

      if (data.ok) {
        if (!saleIdInput.value) {
          saleIdInput.value = data.sale_id; // mantém a mesma venda nos próximos saves
        }
        showSaved();
        // "atualizar a página": você pode escolher:
        // 1) recarregar para refletir qualquer lógica de servidor:
        //    window.location.reload();
        // 2) ou apenas manter o estado (já atualizado no cliente).
        // Vou manter sem reload por padrão. Descomente abaixo se quiser recarregar:
        // window.location.reload();
      } else {
        alert(data.error || 'Erro ao salvar.');
      }
    } catch (e) {
      console.error(e);
      alert('Não foi possível salvar automaticamente.');
    }
  }

  // Submit manual (botão) mantém o fluxo anterior: redireciona para o admin
  form.addEventListener('submit', () => {
    // Normaliza valores antes do submit tradicional
    $$('.item-row', tbody).forEach(row => {
      const unit = parseBRL($('.unit', row).dataset.value || $('.unit', row).value);
      const line = parseBRL($('.line_total', row).dataset.value || $('.line_total', row).value);
      $('.unit', row).value = unit;
      $('.line_total', row).value = line;
    });
  });
})();
