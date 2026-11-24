// Full playback with Spotify's Web Playback SDK (Design-Decisions, Phase 7),
// in the "Listen" card (Phase 9A, A7).
//
// Whenever the SDK can't be used (no Premium, an unsupported browser, a
// refused or missing token, a 429, or no answer in time), the player shows
// a short message and falls back to Spotify's embedded player inside the
// same card. Nothing is retried automatically. The access token stays in
// this script's memory: it is never written to the page, stored or logged.
// The cover comes from the SDK's player state and is shown in this browser
// only: it is never sent to CHORD or stored.
(function () {
  "use strict";

  var box = document.querySelector("[data-spotify-player]");
  if (!box) return;
  var controls = box.querySelector("[data-player-controls]");
  var toggle = box.querySelector("[data-player-toggle]");
  var back = box.querySelector("[data-player-back]");
  var forward = box.querySelector("[data-player-forward]");
  var status = box.querySelector("[data-player-status]");
  var progress = box.querySelector("[data-player-progress]");
  var fill = box.querySelector("[data-player-fill]");
  var elapsedText = box.querySelector("[data-player-elapsed]");
  var totalText = box.querySelector("[data-player-total]");
  var cover = box.querySelector("[data-player-cover]");
  var playIcon = toggle.querySelector("[data-icon-play]");
  var pauseIcon = toggle.querySelector("[data-icon-pause]");
  var fallback = document.querySelector("[data-player-fallback]");
  var READY_TIMEOUT_MS = 15000;
  var TICK_MS = 1000;
  var SKIP_MS = 10000;

  var player = null;
  var deviceId = null;
  var token = null;
  var started = false;
  var fellBack = false;
  var paused = true;
  var position = 0;
  var duration = parseInt(box.dataset.lengthMs, 10) || 0;
  var ticker = null;

  function csrfToken() {
    try {
      return JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"] || "";
    } catch (error) {
      return "";
    }
  }

  function clock(ms) {
    var seconds = Math.max(0, Math.floor(ms / 1000));
    var minutes = Math.floor(seconds / 60);
    seconds = seconds % 60;
    return minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
  }

  function render() {
    var percent = duration ? Math.min(100, Math.round((position / duration) * 100)) : 0;
    fill.style.width = percent + "%";
    progress.setAttribute("aria-valuenow", String(percent));
    progress.setAttribute("aria-valuetext", clock(position) + " of " + clock(duration));
    elapsedText.textContent = clock(position);
    if (duration) totalText.textContent = clock(duration);
  }

  function showPaused(isPaused) {
    paused = isPaused;
    playIcon.hidden = !isPaused;
    pauseIcon.hidden = isPaused;
    toggle.setAttribute("aria-label", isPaused ? "Play" : "Pause");
  }

  function enableControls() {
    toggle.disabled = !deviceId;
    back.disabled = !started;
    forward.disabled = !started;
  }

  function stopTicking() {
    if (ticker) {
      window.clearInterval(ticker);
      ticker = null;
    }
  }

  function startTicking() {
    if (ticker || paused || fellBack || document.hidden || !player) return;
    ticker = window.setInterval(function () {
      player.getCurrentState().then(function (state) {
        if (state) takeState(state);
        else stopTicking();
      });
    }, TICK_MS);
  }

  function showCover(track) {
    var images = track && track.album && track.album.images;
    if (!cover || !images || !images.length) return;
    var sorted = images.slice().sort(function (a, b) {
      return (a.width || 0) - (b.width || 0);
    });
    var pick = sorted.filter(function (image) {
      return (image.width || 0) >= 64;
    })[0] || sorted[sorted.length - 1];
    if (pick && /^https:\/\//.test(pick.url) && cover.getAttribute("src") !== pick.url) {
      cover.setAttribute("src", pick.url);
      cover.hidden = false;
    }
  }

  function takeState(state) {
    position = state.position || 0;
    if (state.duration) duration = state.duration;
    showPaused(state.paused);
    showCover(state.track_window && state.track_window.current_track);
    render();
    if (state.paused) stopTicking();
    else startTicking();
  }

  function fallBack(message) {
    if (fellBack) return;
    fellBack = true;
    stopTicking();
    status.textContent = message + " Playing in Spotify's player instead.";
    if (controls) controls.hidden = true;
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
          enableControls();
        }
      })
      .catch(function () {
        fallBack("Spotify couldn't be reached.");
      });
  }

  function skip(delta) {
    if (!started || fellBack || !player) return;
    player.getCurrentState().then(function (state) {
      var from = state ? state.position : position;
      var length = (state && state.duration) || duration;
      var target = Math.max(0, from + delta);
      if (length) target = Math.min(target, Math.max(0, length - 1000));
      return player.seek(target).then(function () {
        position = target;
        render();
      });
    });
  }

  toggle.addEventListener("click", function () {
    if (fellBack || !deviceId) return;
    if (!started) startTrack();
    else player.togglePlay();
  });
  back.addEventListener("click", function () {
    skip(-SKIP_MS);
  });
  forward.addEventListener("click", function () {
    skip(SKIP_MS);
  });

  // No progress updates while the page is hidden.
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stopTicking();
    else startTicking();
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
      enableControls();
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
      if (state) takeState(state);
    });
    player.connect().then(function (connected) {
      if (!connected) fallBack("Spotify's player couldn't connect.");
    });
  };

  render();

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
