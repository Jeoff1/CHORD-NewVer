// Full playback with Spotify's Web Playback SDK (Design-Decisions, Phase 7).
//
// Whenever the SDK can't be used (no Premium, an unsupported browser, a
// refused or missing token, a 429, or no answer in time), the player shows
// a short message and falls back to Spotify's embedded player. Nothing is
// retried automatically. The access token stays in this script's memory:
// it is never written to the page, stored or logged.
(function () {
  "use strict";

  var box = document.querySelector("[data-spotify-player]");
  if (!box) return;
  var toggle = box.querySelector("[data-player-toggle]");
  var status = box.querySelector("[data-player-status]");
  var fallback = document.querySelector("[data-player-fallback]");
  var READY_TIMEOUT_MS = 15000;

  var player = null;
  var deviceId = null;
  var token = null;
  var started = false;
  var fellBack = false;

  function csrfToken() {
    try {
      return JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"] || "";
    } catch (error) {
      return "";
    }
  }

  function fallBack(message) {
    if (fellBack) return;
    fellBack = true;
    status.textContent = message + " Playing in Spotify's player instead.";
    toggle.hidden = true;
    if (fallback) {
      var frame = fallback.querySelector("iframe");
      if (frame && !frame.getAttribute("src")) frame.setAttribute("src", frame.dataset.src);
      fallback.hidden = false;
    }
    if (player) player.disconnect();
  }

  function fetchToken() {
    return fetch(box.dataset.tokenUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
    }).then(function (reply) {
      return reply
        .json()
        .catch(function () {
          return {};
        })
        .then(function (data) {
          if (!reply.ok || !data.access_token) {
            throw new Error(data.error || "Spotify couldn't be reached.");
          }
          token = data.access_token;
          return token;
        });
    });
  }

  function startTrack() {
    toggle.disabled = true;
    fetch(
      "https://api.spotify.com/v1/me/player/play?device_id=" + encodeURIComponent(deviceId),
      {
        method: "PUT",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({ uris: [box.dataset.track] }),
      }
    )
      .then(function (reply) {
        if (reply.status === 429) {
          fallBack("Spotify asked CHORD to wait.");
        } else if (!reply.ok) {
          fallBack("Spotify couldn't start the song here.");
        } else {
          started = true;
          toggle.disabled = false;
        }
      })
      .catch(function () {
        fallBack("Spotify couldn't be reached.");
      });
  }

  toggle.addEventListener("click", function () {
    if (fellBack || !deviceId) return;
    if (!started) startTrack();
    else player.togglePlay();
  });

  window.onSpotifyWebPlaybackSDKReady = function () {
    player = new window.Spotify.Player({
      name: "CHORD",
      volume: 0.8,
      getOAuthToken: function (callback) {
        fetchToken()
          .then(callback)
          .catch(function (error) {
            fallBack(error.message);
          });
      },
    });
    player.addListener("ready", function (event) {
      deviceId = event.device_id;
      toggle.disabled = false;
      status.textContent = "Ready to play in this browser.";
    });
    player.addListener("not_ready", function () {
      fallBack("Spotify stopped playing in this browser.");
    });
    player.addListener("initialization_error", function () {
      fallBack("This browser can't play Spotify here.");
    });
    player.addListener("authentication_error", function () {
      fallBack("Spotify didn't accept your connection; connect Spotify again.");
    });
    player.addListener("account_error", function () {
      fallBack("Full playback needs Spotify Premium.");
    });
    player.addListener("playback_error", function () {
      fallBack("Spotify couldn't play the song here.");
    });
    player.addListener("player_state_changed", function (state) {
      if (state) toggle.textContent = state.paused ? "Play" : "Pause";
    });
    player.connect().then(function (connected) {
      if (!connected) fallBack("Spotify's player couldn't connect.");
    });
  };

  window.setTimeout(function () {
    if (!deviceId) fallBack("Spotify's player didn't start in time.");
  }, READY_TIMEOUT_MS);

  var sdk = document.createElement("script");
  sdk.src = "https://sdk.scdn.co/spotify-player.js";
  sdk.async = true;
  sdk.onerror = function () {
    fallBack("Spotify's player couldn't be loaded.");
  };
  document.head.appendChild(sdk);
})();
