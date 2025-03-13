document.addEventListener("DOMContentLoaded", function () {
  /************************************************
   * Cookie helpers
   ***********************************************/
  function setCookie(name, value, days = 365) {
    const d = new Date();
    d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
    const expires = "expires=" + d.toUTCString();
    document.cookie = name + "=" + value + ";" + expires + ";path=/";
  }

  function getCookie(name) {
    const cname = name + "=";
    const decodedCookie = decodeURIComponent(document.cookie);
    const ca = decodedCookie.split(";");
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i].trim();
      if (c.indexOf(cname) === 0) {
        return c.substring(cname.length, c.length);
      }
    }
    return "";
  }

  /************************************************
   * Tooltip logic
   ***********************************************/
  let hoverTimeout = null;
  function startTooltipTimer(cardElement) {
    if (document.activeElement && document.activeElement.tagName === "INPUT") {
      document.activeElement.blur();
    }
    const tooltip = cardElement.querySelector(".desc-tooltip");
    hoverTimeout = setTimeout(() => {
      if (tooltip) tooltip.style.display = "block";
    }, 1000);
  }

  function stopTooltipTimer(cardElement) {
    if (hoverTimeout) clearTimeout(hoverTimeout);
    const tooltip = cardElement.querySelector(".desc-tooltip");
    if (tooltip) tooltip.style.display = "none";
  }

  /************************************************
   * Reading data and last-visit cookie
   ***********************************************/
  const offersMetaDataElement = document.getElementById(
    "__SPECIAL_OFFERS_META_DATA__"
  );
  const offersDataElement = document.getElementById("__SPECIAL_OFFERS_DATA__");

  let offersMetaData = {};
  let offersData = [];

  if (offersMetaDataElement) {
    offersMetaData = JSON.parse(offersMetaDataElement.textContent);
  }
  if (offersDataElement) {
    offersData = JSON.parse(offersDataElement.textContent);
  }

  let activeAvailability = "new";
  let priceFromValue = "";
  let priceToValue = "";
  let categoryValue = "";
  let sortValue = "";
  let searchValue = "";

  let currentPage = 1;
  let totalPages = 1;

  let disableNewButton = false;

  let lastVisitCookie = getCookie("lastVisit");
  let lastVisitTimestamp = 0;

  if (offersMetaData && offersMetaData.lastUpdated) {
    document.getElementById("lastUpdatedDate").textContent =
      offersMetaData.lastUpdated;
  }

  if (lastVisitCookie) {
    document.getElementById("lastVisitInfo").style.display = "block";
    lastVisitTimestamp = parseInt(lastVisitCookie, 10);
    if (!isNaN(lastVisitTimestamp)) {
      const d = new Date(lastVisitTimestamp * 1000);
      const dd = String(d.getDate()).padStart(2, "0");
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const yyyy = d.getFullYear();
      document.getElementById(
        "lastVisitDate"
      ).textContent = `${dd}/${mm}/${yyyy}`;
    }
  }

  if (!lastVisitTimestamp) {
    activeAvailability = "all";
    disableNewButton = true;
  } else {
    const newItems = offersData.filter(
      (it) => it.scraped_at > lastVisitTimestamp
    );
    if (newItems.length === 0) {
      activeAvailability = "all";
      disableNewButton = true;
    }
  }

  setCookie("lastVisit", Math.floor(Date.now() / 1000).toString());

  /************************************************
   * Build availability filters
   ***********************************************/
  const availabilityFiltersDiv = document.getElementById(
    "availability-filters"
  );

  const baseFilters = [
    { key: "new", label: "New from last visit", disabled: disableNewButton },
    { key: "all", label: "All products" },
    { key: "inStore", label: "Currently in store" },
  ];

  const futureDates = new Set();
  const today = new Date();
  offersData.forEach((item) => {
    const ds = item.store_availability_date || "";
    if (ds && ds !== "01-01-0000" && ds !== "01-01-9999") {
      const [dd, mm, yyyy] = ds.split("-");
      const dt = new Date(+yyyy, +mm - 1, +dd);
      if (!isNaN(dt) && dt > today) {
        futureDates.add(ds);
      }
    }
  });

  const sortedFutureDates = Array.from(futureDates).sort((a, b) => {
    const [ad, am, ay] = a.split("-");
    const [bd, bm, by] = b.split("-");
    return new Date(+ay, +am - 1, +ad) - new Date(+by, +bm - 1, +bd);
  });

  const dateFilters = sortedFutureDates.map((ds) => {
    const [dd, mm] = ds.split("-");
    return { key: ds, label: `From ${dd}.${mm}` };
  });

  const availabilityFilters = [...baseFilters, ...dateFilters];

  availabilityFilters.forEach((f) => {
    const btn = document.createElement("button");
    btn.textContent = f.label;
    btn.dataset.availabilityKey = f.key;
    if (f.disabled) {
      btn.disabled = true;
      btn.style.opacity = "0.5";
      btn.style.cursor = "not-allowed";
      btn.title =
        "This button is disabled because no new products are available or it is your first visit.";
    }
    if (f.key === activeAvailability) {
      btn.classList.add("active");
    }
    btn.addEventListener("click", () => {
      document
        .querySelectorAll("#availability-filters button")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeAvailability = f.key;
      currentPage = 1;
      render();
    });
    availabilityFiltersDiv.appendChild(btn);
  });

  /************************************************
   * Realtime highlight for price, sort, search
   ***********************************************/
  function highlight(el) {
    el.style.backgroundColor = getComputedStyle(
      document.documentElement
    ).getPropertyValue("--brand-primary");
    el.style.color = getComputedStyle(
      document.documentElement
    ).getPropertyValue("--white");
    if (
      el.parentElement &&
      el.parentElement.classList.contains("price-wrapper")
    ) {
      el.parentElement.style.setProperty(
        "--euro-color",
        getComputedStyle(document.documentElement).getPropertyValue("--white")
      );
    }
  }

  function unhighlight(el) {
    el.style.backgroundColor = "";
    el.style.color = "";
    if (
      el.parentElement &&
      el.parentElement.classList.contains("price-wrapper")
    ) {
      el.parentElement.style.setProperty(
        "--euro-color",
        getComputedStyle(document.documentElement).getPropertyValue(
          "--brand-primary"
        )
      );
    }
  }

  /************************************************
   * Event listeners for price, sort, search inputs
   ***********************************************/
  const priceFromInput = document.getElementById("priceFrom");
  const priceToInput = document.getElementById("priceTo");
  const clearPriceFromBtn =
    priceFromInput.parentElement.querySelector(".clear-price-btn");
  const clearPriceToBtn =
    priceToInput.parentElement.querySelector(".clear-price-btn");

  priceFromInput.addEventListener("input", () => {
    priceFromInput.value = priceFromInput.value.replace(/[^\d.]/g, "");
    priceFromValue = priceFromInput.value.trim();
    if (priceFromValue) {
      clearPriceFromBtn.style.display = "block";
      highlight(priceFromInput);
    } else {
      clearPriceFromBtn.style.display = "none";
      unhighlight(priceFromInput);
    }
    currentPage = 1;
    render();
  });

  priceToInput.addEventListener("input", () => {
    priceToInput.value = priceToInput.value.replace(/[^\d.]/g, "");
    priceToValue = priceToInput.value.trim();
    if (priceToValue) {
      clearPriceToBtn.style.display = "block";
      highlight(priceToInput);
    } else {
      clearPriceToBtn.style.display = "none";
      unhighlight(priceToInput);
    }
    currentPage = 1;
    render();
  });

  clearPriceFromBtn.addEventListener("click", () => {
    priceFromInput.value = "";
    priceFromValue = "";
    clearPriceFromBtn.style.display = "none";
    unhighlight(priceFromInput);
    currentPage = 1;
    render();
  });

  clearPriceToBtn.addEventListener("click", () => {
    priceToInput.value = "";
    priceToValue = "";
    clearPriceToBtn.style.display = "none";
    unhighlight(priceToInput);
    currentPage = 1;
    render();
  });

  const categorySelect = document.getElementById("category");
  categorySelect.addEventListener("change", () => {
    categoryValue = categorySelect.value;
    categoryValue ? highlight(categorySelect) : unhighlight(categorySelect);
    currentPage = 1;
    render();
  });

  const categorySet = new Set();
  offersData.forEach((item) => {
    if (item.category) {
      categorySet.add(item.category);
    }
  });
  const sortedCategories = Array.from(categorySet).sort();
  sortedCategories.forEach((category) => {
    let option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    categorySelect.appendChild(option);
  });

  const sortbySelect = document.getElementById("sortby");
  sortbySelect.addEventListener("change", () => {
    sortValue = sortbySelect.value;
    sortValue ? highlight(sortbySelect) : unhighlight(sortbySelect);
    currentPage = 1;
    render();
  });

  const searchBox = document.getElementById("searchBox");
  const clearSearchBtn = document.querySelector(".clear-search-btn");

  searchBox.addEventListener("input", () => {
    searchValue = searchBox.value.trim().toLowerCase();
    if (searchValue) {
      clearSearchBtn.style.display = "block";
      highlight(searchBox);
    } else {
      clearSearchBtn.style.display = "none";
      unhighlight(searchBox);
    }
    currentPage = 1;
    render();
  });

  clearSearchBtn.addEventListener("click", () => {
    searchBox.value = "";
    searchValue = "";
    clearSearchBtn.style.display = "none";
    unhighlight(searchBox);
    currentPage = 1;
    render();
  });

  const resetButton = document.getElementById("resetFilters");
  resetButton.addEventListener("click", () => {
    if (clearPriceFromBtn) clearPriceFromBtn.click();
    if (clearPriceToBtn) clearPriceToBtn.click();
    if (clearSearchBtn) clearSearchBtn.click();

    const categorySelect = document.getElementById("category");
    categorySelect.value = "";
    categoryValue = "";
    unhighlight(categorySelect);

    const sortSelect = document.getElementById("sortby");
    sortSelect.value = "";
    sortValue = "";
    unhighlight(sortSelect);

    if (!lastVisitTimestamp) {
      activeAvailability = "all";
      disableNewButton = true;
    } else {
      const newItems = offersData.filter(
        (it) => it.scraped_at > lastVisitTimestamp
      );
      if (newItems.length === 0) {
        activeAvailability = "all";
        disableNewButton = true;
      }
    }

    document.querySelectorAll("#availability-filters button").forEach((btn) => {
      btn.classList.remove("active");
      if (btn.dataset.availabilityKey === activeAvailability) {
        btn.classList.add("active");
      }
    });

    currentPage = 1;

    render();
  });

  /************************************************
   * Dynamic Page Size Calculation
   ***********************************************/
  function getDynamicPageSize() {
    if (window.innerWidth < 600) {
      return offersData.length;
    }
  
    const headerHeight = document.querySelector('header').offsetHeight || 0;
    const filtersRowHeight = document.querySelector(".filters-row").offsetHeight || 0;
    const paginationHeight = document.getElementById("paginationContainer").offsetHeight || 0;
    const footerHeight = document.querySelector("footer").offsetHeight || 0;
  
    const availableHeight = window.innerHeight - headerHeight - filtersRowHeight - paginationHeight - footerHeight;
  
    const sampleCard = document.querySelector(".product-card");
    const cardHeight = sampleCard ? sampleCard.offsetHeight : 320;
  
    const rows = Math.floor(availableHeight / cardHeight) || 1;
  
    const grid = document.getElementById("productsGrid");
    const gridWidth = grid ? grid.offsetWidth : window.innerWidth;
    const sampleCardWidth = sampleCard ? sampleCard.offsetWidth : 250;
    const cols = Math.floor(gridWidth / sampleCardWidth) || 1;
  
    return rows * cols;
  }

  window.addEventListener("resize", () => {
    render();
  });

  /************************************************
   * Filter, Pagination, and Rendering Logic
   ***********************************************/
  function applyFilters(data, ignoreCategory = false) {
    let filtered = [...data];

    if (activeAvailability === "inStore") {
      filtered = filtered.filter((it) => {
        if (it.store_availability_date === "01-01-0000") return true;
        if (
          !it.store_availability_date ||
          it.store_availability_date === "01-01-9999"
        )
          return false;

        const [dd, mm, yyyy] = it.store_availability_date.split("-");
        const productDate = new Date(+yyyy, +mm - 1, +dd);

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        productDate.setHours(0, 0, 0, 0);

        return productDate <= today;
      });
    } else if (activeAvailability === "all") {
      // no filtering
    } else if (activeAvailability === "new") {
      filtered = filtered.filter((it) => it.scraped_at > lastVisitTimestamp);
    } else {
      const [fd, fm, fy] = activeAvailability.split("-");
      const filterDate = new Date(+fy, +fm - 1, +fd);
      filtered = filtered.filter((it) => {
        if (!it.store_availability_date) return false;
        if (
          it.store_availability_date === "01-01-0000" ||
          it.store_availability_date === "01-01-9999"
        )
          return false;
        const [id, im, iy] = it.store_availability_date.split("-");
        const itemDate = new Date(+iy, +im - 1, +id);
        return itemDate >= filterDate;
      });
    }

    filtered = filtered.filter((it) => {
      const p = parseFloat(it.price) || 0;
      if (priceFromValue) {
        const pf = parseFloat(priceFromValue);
        if (!isNaN(pf) && p < pf) return false;
      }
      if (priceToValue) {
        const pt = parseFloat(priceToValue);
        if (!isNaN(pt) && p > pt) return false;
      }
      return true;
    });

    if (searchValue) {
      filtered = filtered.filter((it) => {
        const t = (
          it.store +
          " " +
          (it.title || "") +
          " " +
          (it.description || "")
        ).toLowerCase();
        return t.includes(searchValue);
      });
    }

    if (!ignoreCategory && categoryValue) {
      filtered = filtered.filter((it) => it.category === categoryValue);
    }

    if (sortValue === "price-asc") {
      filtered.sort((a, b) => parseFloat(a.price) - parseFloat(b.price));
    } else if (sortValue === "price-desc") {
      filtered.sort((a, b) => parseFloat(b.price) - parseFloat(a.price));
    }

    return filtered;
  }

  function applyFiltersExceptCategory(data) {
    let filtered = [...data];

    if (activeAvailability === "inStore") {
      filtered = filtered.filter((it) => {
        if (it.store_availability_date === "01-01-0000") return true;
        if (
          !it.store_availability_date ||
          it.store_availability_date === "01-01-9999"
        )
          return false;

        const [dd, mm, yyyy] = it.store_availability_date.split("-");
        const productDate = new Date(+yyyy, +mm - 1, +dd);

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        productDate.setHours(0, 0, 0, 0);

        return productDate <= today;
      });
    } else if (activeAvailability === "all") {
      // no filtering
    } else if (activeAvailability === "new") {
      filtered = filtered.filter((it) => it.scraped_at > lastVisitTimestamp);
    } else {
      const [fd, fm, fy] = activeAvailability.split("-");
      const filterDate = new Date(+fy, +fm - 1, +fd);
      filtered = filtered.filter((it) => {
        if (!it.store_availability_date) return false;
        if (
          it.store_availability_date === "01-01-0000" ||
          it.store_availability_date === "01-01-9999"
        )
          return false;
        const [id, im, iy] = it.store_availability_date.split("-");
        const itemDate = new Date(+iy, +im - 1, +id);
        return itemDate >= filterDate;
      });
    }

    filtered = filtered.filter((it) => {
      const p = parseFloat(it.price) || 0;
      if (priceFromValue) {
        const pf = parseFloat(priceFromValue);
        if (!isNaN(pf) && p < pf) return false;
      }
      if (priceToValue) {
        const pt = parseFloat(priceToValue);
        if (!isNaN(pt) && p > pt) return false;
      }
      return true;
    });

    if (searchValue) {
      filtered = filtered.filter((it) => {
        const t = (
          it.store +
          " " +
          (it.title || "") +
          " " +
          (it.description || "")
        ).toLowerCase();
        return t.includes(searchValue);
      });
    }
    return filtered;
  }

  function render() {
    const filteredForCategories = applyFilters(offersData, true);
    const availableCategories = new Set();
    filteredForCategories.forEach((item) => {
      if (item.category) {
        availableCategories.add(item.category);
      }
    });
    const categorySelect = document.getElementById("category");
    categorySelect.innerHTML = "";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "All categories";
    categorySelect.appendChild(defaultOption);

    Array.from(availableCategories)
      .sort()
      .forEach((category) => {
        const option = document.createElement("option");
        option.value = category;
        option.textContent = category;
        categorySelect.appendChild(option);
      });

    if (categoryValue) {
      if (!availableCategories.has(categoryValue)) {
        const option = document.createElement("option");
        option.value = categoryValue;
        option.textContent = categoryValue;
        categorySelect.appendChild(option);
      }
      categorySelect.value = categoryValue;
    } else {
      categorySelect.value = "";
    }

    const filtered = applyFilters(offersData);
    const pageSize = getDynamicPageSize();

    totalPages = Math.ceil(filtered.length / pageSize);
    if (totalPages < 1) totalPages = 1;
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const startIndex = (currentPage - 1) * pageSize;
    const pageItems = filtered.slice(startIndex, startIndex + pageSize);

    const productsGrid = document.getElementById("productsGrid");
    productsGrid.innerHTML = "";
    pageItems.forEach((item) => {
      const card = document.createElement("div");
      card.className = "product-card";
      card.addEventListener("mouseover", () => startTooltipTimer(card));
      card.addEventListener("mouseout", () => stopTooltipTimer(card));

      const link = document.createElement("a");
      link.href = item.url;
      link.target = "_blank";
      link.style.textDecoration = "none";
      link.style.color = "inherit";

      const titleDiv = document.createElement("div");
      titleDiv.className = "product-title";
      const storeImg = document.createElement("img");
      if (item.store === "ALDI") {
        storeImg.src = "img/aldi.png";
        storeImg.width = "16";
        storeImg.height = "16";
        storeImg.alt = "ALDI";
      } else {
        storeImg.src = "img/lidl.png";
        storeImg.width = "16";
        storeImg.height = "16";
        storeImg.alt = "LIDL";
      }
      titleDiv.appendChild(storeImg);
      titleDiv.appendChild(
        document.createTextNode(item.title ? " " + item.title : "")
      );
      link.appendChild(titleDiv);

      const bottom = document.createElement("div");
      bottom.className = "bottom-container";

      const imgDiv = document.createElement("div");
      imgDiv.className = "product-image";
      if (item.images && item.images.length > 0) {
        const prodImg = document.createElement("img");
        prodImg.src = "img/" + item.images[0].path;
        prodImg.alt = item.title || "Product";
        prodImg.style.maxWidth = "100%";
        prodImg.style.maxHeight = "100%";
        imgDiv.innerHTML = "";
        imgDiv.appendChild(prodImg);
      } else {
        imgDiv.textContent = "No image";
      }

      const infoDiv = document.createElement("div");
      infoDiv.className = "product-info";
      const availSpan = document.createElement("span");
      availSpan.textContent = formatAvailability(item.store_availability_date);
      const priceSpan = document.createElement("span");
      priceSpan.textContent = "€" + item.price;

      infoDiv.appendChild(availSpan);
      infoDiv.appendChild(priceSpan);
      bottom.appendChild(imgDiv);
      bottom.appendChild(infoDiv);
      card.appendChild(bottom);

      link.appendChild(bottom);
      card.appendChild(link);

      const tooltip = document.createElement("div");
      tooltip.className = "desc-tooltip";
      tooltip.textContent =
        "Store: " + item.store + "\n\n" + (item.description || "");
      card.appendChild(tooltip);

      productsGrid.appendChild(card);
    });

    const paginationContainer = document.getElementById("paginationContainer");
    paginationContainer.innerHTML = "";
    const prevBtn = document.createElement("button");
    prevBtn.innerHTML = `
      <svg viewBox="0 0 24 24">
        <path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"></path>
      </svg>
      Prev
    `;
    let prevBtnDisabled = currentPage <= 1;
    prevBtn.disabled = prevBtnDisabled;
    prevBtn.style.opacity = prevBtnDisabled ? "0.5" : "";
    prevBtn.style.cursor = prevBtnDisabled ? "not-allowed" : "";
    prevBtn.addEventListener("click", () => {
      if (currentPage > 1) {
        currentPage--;
        render();
      }
    });
    paginationContainer.appendChild(prevBtn);

    for (let p = 1; p <= totalPages; p++) {
      const pageBtn = document.createElement("button");
      pageBtn.textContent = p;
      pageBtn.classList.add("page-number-btn");
      if (p === currentPage) {
        pageBtn.classList.add("active-page");
      }
      pageBtn.addEventListener("click", () => {
        currentPage = p;
        render();
      });
      if (totalPages == 1) {
        pageBtn.disabled = true;
        pageBtn.style.opacity = "0.5";
        pageBtn.style.cursor = "not-allowed";
      }
      paginationContainer.appendChild(pageBtn);
    }

    const nextBtn = document.createElement("button");
    nextBtn.innerHTML = `
      Next
      <svg viewBox="0 0 24 24">
        <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"></path>
      </svg>
    `;
    let nextBtnDisabled = currentPage >= totalPages;
    nextBtn.disabled = nextBtnDisabled;
    nextBtn.style.opacity = nextBtnDisabled ? "0.5" : "";
    nextBtn.style.cursor = nextBtnDisabled ? "not-allowed" : "";
    nextBtn.addEventListener("click", () => {
      if (currentPage < totalPages) {
        currentPage++;
        render();
      }
    });
    paginationContainer.appendChild(nextBtn);
  }

  function formatAvailability(ds) {
    if (!ds) return "Unknown date";
    if (ds === "01-01-0000") return "While Stock Lasts";
    if (ds === "01-01-9999") return "Unknown date";
    const [dd, mm] = ds.split("-");
    return "From " + dd + "." + mm;
  }

  window.addEventListener("keydown", function (e) {
    const tag = document.activeElement.tagName.toLowerCase();
    if (tag === "input" || tag === "textarea") return;

    if (e.key === "ArrowLeft") {
      if (currentPage > 1) {
        currentPage--;
        render();
      }
    } else if (e.key === "ArrowRight") {
      if (currentPage < totalPages) {
        currentPage++;
        render();
      }
    }
  });

  render();
});
