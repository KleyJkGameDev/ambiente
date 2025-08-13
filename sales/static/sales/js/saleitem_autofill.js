(function () {
  function buildUrl(productId) {
    return "/sales/product-info/?id=" + encodeURIComponent(productId);
  }

  function updatePrice(row) {
    var priceSpan = row.querySelector('[data-saleitem="price_display"]');
    var qtyInput = row.querySelector('input[name$="-quantity"]');
    var unitPrice = parseFloat(priceSpan.dataset.unitPrice || "0");
    var qty = parseInt(qtyInput.value || "1", 10);
    priceSpan.textContent = (unitPrice * qty).toFixed(2);
  }

  function autofillRow(selectEl, data) {
    var row = selectEl.closest("tr");
    if (!row) return;

    // Atualiza preço unitário
    var priceSpan = row.querySelector('[data-saleitem="price_display"]');
    if (priceSpan) {
      priceSpan.dataset.unitPrice = data.price || 0;
      updatePrice(row); // recalcula total
    }

    // Atualiza marca e categoria
    var brandSpan = row.querySelector('[data-saleitem="brand_display"]');
    var categorySpan = row.querySelector('[data-saleitem="category_display"]');
    if (brandSpan) brandSpan.textContent = data.brand_name || "-";
    if (categorySpan) categorySpan.textContent = data.category_name || "-";
  }

  function onProductChange(e) {
    var select = e.target;
    var productId = select.value;
    if (!productId) {
      autofillRow(select, { price: 0, brand_name: "-", category_name: "-" });
      return;
    }
    fetch(buildUrl(productId), { credentials: "same-origin" })
      .then(r => r.json())
      .then(data => autofillRow(select, data))
      .catch(() => {});
  }

  function onQuantityChange(e) {
    var row = e.target.closest("tr");
    updatePrice(row);
  }

  function bindAll() {
    document.querySelectorAll('select[name$="-product"]').forEach(s => {
      if (!s.dataset.bound) {
        s.addEventListener("change", onProductChange);
        s.dataset.bound = "1";
      }
    });

    document.querySelectorAll('input[name$="-quantity"]').forEach(q => {
      if (!q.dataset.bound) {
        q.addEventListener("input", onQuantityChange);
        q.dataset.bound = "1";
      }
    });
  }

  document.addEventListener("DOMContentLoaded", bindAll);
  document.body.addEventListener("click", e => {
    if (e.target.classList.contains("add-row")) {
      setTimeout(bindAll, 60);
    }
  });
})();
