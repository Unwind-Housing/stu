// CLT Stewardship pages: shared helpers (deployed as clt_/pages/pages.js by build_app.py).
// Reads data through the Dataverse Web API as the signed-in user, so people only see counts
// for records they're allowed to see. Navigation goes through the app (Xrm) when it's there.
var CLTPage = (function () {
  var API = location.origin + "/api/data/v9.2/";

  // Formatted values (choice labels, lookup names) come back as <column>@OData.Community.Display.V1.FormattedValue.
  function get(path) {
    return fetch(path.indexOf("http") === 0 ? path : API + path, {
      credentials: "same-origin",
      headers: { "Accept": "application/json", "OData-MaxVersion": "4.0", "OData-Version": "4.0",
                 "Prefer": "odata.maxpagesize=500,odata.include-annotations=\"OData.Community.Display.V1.FormattedValue\"" }
    }).then(function (r) { return r.ok ? r.json() : Promise.reject(new Error(r.status)); });
  }

  // Every row, following the next-page links (up to 25,000 rows).
  function getAll(path) {
    var rows = [];
    function page(p, n) {
      return get(p).then(function (r) {
        rows = rows.concat(r.value);
        return r["@odata.nextLink"] && n < 50 ? page(r["@odata.nextLink"], n + 1) : rows;
      });
    }
    return page(path, 0);
  }

  // Change data: patch("clt_applications(<id>)", {...}), post("clt_eligibilitychecks", {...}), del("clt_x(<id>)").
  function send(method, path, body) {
    var headers = { "Accept": "application/json", "OData-MaxVersion": "4.0", "OData-Version": "4.0" };
    if (body) headers["Content-Type"] = "application/json; charset=utf-8";
    if (method === "PATCH") headers["If-Match"] = "*";   // update only, never create
    return fetch(API + path, { method: method, credentials: "same-origin", headers: headers,
                               body: body ? JSON.stringify(body) : undefined }).then(function (r) {
      if (r.ok) return true;
      return r.json().then(function (e) { throw new Error((e.error && e.error.message) || r.status); },
                           function () { throw new Error(r.status); });
    });
  }
  function patch(path, body) { return send("PATCH", path, body); }
  function post(path, body) { return send("POST", path, body); }
  function del(path) { return send("DELETE", path); }

  // {label: value} for a global choice, for example choice("clt_checkresult").Pass
  function choice(name) {
    return get("GlobalOptionSetDefinitions(Name='" + name + "')").then(function (r) {
      var out = {};
      (r.Options || []).forEach(function (o) {
        var l = o.Label && o.Label.UserLocalizedLabel && o.Label.UserLocalizedLabel.Label;
        if (l) out[l] = o.Value;
      });
      return out;
    });
  }

  // The label Dataverse shows for a column (choice label, lookup name), or "".
  function fv(row, col) { return row[col + "@OData.Community.Display.V1.FormattedValue"] || ""; }

  function confirmBox(title, text) {
    var X = xrm();
    if (X && X.Navigation && X.Navigation.openConfirmDialog) {
      return X.Navigation.openConfirmDialog({ title: title, text: text }).then(function (r) { return r.confirmed; });
    }
    return Promise.resolve(window.confirm(title + "\n\n" + text));
  }

  function openRecord(entity, id) { return go({ pageType: "entityrecord", entityName: entity, entityId: id }); }

  function xrm() {
    try { return window.parent.Xrm || window.Xrm || null; } catch (e) { return null; }
  }

  // Client settings (environment variables clt_*): {OrgName, BrandHeaderColor, ...}
  function settings() {
    return Promise.all([
      get("environmentvariabledefinitions?$select=environmentvariabledefinitionid,schemaname,defaultvalue" +
          "&$filter=startswith(schemaname,'clt_')"),
      get("environmentvariablevalues?$select=value,_environmentvariabledefinitionid_value")
    ]).then(function (r) {
      var vals = {}, out = {};
      r[1].value.forEach(function (v) { vals[v._environmentvariabledefinitionid_value] = v.value; });
      r[0].value.forEach(function (d) {
        out[d.schemaname.replace(/^clt_/, "")] = vals[d.environmentvariabledefinitionid] || d.defaultvalue || "";
      });
      return out;
    }).catch(function () { return {}; });
  }

  // Apply the brand: colors, organization name ([data-org]) and the logo ([data-logo]).
  function brand() {
    return settings().then(function (s) {
      var root = document.documentElement.style;
      if (/^#[0-9a-f]{6}$/i.test(s.BrandHeaderColor || "")) root.setProperty("--brand", s.BrandHeaderColor);
      if (/^#[0-9a-f]{6}$/i.test(s.BrandAccentColor || "")) root.setProperty("--accent", s.BrandAccentColor);
      var org = s.OrgName || "your land trust";
      document.querySelectorAll("[data-org]").forEach(function (el) { el.textContent = org; });
      document.querySelectorAll("img[data-logo]").forEach(function (img) {
        img.onerror = function () { img.style.display = "none"; };
        img.src = "../../clt_brandlogo";  // uploaded by tools/apply_branding.py
        img.alt = org;
      });
      return s;
    });
  }

  var setNames = {};
  function entitySet(entity) {
    if (!setNames[entity]) {
      setNames[entity] = get("EntityDefinitions(LogicalName='" + entity + "')?$select=EntitySetName")
        .then(function (r) { return r.EntitySetName; });
    }
    return setNames[entity];
  }

  // A saved view by name: {id, count, more}. Counting runs the view itself, so the number always
  // matches the list people see when they click through. Resolves null if the view isn't there.
  function viewCount(entity, viewName) {
    return get("savedqueries?$select=savedqueryid&$filter=returnedtypecode eq '" + entity +
               "' and name eq '" + viewName.replace(/'/g, "''") + "' and statecode eq 0")
      .then(function (r) {
        if (!r.value.length) return null;
        var id = r.value[0].savedqueryid;
        return entitySet(entity).then(function (es) {
          return get(es + "?savedQuery=" + id).then(function (d) {
            return { id: id, count: d.value.length, more: !!d["@odata.nextLink"] };
          });
        });
      })
      .catch(function () { return null; });
  }

  function go(page) {
    var X = xrm();
    if (X && X.Navigation) return X.Navigation.navigateTo(page);
    // Outside the app (opened directly): fall back to plain links.
    var q = page.pageType === "entityrecord" ? "pagetype=entityrecord&etn=" + page.entityName + (page.entityId ? "&id=" + page.entityId : "")
          : page.pageType === "entitylist" ? "pagetype=entitylist&etn=" + page.entityName + (page.viewId ? "&viewid=" + page.viewId : "")
          : "pagetype=webresource&webresourceName=" + encodeURIComponent(page.webresourceName) +
            (page.data ? "&data=" + encodeURIComponent(page.data) : "");
    window.top.location.href = location.origin + "/main.aspx?" + q;
  }
  function openList(entity, viewId) { return go({ pageType: "entitylist", entityName: entity, viewId: viewId }); }
  function newRecord(entity) { return go({ pageType: "entityrecord", entityName: entity }); }
  function openGuide(id) { return go({ pageType: "webresource", webresourceName: "clt_/pages/guides.html", data: id || "" }); }

  // Wire up any element with data-new="clt_property", data-list="clt_property" or data-guide="property".
  function wire(rootEl) {
    (rootEl || document).querySelectorAll("[data-new],[data-list],[data-guide]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        if (el.dataset.new) newRecord(el.dataset.new);
        else if (el.dataset.list) openList(el.dataset.list);
        else openGuide(el.dataset.guide);
      });
    });
  }

  return { get: get, getAll: getAll, patch: patch, post: post, del: del, choice: choice, entitySet: entitySet,
           fv: fv, confirm: confirmBox, brand: brand, settings: settings,
           viewCount: viewCount, go: go, openList: openList, newRecord: newRecord, openRecord: openRecord,
           openGuide: openGuide, wire: wire };
})();
