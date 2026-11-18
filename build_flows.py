#!/usr/bin/env python3
"""
CLT Stewardship: Power Automate cloud flows, kept in source control and deployed into the solution.

Flows here:
  - Property document folder, Household document folder: when a record has a name and no
    SharePoint folder yet, create one in the table's library and link it to the record.
    Property: "<address> - <record number>" (testing 123, Unit 201 - P-00004).
    Household: "<last name> - <record number>" (Rivera - H-00001). Dataverse's own are "<name>_<GUID>".
  - Screener intake (flows_intake.py): the forms platform posts each screener entry to the flow's
    web address; the flow creates or updates the household, its members and the application.
    After the flow is on, copy its HTTP URL (open the flow > the trigger) into Cognito:
    form > Build > Settings (gear) > Submission Settings > Post JSON Data to a Website, for both
    Submit Entry Endpoint and Update Entry Endpoint. The URL is a secret: anyone with it can post.
    Every screener form uses the same URL. A new form works without a rebuild if it is a Cognito
    copy of the screener (same field names); its first entry adds its Source form row. A Source
    form with a project sends that form's new applications straight into the project.
  - Full application intake (flows_full_app.py): same set-up, its own web address, pasted into the
    full application form. Finds the application by the form's Application Number (from the invite
    link), then by email, and adds the members, income sources, debts and assets.

The flows find the SharePoint site (the default site record) and the library (its document
location) in Dataverse, so nothing client-specific is built in.

Connections can't be created by a script (each one is a person's sign-in). The first time,
the build creates the connection references empty and the flows switched off. Run the build
signed in as the service account (CLT Flow Automation, with Power Apps Premium), so it owns the
flows; then, signed in as that account:
  make.powerautomate.com > Solutions > CLT Stewardship > Objects > Connection references >
  fill "CLT Stewardship: Dataverse" and "CLT Stewardship: SharePoint" with its connections
  (don't "Add new" inside the flow: that makes extra references) > each flow > Turn on.
After that, re-running the build updates the flow definitions in place.

Usage:
  python3 build_flows.py --check
  python3 build_flows.py --url https://yourorg.crm.dynamics.com
"""
import argparse
import json
import os
import sys
import uuid

import form_mapping
from flows_intake import screener_flow
from flows_full_app import full_application_flow
from flows_verification import verification_flow
from build_schema import (Dataverse, DataverseError, Log, make_token_provider, DEFAULT_CLIENT_ID,
                          SOLUTION, PREFIX)

DATAVERSE = "shared_commondataserviceforapps"
SHAREPOINT = "shared_sharepointonline"
CONNECTION_REFERENCES = {
    DATAVERSE: (f"{PREFIX}_dataverse", "CLT Stewardship: Dataverse"),
    SHAREPOINT: (f"{PREFIX}_sharepoint", "CLT Stewardship: SharePoint"),
}
# Characters SharePoint doesn't allow in folder names.
BAD_CHARS = ['"', "*", ":", "<", ">", "?", "/", "\\", "|", "#", "%"]


def api(connector):
    return f"/providers/Microsoft.PowerApps/apis/{connector}"


def op(connector, operation, parameters, run_after=None):
    action = {"type": "OpenApiConnection",
              "inputs": {"host": {"connectionName": connector, "operationId": operation, "apiId": api(connector)},
                         "parameters": parameters, "authentication": "@parameters('$authentication')"}}
    if run_after is not None:
        action["runAfter"] = run_after
    return action


def safe_name(expr):
    """Expression: expr with SharePoint's forbidden characters removed, trimmed."""
    for ch in BAD_CHARS:
        expr = f"replace({expr}, '{ch.replace(chr(39), chr(39) * 2)}', '')"
    return f"trim({expr})"


def folder_flow(table, entity_set, label, folder_style="name-number"):
    """Definition of the '<label> document folder' flow for clt_<table>."""
    t = f"{PREFIX}_{table}"
    rec = f"triggerOutputs()?['body/{t}id']"
    name = f"triggerOutputs()?['body/{PREFIX}_name']"
    number = f"triggerOutputs()?['body/{PREFIX}_recordnumber']"
    if folder_style == "lastname-number":
        # "Rivera, Maria" -> "Rivera": the household name up to any comma
        base = f"trim(first(split(coalesce({name}, ''), ',')))"
    else:
        base = f"coalesce({name}, '')"
    folder = safe_name(f"concat({base}, ' - ', coalesce({number}, ''))")
    library = "first(outputs('Find_library')?['body/value'])?['sharepointdocumentlocationid']"
    parents = "outputs('Find_parent_folder')?['body/value']"
    parent = f"first({parents})"
    site_path = "uriPath(first(outputs('Find_site')?['body/value'])?['absoluteurl'])"

    def sp_folder(body, run_after=None):
        return op(SHAREPOINT, "HttpRequest", {
            "dataset": "@first(outputs('Find_site')?['body/value'])?['absoluteurl']",
            "parameters/method": "POST",
            "parameters/uri": "_api/web/folders",
            "parameters/headers": {"Accept": "application/json;odata=nometadata",
                                   "Content-Type": "application/json;odata=nometadata"},
            "parameters/body": body}, **({"run_after": run_after} if run_after else {}))
    has_folder = {
        "Find_existing_folder": op(DATAVERSE, "ListRecords", {
            "entityName": "sharepointdocumentlocations",
            "$select": "sharepointdocumentlocationid",
            "$filter": f"_regardingobjectid_value eq @{{{rec}}}",
            "$top": 1}),
        "If_no_folder_yet": {
            "type": "If", "runAfter": {"Find_existing_folder": ["Succeeded"]},
            "expression": {"equals": ["@length(outputs('Find_existing_folder')?['body/value'])", 0]},
            "actions": {
                "Find_site": op(DATAVERSE, "ListRecords", {
                    "entityName": "sharepointsites", "$select": "absoluteurl",
                    "$filter": "isdefault eq true", "$top": 1}),
                "Find_library": op(DATAVERSE, "ListRecords", {
                    "entityName": "sharepointdocumentlocations", "$select": "sharepointdocumentlocationid",
                    "$filter": f"relativeurl eq '{t}' and statecode eq 0", "$top": 1},
                    run_after={"Find_site": ["Succeeded"]}),
                # A parent folder inside the library (for example DEV), if this environment has one: a document
                # location under the library that isn't tied to a record. build_schema.py --sharepoint-folder adds it.
                "Find_parent_folder": op(DATAVERSE, "ListRecords", {
                    "entityName": "sharepointdocumentlocations",
                    "$select": "sharepointdocumentlocationid,relativeurl",
                    "$filter": f"_parentsiteorlocation_value eq @{{{library}}} and _regardingobjectid_value eq null"
                               " and statecode eq 0",
                    "$top": 1},
                    run_after={"Find_library": ["Succeeded"]}),
                "Parent_folder": {"type": "Compose", "runAfter": {"Find_parent_folder": ["Succeeded"]},
                                  "inputs": f"@{{if(empty({parents}), '', concat({parent}?['relativeurl'], '/'))}}"},
                "Folder_name": {"type": "Compose", "runAfter": {"Parent_folder": ["Succeeded"]},
                                "inputs": f"@{folder}"},
                "If_parent_folder": {
                    "type": "If", "runAfter": {"Folder_name": ["Succeeded"]},
                    "expression": {"not": {"equals": ["@outputs('Parent_folder')", ""]}},
                    # SharePoint hands back the folder if it's already there, so this is safe every time.
                    "actions": {"Create_parent_folder_in_SharePoint": sp_folder(
                        "@{concat('{\"ServerRelativeUrl\":\"', " + site_path + ", '/" + t + "/', "
                        + parent + "?['relativeurl'], '\"}')}")},
                    "else": {"actions": {}}},
                "Folder_request": {
                    "type": "Compose", "runAfter": {"If_parent_folder": ["Succeeded"]},
                    "inputs": {"ServerRelativeUrl": f"@{{concat({site_path}, '/{t}/', outputs('Parent_folder'), "
                                                    "outputs('Folder_name'))}"}},
                "Create_folder_in_SharePoint": sp_folder("@{string(outputs('Folder_request'))}",
                                                         run_after={"Folder_request": ["Succeeded"]}),
                "Link_folder_to_record": op(DATAVERSE, "CreateRecord", {
                    "entityName": "sharepointdocumentlocations",
                    "item/name": f"@{{outputs('Folder_name')}}",
                    "item/relativeurl": "@{outputs('Folder_name')}",
                    "item/parentsiteorlocation_sharepointdocumentlocation@odata.bind":
                        f"/sharepointdocumentlocations(@{{coalesce({parent}?['sharepointdocumentlocationid'], {library})}})",
                    f"item/regardingobjectid_{t}@odata.bind": f"/{entity_set}(@{{{rec}}})"},
                    run_after={"Create_folder_in_SharePoint": ["Succeeded"]}),
                "Save_folder_link": op(DATAVERSE, "UpdateRecord", {
                    "entityName": entity_set,
                    "recordId": f"@{{{rec}}}",
                    f"item/{PREFIX}_documentsfolder":
                        "@{concat(first(outputs('Find_site')?['body/value'])?['absoluteurl'], "
                        f"'/{t}/', outputs('Parent_folder'), uriComponent(outputs('Folder_name')))}}"},
                    run_after={"Link_folder_to_record": ["Succeeded"]}),
            },
            "else": {"actions": {}},
        },
    }
    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        "triggers": {
            f"When_a_{table}_is_saved": {
                "type": "OpenApiConnectionWebhook",
                # One run at a time, so a create and a quick rename can't both make a folder.
                "runtimeConfiguration": {"concurrency": {"runs": 1}},
                "inputs": {"host": {"connectionName": DATAVERSE, "operationId": "SubscribeWebhookTrigger",
                                    "apiId": api(DATAVERSE)},
                           "parameters": {"subscriptionRequest/message": 4,  # added or modified
                                          "subscriptionRequest/entityname": t,
                                          "subscriptionRequest/scope": 4,  # whole organization
                                          "subscriptionRequest/filteringattributes": f"{PREFIX}_name"},
                           "authentication": "@parameters('$authentication')"},
                # Households get their name a moment after they're created; wait until there is one.
                "conditions": [{"expression": f"@not(empty(triggerBody()?['{PREFIX}_name']))"}],
            }
        },
        "actions": has_folder,
    }
    return {
        "name": f"CLT: {label} document folder",
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"clt-stewardship/flows/{table}-document-folder")),
        "description": f"Creates the {label.lower()}'s SharePoint folder with a readable name and links it.",
        "definition": definition,
    }


def intake_flows(folder):
    """One intake flow per form mapping in an organization's folder (clients/<organization>/forms/*.json):
    screeners first, then full applications, then annual verifications. Forms that are copies of each other share a mapping and a flow."""
    build = {"screener": screener_flow, "full-application": full_application_flow, "annual-verification": verification_flow}
    return [build[m.type](m) for m in form_mapping.mappings(folder)]


def flows_for(folder=None):
    """Every flow for an organization: the three document folder flows, then its intake flows."""
    return [
        folder_flow("property", "clt_properties", "Property"),
        folder_flow("household", "clt_households", "Household", "lastname-number"),
        folder_flow("occupancy", "clt_occupancies", "Occupancy"),   # "Rivera - 12 Pine St - O-00001"
    ] + (intake_flows(folder) if folder else [])


EXAMPLE = os.path.join(form_mapping.CLIENTS, "example")
FLOWS = flows_for(EXAMPLE)   # the example organization's flows: what --check and the tests look at


def connectors_used(flow):
    return {a["inputs"]["host"]["connectionName"] for a in _actions(flow["definition"])
            if a.get("type", "").startswith("OpenApi")}


def clientdata(flow):
    refs = {c: {"runtimeSource": "embedded", "connection": {"connectionReferenceLogicalName": CONNECTION_REFERENCES[c][0]},
                "api": {"name": c}} for c in CONNECTION_REFERENCES if c in connectors_used(flow)}
    return json.dumps({"properties": {"connectionReferences": refs, "definition": flow["definition"]},
                       "schemaVersion": "1.0.0.0"}, separators=(",", ":"))


def check_spec(flows=None):
    problems = []
    for f in flows or FLOWS:
        used = connectors_used(f)
        if not used:
            problems.append(f"{f['name']}: uses no connections")
        if used - set(CONNECTION_REFERENCES):
            problems.append(f"{f['name']}: unknown connections {used - set(CONNECTION_REFERENCES)}")
        # every runAfter points at a sibling
        for scope in _scopes(f["definition"]):
            for k, a in scope.items():
                for dep in a.get("runAfter", {}):
                    if dep not in scope:
                        problems.append(f"{f['name']}: {k} runs after missing {dep}")
    return problems


def _scopes(defn):
    yield defn["actions"]
    stack = list(defn["actions"].values())
    while stack:
        a = stack.pop()
        for key in ("actions",):
            if isinstance(a.get(key), dict):
                yield a[key]; stack += a[key].values()
        if isinstance(a.get("else"), dict) and a["else"].get("actions"):
            yield a["else"]["actions"]; stack += a["else"]["actions"].values()


def _actions(defn):
    for scope in _scopes(defn):
        yield from scope.values()
    yield from defn["triggers"].values()


def ensure_connection_references(dv, log):
    for connector, (logical, display) in CONNECTION_REFERENCES.items():
        r = dv.call("GET", f"connectionreferences?$select=connectionreferenceid,connectionid"
                           f"&$filter=connectionreferencelogicalname eq '{logical}'").get("value", [])
        if r:
            log.skipped(f"Connection reference {display}" + ("" if r[0].get("connectionid") else " (no connection picked yet)"))
            continue
        dv.call("POST", "connectionreferences", {"connectionreferencelogicalname": logical,
                                                 "connectionreferencedisplayname": display,
                                                 "connectorid": api(connector)})
        log.created(f"Connection reference {display}")


def deploy_flow(dv, log, flow):
    data = clientdata(flow)
    r = dv.call("GET", f"workflows?$select=workflowid,clientdata,statecode&$filter=workflowid eq {flow['id']}").get("value", [])
    if not r:
        dv.call("POST", "workflows", {"workflowid": flow["id"], "name": flow["name"], "description": flow["description"],
                                      "category": 5, "type": 1, "primaryentity": "none", "clientdata": data})
        log.created(f"{flow['name']} (off until its connections are picked)")
        return
    if r[0].get("clientdata") == data:
        log.skipped(flow["name"])
        return
    was_on = r[0].get("statecode") == 1
    try:
        dv.call("PATCH", f"workflows({flow['id']})", {"clientdata": data, "description": flow["description"]})
        log.created(f"{flow['name']} updated")
    except DataverseError as e:
        log(f"  ! {flow['name']}: couldn't update ({e}). Turn the flow off, re-run, then turn it on.")
        return
    # An update can switch a flow off. Turn it back on if it was on (works when signed in as its owner).
    now = dv.call("GET", f"workflows({flow['id']})?$select=statecode").get("statecode")
    if was_on and now != 1:
        try:
            dv.call("PATCH", f"workflows({flow['id']})", {"statecode": 1, "statuscode": 2})
            log("    turned back on")
        except DataverseError as e:
            log(f"  ! {flow['name']} was switched off by the update and couldn't be turned back on ({e});"
                " turn it on in Power Automate.")


def run(dv, log, require_service_account=False, only=None, flows=None):
    flows = flows or FLOWS
    log(f"Environment: {dv.base}")
    try:
        me = dv.call("GET", "WhoAmI")
        u = dv.call("GET", f"systemusers({me['UserId']})?$select=fullname,domainname")
        log(f"Signed in as {u.get('fullname')} ({u.get('domainname')})")
        if "automation" not in (u.get("domainname") or "").lower():
            msg = ("New flows would be owned by this account, and a flow only turns on if its owner has a premium"
                   " license and owns its connections. Sign in as the service account (CLT Flow Automation).")
            if require_service_account:
                raise DataverseError(msg + " Nothing was changed. (--any-owner builds anyway.)")
            log("  ! " + msg)
    except DataverseError as e:
        if require_service_account and "Nothing was changed" in str(e):
            raise
    log("\nConnection references")
    ensure_connection_references(dv, log)
    log("\nFlows")
    for f in flows:
        if only and only.lower() not in f["name"].lower():
            log(f"  - {f['name']} (left alone: --only {only})")
            continue
        deploy_flow(dv, log, f)
    log("\nIf a flow is new or shows 'no connection picked': make.powerautomate.com > Solutions > CLT Stewardship >"
        " the flow > Edit > pick its connections (Dataverse, and SharePoint for the folder flows) > Save > Turn on.")
    log("Screener and full application intake: once each is on, copy the web address from its trigger into the forms platform's"
        " 'post JSON on submit' and 'on update' settings (see the top of build_flows.py).")


def service_account_for(folder):
    """The flow service account from an organization's client.json, or None."""
    try:
        return json.load(open(form_mapping.client_file(folder), encoding="utf-8")).get("flowServiceAccount")
    except (OSError, ValueError, TypeError):
        return None


def check_all():
    """Check the example's flows and those of every other organization folder on this machine."""
    problems, count = [], 0
    for folder in form_mapping.client_dirs():
        try:
            flows = flows_for(folder)
        except form_mapping.MappingError as e:
            problems.append(str(e))
            continue
        count = max(count, len(flows))
        problems += [f"{os.path.basename(folder)}: {p}" for p in check_spec(flows)]
    return problems, count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url")
    ap.add_argument("--check", action="store_true", help="Check the flow definitions. No sign-in.")
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    ap.add_argument("--as", dest="account",
                    help="Account to sign in as. Default: flowServiceAccount from the organization's client.json. "
                         "Flows are owned by whoever signs in.")
    ap.add_argument("--client", help="The organization's folder, for example clients/yourname. Default: the folder "
                                     "under clients/ whose client.json lists --url under environments.")
    ap.add_argument("--any-owner", action="store_true",
                    help="Build even if the signed-in account isn't the service account (flows then can't turn on "
                         "unless that account has a premium license).")
    ap.add_argument("--only", help="Deploy only the flows whose name contains this text, for example \"document folder\". "
                                   "The others are left exactly as they are.")
    args = ap.parse_args()
    problems, count = check_all()
    if problems or args.check:
        print("\n".join(problems) or f"{count} flows look good.")
        sys.exit(1 if problems else 0)
    if not args.url:
        sys.exit("Give --url (or --check).")
    folder = args.client or form_mapping.client_for(args.url)
    if not folder or not os.path.isfile(form_mapping.client_file(folder)):
        sys.exit("No organization folder for this environment. Copy clients/example to clients/<yourname>, put this "
                 "address under \"environments\" in its client.json, or pass --client clients/<yourname>.")
    try:
        flows = flows_for(folder)
    except form_mapping.MappingError as e:
        sys.exit(f"STOPPED: {e}")
    print(f"Organization folder: {folder} ({len(flows) - 3} intake flows from its form mappings)")
    account = args.account or service_account_for(folder)
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code, account),
                   SOLUTION)
    log = Log("flows-build-log.txt")
    try:
        run(dv, log, require_service_account=not args.any_owner, only=args.only, flows=flows)
    except DataverseError as e:
        sys.exit(f"\nSTOPPED: {e}")


if __name__ == "__main__":
    main()
