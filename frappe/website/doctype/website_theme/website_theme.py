# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import re
from os.path import abspath, splitext
from os.path import exists as path_exists
from os.path import join as join_path
from pathlib import Path
from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document


class WebsiteTheme(Document):
	_DOCTYPE_NAME = "Website Theme"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from frappe.website.doctype.website_theme_ignore_app.website_theme_ignore_app import (
			WebsiteThemeIgnoreApp,
		)

		background_color: DF.Link | None
		button_gradients: DF.Check
		button_rounded_corners: DF.Check
		button_shadows: DF.Check
		custom: DF.Check
		custom_overrides: DF.Code | None
		custom_scss: DF.Code | None
		dark_color: DF.Link | None
		font_properties: DF.Data | None
		font_size: DF.Data | None
		google_font: DF.Data | None
		ignored_apps: DF.Table[WebsiteThemeIgnoreApp]
		js: DF.Code | None
		light_color: DF.Link | None
		module: DF.Link
		primary_color: DF.Link | None
		text_color: DF.Link | None
		theme: DF.Data
		theme_scss: DF.Code | None
		theme_url: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.validate_if_customizable()
		self.generate_bootstrap_theme()

	def on_update(self):
		if (
			not self.custom
			and frappe.local.conf.get("developer_mode")
			and not frappe.flags.in_import
			and not frappe.in_test
		):
			self.export_doc()

		self.clear_cache_if_current_theme()

	def is_standard_and_not_valid_user(self):
		return (
			not self.custom
			and not frappe.local.conf.get("developer_mode")
			and not (frappe.flags.in_import or frappe.in_test or frappe.flags.in_migrate)
		)

	def on_trash(self):
		if self.is_standard_and_not_valid_user():
			frappe.throw(_("You are not allowed to delete a standard Website Theme"), frappe.PermissionError)

	def validate_if_customizable(self):
		if self.is_standard_and_not_valid_user():
			frappe.throw(_("Please Duplicate this Website Theme to customize."))

	def export_doc(self):
		"""Export to standard folder `[module]/website_theme/[name]/[name].json`."""
		from frappe.modules.export_file import export_to_files

		export_to_files(record_list=[["Website Theme", self.name]], create_init=True)

	def clear_cache_if_current_theme(self):
		if frappe.flags.in_install == "frappe":
			return
		website_settings = frappe.get_doc("Website Settings", "Website Settings")
		if getattr(website_settings, "website_theme", None) == self.name:
			website_settings.clear_cache()

	def generate_bootstrap_theme(self):
		from subprocess import PIPE, Popen

		# create theme file in site public files folder
		folder_path = abspath(frappe.utils.get_files_path("website_theme", is_private=False))
		# create folder if not exist
		frappe.create_folder(folder_path)

		if self.custom:
			self.delete_old_theme_files(folder_path)

		# add a random suffix
		suffix = frappe.generate_hash(length=8) if self.custom else "style"
		file_name = frappe.scrub(self.name) + "_" + suffix + ".css"
		output_path = join_path(folder_path, file_name)

		self.theme_scss = content = get_scss(self)
		content = content.replace("\n", "\\n")
		command = ["node", "generate_bootstrap_theme.js", output_path, content]

		process = Popen(command, cwd=frappe.get_app_source_path("frappe"), stdout=PIPE, stderr=PIPE)

		stderr = process.communicate()[1]

		if stderr:
			stderr = frappe.safe_decode(stderr)
			stderr = stderr.replace("\n", "<br>")
			frappe.throw(f'<div style="font-family: monospace;">{stderr}</div>')
		else:
			absolutify_app_asset_imports(output_path)
			self.theme_url = "/files/website_theme/" + file_name

		frappe.msgprint(_("Compiled Successfully"), alert=True)

	def delete_old_theme_files(self, folder_path):
		import os

		theme_files: list[Path] = []
		for fname in os.listdir(folder_path):
			if fname.startswith(frappe.scrub(self.name) + "_") and fname.endswith(".css"):
				theme_files.append(Path(folder_path) / fname)

		theme_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
		# Keep 3 recent files
		for old_file in theme_files[2:]:
			old_file.unlink()

	@frappe.whitelist()
	def set_as_default(self):
		self.save()
		website_settings = frappe.get_doc("Website Settings")
		website_settings.website_theme = self.name
		website_settings.ignore_validate = True
		website_settings.save()

	@frappe.whitelist()
	def get_apps(self):
		from frappe.utils.change_log import get_versions

		apps = get_versions()
		return [{"name": app, "title": values["title"]} for app, values in apps.items()]


def get_active_theme() -> "WebsiteTheme" | None:
	if website_theme := frappe.get_website_settings("website_theme"):
		try:
			return frappe.client_cache.get_doc("Website Theme", website_theme)
		except frappe.DoesNotExistError:
			frappe.clear_last_message()
			pass


#: `@import "<app>/public/<rest>"` → the URL that actually serves it, `/assets/<app>/<rest>`.
#: Anchored to the start of the quoted value so already-absolute (`/assets/…`) and remote
#: (`https://…`) imports are left alone, and the import must be a bare app-relative path.
APP_ASSET_IMPORT = re.compile(
	r"""(@import\s*(?:url\(\s*)?)(['"])(?!/|https?:|data:)([a-z0-9_]+)/public/([^'"]+)\2""",
	re.IGNORECASE,
)


def absolutify_app_asset_imports(css_path):
	"""Rewrite app-relative plain-CSS `@import`s in a generated theme file (framework#171).

	Dart Sass treats `@import "…/x.css"` as a **plain CSS import** and emits it
	verbatim instead of inlining it. `frappe/public/scss/espresso_components.scss`
	imports 17 component files that way, and the website theme pulls it in — so the
	compiled theme keeps ~30 literal `@import "frappe/public/css/espresso/…"` lines.

	The bundles are fine: esbuild resolves those at build time. This file is not
	bundled — it is written to `sites/public/files/website_theme/` and served from
	`/files/website_theme/`, so the browser resolves each relative import against
	*that* directory (`/files/website_theme/frappe/public/css/…`), which does not
	exist. Every one 404/502s with an HTML body, so the browser refuses it as the
	wrong MIME type and the espresso base styles never load — 30 failed requests on
	every page view, on every site using a custom theme.

	`public/` is dropped because that is exactly how Frappe serves app assets:
	`<app>/public/css/x.css` is published at `/assets/<app>/css/x.css`.

	Idempotent: already-absolute and remote imports do not match the pattern.
	"""
	try:
		with open(css_path, encoding="utf-8") as f:
			css = f.read()
	except OSError:
		return  # never fail a theme compile over a cosmetic rewrite

	rewritten, count = APP_ASSET_IMPORT.subn(r"\1\g<2>/assets/\3/\4\2", css)
	if not count:
		return

	with open(css_path, "w", encoding="utf-8") as f:
		f.write(rewritten)


def get_scss(website_theme):
	"""
	Render `website_theme_template.scss` with the values defined in Website Theme.

	params:
	website_theme - instance of a Website Theme
	"""
	apps_to_ignore = tuple((d.app + "/") for d in website_theme.ignored_apps)
	available_imports = get_scss_paths()
	imports_to_include = [d for d in available_imports if not d.startswith(apps_to_ignore)]
	context = website_theme.as_dict()
	context["website_theme_scss"] = imports_to_include
	return frappe.render_template("frappe/website/doctype/website_theme/website_theme_template.scss", context)


def get_scss_paths():
	"""
	Return a set of SCSS import paths from all apps that provide `website.scss`.

	If `$BENCH_PATH/apps/frappe/frappe/public/scss/website[.bundle].scss` exists, the
	returned set will contain 'frappe/public/scss/website[.bundle]'.
	"""
	import_path_list = []

	scss_files = ["public/scss/website.scss", "public/scss/website.bundle.scss"]
	for app in frappe.get_installed_apps():
		for scss_file in scss_files:
			full_path = frappe.get_app_path(app, scss_file)
			if path_exists(full_path):
				import_path = splitext(join_path(app, scss_file))[0]
				import_path_list.append(import_path)

	return import_path_list


def after_migrate():
	"""
	Regenerate Active Theme CSS file after migration.

	Necessary to reflect possible changes in the imported SCSS files. Called at
	the end of every `bench migrate`.
	"""
	website_theme = frappe.db.get_single_value("Website Settings", "website_theme")
	if not website_theme or website_theme == "Standard":
		return

	doc = frappe.get_doc("Website Theme", website_theme)
	doc.save()  # Just re-saving re-generates the theme.
