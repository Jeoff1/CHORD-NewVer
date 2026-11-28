/*
 * The church address's location picker (church/includes/location_picker.html; the owner,
 * 28 Nov 2026). "Use my current location" asks the browser for the device's position; "Pick on
 * the map" opens an OpenStreetMap map to click or drag a pin on. The spot is turned into an
 * address by OpenStreetMap's Nominatim service and written into the address field, which the
 * person can still edit. Nothing about the spot is stored: only the address text is sent with
 * the form.
 *
 * Nominatim's usage policy: at most one lookup a second, made only when the person acts, with
 * OpenStreetMap credited on the map. Lookups wait their turn and only the latest one counts.
 *
 * OpenStreetMap's tile and Nominatim servers refuse browser requests that don't say which site
 * they come from. CHORD's pages send "Referrer-Policy: same-origin" (Django's default), which
 * would leave the Referer off, so the map and the lookups ask for the site's origin only
 * (never the page's path) to be sent.
 */
(function () {
  "use strict";

  var NOMINATIM = "https://nominatim.openstreetmap.org/";
  var TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  var CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  var WORLD = { lat: 20, lon: 0, zoom: 2 };
  var REFERRER = "strict-origin-when-cross-origin";
  var lastCall = 0;

  // One request a second at most, across every picker on the page.
  function politely(run) {
    var wait = Math.max(0, 1100 - (Date.now() - lastCall));
    return setTimeout(function () {
      lastCall = Date.now();
      run();
    }, wait);
  }

  function getJson(url) {
    return fetch(url, {
      headers: { Accept: "application/json" },
      referrerPolicy: REFERRER,
    }).then(function (response) {
      if (!response.ok) throw new Error("lookup failed");
      return response.json();
    });
  }

  function setUp(root) {
    var target = document.getElementById(root.getAttribute("data-target"));
    if (!target || !window.L || !window.fetch) return;
    var mapBox = root.querySelector("[data-loc-map]");
    var status = root.querySelector("[data-loc-status]");
    var openButton = root.querySelector("[data-loc-open]");
    var map = null;
    var marker = null;
    var timer = null;
    var asked = 0;

    root.hidden = false;

    function say(text) {
      status.textContent = text;
    }

    function showMap(lat, lon, zoom) {
      mapBox.hidden = false;
      openButton.setAttribute("aria-expanded", "true");
      if (!map) {
        map = window.L.map(mapBox).setView([lat, lon], zoom);
        window.L.tileLayer(TILES, {
          maxZoom: 19,
          attribution: CREDIT,
          referrerPolicy: REFERRER,
        }).addTo(map);
        map.on("click", function (event) {
          pin(event.latlng.lat, event.latlng.lng, true);
        });
      } else {
        map.setView([lat, lon], zoom);
      }
      // The box was hidden until now, so the map measures itself again.
      setTimeout(function () { map.invalidateSize(); }, 0);
    }

    function pin(lat, lon, lookUp) {
      if (!marker) {
        marker = window.L.marker([lat, lon], { draggable: true, keyboard: true, title: "The church" }).addTo(map);
        marker.on("dragend", function () {
          var spot = marker.getLatLng();
          fillAddress(spot.lat, spot.lng);
        });
      } else {
        marker.setLatLng([lat, lon]);
      }
      if (lookUp) fillAddress(lat, lon);
    }

    function fillAddress(lat, lon) {
      var mine = ++asked;
      clearTimeout(timer);
      say("Finding the address…");
      timer = politely(function () {
        var url = NOMINATIM + "reverse?format=jsonv2&zoom=18&lat=" + encodeURIComponent(lat) +
          "&lon=" + encodeURIComponent(lon);
        getJson(url).then(function (place) {
          if (mine !== asked) return;
          if (place && place.display_name) {
            target.value = place.display_name;
            target.dispatchEvent(new Event("input", { bubbles: true }));
            say("Address filled in. Check it, and edit it if you need to.");
          } else {
            say("No address was found there. Type it in instead.");
          }
        }).catch(function () {
          if (mine === asked) say("The address couldn't be looked up. Type it in instead.");
        });
      });
    }

    // Opening the map on an address already typed starts there, without changing the text.
    function openOnTypedAddress() {
      var typed = target.value.trim();
      showMap(WORLD.lat, WORLD.lon, WORLD.zoom);
      if (!typed) {
        say("Click the map where the church is, then drag the pin to adjust.");
        return;
      }
      say("Finding the address on the map…");
      politely(function () {
        getJson(NOMINATIM + "search?format=jsonv2&limit=1&q=" + encodeURIComponent(typed)).then(function (found) {
          if (found && found.length) {
            var lat = parseFloat(found[0].lat);
            var lon = parseFloat(found[0].lon);
            map.setView([lat, lon], 17);
            pin(lat, lon, false);
            say("Drag the pin or click the map to change the address.");
          } else {
            say("That address isn't on the map. Click where the church is.");
          }
        }).catch(function () {
          say("Click the map where the church is, then drag the pin to adjust.");
        });
      });
    }

    openButton.addEventListener("click", openOnTypedAddress);

    root.querySelector("[data-loc-here]").addEventListener("click", function () {
      if (!navigator.geolocation) {
        say("This browser can't share its location. Use Pick on the map instead.");
        return;
      }
      say("Asking for your location…");
      navigator.geolocation.getCurrentPosition(
        function (position) {
          var lat = position.coords.latitude;
          var lon = position.coords.longitude;
          showMap(lat, lon, 17);
          pin(lat, lon, true);
        },
        function (error) {
          say(error.code === 1
            ? "Location access is blocked for this site. Use Pick on the map instead."
            : "Your location couldn't be found. Use Pick on the map instead.");
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
      );
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll("[data-location-picker]"), setUp);
  });
})();
