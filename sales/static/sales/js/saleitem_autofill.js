(function () {
  // Monta a URL de consulta
  function buildUrl(productId) {
    return "/sales/product-info/?id=" + encodeURIComponent(productId);
  }

  // Dado o name "...-product", gera o name do outro campo
  function siblingName(productName, targetSuffix) {
    // ex.: id_saleitem_set-0-product  -> id_saleitem_set-0-price_at_sale
    return productName.replace(/-product$/, "-" + targetSuffix);
  }

  // Preenche os campos da mesma linha usando o padrão de name
  function autofillByName(selectEl, data) {
    // preço
    var priceInput = document.querySelector('input[name="' + siblingName(selectEl.name, "price_at_sale") + '"]');
    if (priceInput && data.price != null && data.price !== "") {
      priceInput.value = data.price;
    }
    // marca/categoria (somente leitura)
    // Eles aparecem no admin como readonly_fields renderizados em HTML — vamos localizar pelo "data-saleitem"
    var row = selectEl.closest("tr");
    if (row) {
      var brandSpan = row.querySelector('[data-saleitem="brand_display"]');
      var categorySpan = row.querySelector('[data-saleitem="category_display"]');
      if (brandSpan) brandSpan.textContent = data.brand_name || "-";
      if (categorySpan) categorySpan.textContent = data.category_name || "-";
    }
  }

  function onProductChange(e) {
    var select = e.target;
    var productId = select.value;
    if (!productId) {
      autofillByName(select, { price: "", brand_name: "-", category_name: "-" });
      return;
    }
    fetch(buildUrl(productId), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) { autofillByName(select, data); })
      .catch(function () { /* silencia erros */ });
  }

  // Faz o bind em TODOS os selects de produto, sem depender de classe do inline
  function bindAll() {
    var selects = document.querySelectorAll('select[name$="-product"]');
    selects.forEach(function (s) {
      if (!s.dataset.autofillBound) {
        s.addEventListener("change", onProductChange);
        s.dataset.autofillBound = "1";
        // Se já vier selecionado (edição), dispara para preencher
        if (s.value) {
          var ev = new Event("change", { bubbles: true });
          s.dispatchEvent(ev);
        }
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindAll();

    // Quando adiciona uma nova linha inline ("Adicionar outro Item de venda")
    document.body.addEventListener("click", function (e) {
      var t = e.target;
      if (t && t.classList.contains("add-row")) {
        setTimeout(bindAll, 60); // aguarda DOM inserir a nova linha
      }
    });
  });
})();
