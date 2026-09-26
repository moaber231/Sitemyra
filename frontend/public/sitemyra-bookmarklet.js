/* Sitemyra bookmarklet — "Monitor with Sitemyra"
 *
 * WHAT THIS IS
 *   Drag the "Monitor with Sitemyra" link from your bookmarks bar. Click it
 *   on any public competitor or product page and Sitemyra opens with that
 *   URL pre-filled, ready to analyse.
 *
 * WHY IT IS BUILT THIS WAY (security)
 *   This file contains NO token, NO API key and NO secret of any kind. It
 *   does not talk to the API at all — it only opens the Sitemyra app with
 *   the current URL as a query parameter. Authentication happens in the
 *   app, in the user's own browser session, exactly as it does when they
 *   paste a URL by hand.
 *
 *   That means there is nothing here to leak, nothing to revoke, and no
 *   privileged code running on a third-party page. A browser extension
 *   (Phase 6 of docs/INTELLIGENCE-ROADMAP.md) can do more, but it will
 *   still never hold a billing or channel credential.
 *
 * The one-liner to paste into a bookmark (replace the origin):
 *   javascript:(()=>{window.open('<origin>/dashboard/monitors/new?url='+encodeURIComponent(location.href),'_blank','noopener')})()
 */
(function () {
  "use strict";

  var APP_ORIGIN = document.currentScript
    ? document.currentScript.getAttribute("data-sitemyra-origin")
    : null;

  if (!APP_ORIGIN) {
    return;
  }

  var target = APP_ORIGIN + "/dashboard/monitors/new?url=" + encodeURIComponent(window.location.href);
  window.open(target, "_blank", "noopener");
})();
