import frappe

from frappe.desk.doctype.desktop_icon.desktop_icon import (
	clear_desktop_icons_cache,
	create_desktop_icons_from_installed_apps,
	create_desktop_icons_from_workspace,
	is_desk_route,
	should_hide_workspace_icon,
)


def execute():
	create_desktop_icons_from_installed_apps()
	create_desktop_icons_from_workspace()

	workspace_routes_by_app = {}
	for workspace in frappe.get_all(
		"Workspace",
		filters={"public": 1, "name": ["!=", "Welcome Workspace"]},
		fields=["name", "app", "module"],
	):
		workspace_app = workspace.app or (
			frappe.db.get_value("Module Def", workspace.module, "app_name") if workspace.module else None
		)
		if not workspace_app:
			continue
		workspace_routes_by_app.setdefault(workspace_app, []).append(workspace.name)

	for app_name in frappe.get_installed_apps():
		app_details = frappe.get_hooks("add_to_apps_screen", app_name=app_name)
		if not app_details:
			continue

		app_detail = app_details[0]
		app_route = app_detail.get("route")
		app_logo = app_detail.get("logo")
		app_title = frappe.get_hooks("app_title", app_name=app_name)[0]

		app_icon_name = frappe.db.exists("Desktop Icon", {"icon_type": "App", "app": app_name})
		if app_icon_name:
			frappe.db.set_value("Desktop Icon", str(app_icon_name), "label", app_title, update_modified=False)
			frappe.db.set_value("Desktop Icon", str(app_icon_name), "link", app_route, update_modified=False)
			frappe.db.set_value(
				"Desktop Icon", str(app_icon_name), "logo_url", app_logo, update_modified=False
			)

		for workspace_name in workspace_routes_by_app.get(app_name, []):
			workspace_icon_name = frappe.db.exists(
				"Desktop Icon", {"icon_type": "Link", "link_type": "Workspace Sidebar", "link_to": workspace_name}
			)
			if not workspace_icon_name:
				continue

			parent_icon = app_icon_name if app_icon_name and is_desk_route(app_route) else None
			hidden = 1 if should_hide_workspace_icon(app_route, workspace_name, app_title) else 0
			frappe.db.set_value(
				"Desktop Icon",
				str(workspace_icon_name),
				"parent_icon",
				parent_icon,
				update_modified=False,
			)
			frappe.db.set_value(
				"Desktop Icon", str(workspace_icon_name), "hidden", hidden, update_modified=False
			)

	clear_desktop_icons_cache()
	frappe.db.commit()
