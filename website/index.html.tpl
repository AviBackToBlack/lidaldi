<!DOCTYPE html>
<html lang="en">
	<head>
		<meta charset="UTF-8" />
		<meta http-equiv="X-UA-Compatible" content="IE=edge" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title>ALDI.IE &amp; LIDL.IE Special Offers</title>
		<link rel="stylesheet" href="css/lidaldi.css" />
	</head>
	<body>
		<header>
			<div class="header-top">
				<div class="project-logo">
					<img src="img/lidaldi.png" width="80" height="80" alt="LIDALDI" />
				</div>
				<div class="header-info">
					<h1>ALDI.IE &amp; LIDL.IE Special Offers</h1>
					<div class="page-last-updated">
						<svg class="header-icon" viewBox="0 0 24 24">
							<path d="M12 1a11 11 0 1 0 11 11A11.013 11.013 0 0 0 12 1Zm.5 11h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5v-5a.5.5 0 0 1 1 0v4.5Z"></path>
						</svg>
						Last updated: <strong id="lastUpdatedDate"></strong>
					</div>
					<div class="last-visit-info" id="lastVisitInfo" style="display: none">
						<svg class="header-icon" viewBox="0 0 24 24">
							<path d="M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2Zm0 16H5V9h14Z"></path>
						</svg>
						Your last visit: <strong id="lastVisitDate"></strong>
					</div>
				</div>
			</div>
		</header>

		<div class="filters-row">
			<div id="availability-filters"></div>
			<div class="category-wrapper">
				<select name="category" id="category">
					<option value="">All categories</option>
				</select>
			</div>
			<div class="price-range">
				<div class="price-wrapper">
					<input id="priceFrom" type="text" placeholder="Price from" style="width: 70px" />
					<button type="button" class="clear-price-btn" style="display: none;">×</button>
				</div>
				-
				<div class="price-wrapper">
					<input id="priceTo" type="text" placeholder="Price to" style="width: 70px" />
					<button type="button" class="clear-price-btn" style="display: none;">×</button>
				</div>
			</div>
			<div class="sortby-wrapper">
				<select name="sortby" id="sortby">
					<option value="">No price sorting</option>
					<option value="price-asc">Price ascending</option>
					<option value="price-desc">Price descending</option>
				</select>
			</div>
			<div class="search-container">
				<input class="search-box" type="text" placeholder="Search products..." id="searchBox" />
				<button type="button" class="clear-search-btn" style="display: none">×</button>
			</div>
			<button id="resetFilters">Reset</button>
		</div>

		<div class="products-grid" id="productsGrid"></div>

		<div class="pagination" id="paginationContainer"></div>

		<footer>
			<p>Not affiliated with ALDI or LIDL.</p>
			<p>Contribute on GitHub → <a href="https://github.com/AviBackToBlack/lidaldi" target="_blank">lidaldi</a></p>
		</footer>
		<script type="application/json" id="__SPECIAL_OFFERS_META_DATA__">
			%%SPECIAL_OFFERS_META_DATA%%
		</script>
		<script type="application/json" id="__SPECIAL_OFFERS_DATA__">
			%%SPECIAL_OFFERS_DATA%%
		</script>
		<script src="js/lidaldi.js"></script>
	</body>
</html>
