// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

function preload_file_uploader() {
	// Only preload when the bundle map can actually resolve the name. On
	// website/portal pages frappe.boot.assets_json isn't booted, so
	// frappe.assets.bundled_asset() falls back to the bare bundle name — a
	// relative URL resolved against the current page path → a harmless-but-noisy
	// 404 + strict-MIME error. The uploader still lazy-loads on first real use
	// (an actual upload), which runs in desk context where the map is present.
	try {
		if (frappe.boot?.assets_json?.["file_uploader.bundle.js"]) {
			frappe.require("file_uploader.bundle.js");
		}
	} catch (e) {
		// never let an eager preload break page load
	}
}

if (frappe.require) {
	preload_file_uploader();
} else {
	frappe.ready(preload_file_uploader);
}
