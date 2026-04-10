<!DOCTYPE html>
<html lang="en">
	<head>
		<meta charset="UTF-8" />
		<meta http-equiv="X-UA-Compatible" content="IE=edge" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<meta name="vapid-public-key" content="%%VAPID_PUBLIC_KEY%%" />
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
			<button id="openAlertsModal" class="alerts-btn" title="Manage alerts and sync settings">
				<svg class="alerts-icon" viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4a2 2 0 0 0 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4a1.5 1.5 0 0 0-3 0v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"></path></svg>
				Alerts
			</button>
		</div>

		<div class="products-grid" id="productsGrid"></div>

		<div class="pagination" id="paginationContainer"></div>

		<footer>
			<p>Not affiliated with ALDI or LIDL.</p>
			<p>Contribute on GitHub → <a href="https://github.com/AviBackToBlack/lidaldi" target="_blank">lidaldi</a></p>
		</footer>

		<!-- Alerts & Sync Modal -->
		<div class="modal-overlay" id="alertsModal" style="display: none">
			<div class="modal-content">
				<div class="modal-header">
					<h2>Alerts &amp; Sync</h2>
					<button class="modal-close" id="closeAlertsModal">&times;</button>
				</div>
				<div class="modal-body">
					<!-- Sync Code Section -->
					<h3>Sync Code</h3>
					<p class="modal-hint">Use the same code on all your devices to sync alerts and "New from last visit".</p>
					<div class="sync-code-display" id="syncCodeDisplay" style="display: none">
						<span class="sync-code-value" id="syncCodeValue"></span>
						<button id="copySyncCode" class="btn-secondary">Copy</button>
						<button id="removeSyncCode" class="btn-danger">Remove</button>
					</div>
					<div class="sync-code-setup" id="syncCodeSetup">
						<button id="generateSyncCode">Generate New Code</button>
						<span class="modal-hint">or</span>
						<input type="text" id="enterSyncCode" placeholder="Enter code" maxlength="8" />
						<button id="applySyncCode">Apply</button>
					</div>

					<!-- Notifications Section -->
					<h3>Push Notifications</h3>
					<div class="notifications-row">
						<button id="enableNotifications">Enable Notifications</button>
						<span id="notificationStatus" class="modal-hint"></span>
					</div>

					<!-- Alerts Section -->
					<h3>Your Alerts</h3>
					<div id="alertsList"></div>
					<div class="add-alert-form">
						<input type="text" id="alertKeyword" placeholder="Enter keyword(s)..." />
						<select id="alertMatchType">
							<option value="exact">Exact phrase</option>
							<option value="allWords">All words</option>
							<option value="anyWord">Any word</option>
						</select>
						<button id="addAlertBtn">Add</button>
					</div>
				</div>
			</div>
		</div>

		<!--
			The placeholders below are substituted by process_offers.py at
			render time. process_offers.safe_json_for_script() escapes "</"
			and U+2028/U+2029 so scraped descriptions cannot terminate the
			<script> tag and inject markup (stored XSS).
		-->
		<script type="application/json" id="__SPECIAL_OFFERS_META_DATA__">
			%%SPECIAL_OFFERS_META_DATA%%
		</script>
		<script type="application/json" id="__SPECIAL_OFFERS_DATA__">
			%%SPECIAL_OFFERS_DATA%%
		</script>
		<script src="js/lidaldi.js"></script>
	</body>
</html>
